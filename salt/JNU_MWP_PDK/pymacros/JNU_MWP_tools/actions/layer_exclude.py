# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""
KLayout GUI 宏脚本：Layer Exclude。
1. 对当前打开的版图做全层级 flatten。
2. 弹窗让用户勾选需要保留的工艺图层。
3. 未勾选的其它图层会被排除/删除。
4. 可选地对保留图层做几何 merge。
5. 可选删除除目标 Cell 之外的其它 Cell。

重要说明：
脚本只修改 KLayout 当前内存中的版图，不调用 layout.write()，
因此不会自动保存或覆盖原始 GDS/OAS 文件。
"""

import json      # 保存 Layer Exclude GUI 参数。
import os        # 处理 ~/.klayout 参数文件路径。

import pya       # KLayout Python API

from JNU_MWP_tools.core.gui_state import exec_dialog_with_persisted_size


TOOL_TITLE = "Layer Exclude"


# 需要在弹窗中列出来的候选保留图层。
#
# tuple 格式：
#   (显示名称, layer number, datatype, 中文说明)
#
# datatype=None 表示保留该 layer number 下的全部 datatype，
# 等价于 DRC 脚本里常见的 input(99) / input(290) 写法。
KEEP_LAYER_SPECS = [
    ("LayerSi", 1, 0, "硅波导层"),
    ("LayerSi_rib", 2, 0, "脊型硅层"),
    ("LayerFP", 99, None, "芯片边界"),
    ("LayerCD", 290, None, "芯片设计区域"),
    ("LayerM1", 11, 0, "金属1层（加热电极）"),
    ("LayerM2", 12, 0, "金属2层（布线）"),
    ("LayerMLOpen", 13, 0, "金属焊盘开口层"),
    ("LayerText", 10, 0, "文本标记层（Layer 10）"),
    ("LayerDeepTrench", 40, 0, "深槽隔离层"),
    ("LayerDicing", 210, 0, "划片层"),
]


DEFAULT_MERGE_LAYER_NAMES = set([
    "LayerSi",
    "LayerSi_rib",
    "LayerM1",
    "LayerM2",
])


def _layer_exclude_params_file():
    """返回 Layer Exclude 参数持久化文件路径。"""
    home = os.path.expanduser("~")
    klayout_dir = os.path.join(home, ".klayout")
    if not os.path.isdir(klayout_dir):
        os.makedirs(klayout_dir, exist_ok=True)
    return os.path.join(klayout_dir, "jnu_layer_exclude_params.json")


def _current_layer_names():
    """返回当前候选图层名称列表。"""
    return [spec[0] for spec in KEEP_LAYER_SPECS]


def _load_layer_exclude_params():
    """读取 Layer Exclude 上一次 GUI 勾选状态。"""
    layer_names = _current_layer_names()
    defaults = {
        "known_layers": list(layer_names),
        "keep_layers": list(layer_names),
        "merge_layers": [
            name for name in layer_names if name in DEFAULT_MERGE_LAYER_NAMES
        ],
        "path_to_polygon": True,
    }

    filepath = _layer_exclude_params_file()
    if not os.path.isfile(filepath):
        return defaults

    try:
        with open(filepath, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return defaults

    if not isinstance(data, dict):
        return defaults

    known_layers = set(data.get("known_layers", []))
    keep_layers = set(data.get("keep_layers", []))

    # 已保存状态中没有出现过的新候选层默认勾选，减少误删风险。
    defaults["known_layers"] = list(layer_names)
    defaults["keep_layers"] = [
        name for name in layer_names
        if name in keep_layers or name not in known_layers
    ]

    merge_layers = set(data.get("merge_layers", defaults["merge_layers"]))
    defaults["merge_layers"] = [
        name for name in layer_names if name in merge_layers
    ]
    # 兼容旧版本保存的 merge_path_shapes 键；新语义统一叫 Path to polygon。
    defaults["path_to_polygon"] = bool(
        data.get(
            "path_to_polygon",
            data.get("merge_path_shapes", defaults["path_to_polygon"]),
        )
    )
    return defaults


def _save_layer_exclude_params(selected_specs, merge_specs, path_to_polygon):
    """保存 Layer Exclude GUI 勾选状态，供下次打开弹窗时恢复。"""
    data = {
        "known_layers": _current_layer_names(),
        "keep_layers": [spec[0] for spec in selected_specs],
        "merge_layers": [spec[0] for spec in merge_specs],
        "path_to_polygon": bool(path_to_polygon),
    }
    try:
        with open(_layer_exclude_params_file(), "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _value(obj, name):
    """兼容读取 KLayout 对象属性。

    不同 KLayout 版本中，有些接口既可能表现为属性，也可能表现为方法。
    例如 cell.name 和 cell.name() 都可能遇到，所以这里统一包装一下。
    """
    attr = getattr(obj, name)
    return attr() if callable(attr) else attr


def _main_window():
    """取得 KLayout 主窗口对象，后续弹窗都挂在主窗口上。"""
    return pya.Application.instance().main_window()


def _message(kind, title, text, parent=None):
    """显示提示框。

    pya.MessageBox.warning/info 是本机已有宏中常用的写法；
    critical 情况也用 warning 样式显示，避免不同版本没有 critical 接口。
    """
    if kind == "warning":
        return pya.MessageBox.warning(title, text, pya.MessageBox.Ok)
    if kind == "critical":
        return pya.MessageBox.warning(title, text, pya.MessageBox.Ok)
    return pya.MessageBox.info(title, text, pya.MessageBox.Ok)


def _question(title, text, parent=None):
    """显示 Yes/No 确认框，返回 True 表示用户选择 Yes。"""
    question = pya.QMessageBox()
    question.setWindowTitle(title)
    question.setText(text)
    question.setStandardButtons(pya.QMessageBox.Yes | pya.QMessageBox.No)
    question.setDefaultButton(pya.QMessageBox.No)
    return pya.QMessageBox_StandardButton(question.exec_()) == pya.QMessageBox.Yes


def _current_layout_and_cell():
    """取得当前 view、layout 和目标 Cell。

    优先使用名为 TOP 的 Cell，符合“保留 TOP”的操作习惯；
    如果版图里没有 TOP，则退回到当前 GUI 中激活的 Cell。
    """
    mw = _main_window()
    view = mw.current_view()
    if view is None:
        return None, None, None

    cv = view.active_cellview()
    if cv is None:
        return view, None, None

    layout = cv.layout()
    active_cell = cv.cell

    # 如果存在显式命名的 TOP，就以 TOP 作为 flatten 和保留的目标。
    top_cell = None
    try:
        top_cell = layout.cell("TOP")
    except Exception:
        top_cell = None

    return view, layout, top_cell or active_cell


def _layer_label(name, layer, datatype, description):
    """生成弹窗中每个图层复选框的显示文字。"""
    datatype_text = "*" if datatype is None else str(datatype)
    return "%-16s input(%s,%s)  %s" % (name, layer, datatype_text, description)


def _show_options_dialog(target_cell):
    """显示 Layer Exclude 操作选项弹窗。

    返回值：
      None：用户取消。
      (selected_specs, delete_other_cells)：用户确认后的图层勾选结果和 Cell 清理选项。
    """
    saved = _load_layer_exclude_params()
    saved_keep_layers = set(saved["keep_layers"])

    dialog = pya.QDialog(_main_window())
    dialog.setWindowTitle(TOOL_TITLE)

    layout = pya.QVBoxLayout(dialog)
    dialog.setLayout(layout)

    target_name = _value(target_cell, "name")
    info = pya.QLabel(
        "目标 Cell：%s\n"
        "运行后会 flatten 到该 Cell。\n"
        "勾选的图层会保留；未勾选的 layout layer 会被排除/删除。\n"
        "LayerFP/LayerCD 使用 * 表示保留该 layer number 的全部 datatype。"
        % target_name,
        dialog,
    )
    layout.addWidget(info)

    # 为每个候选图层创建一个复选框。默认全部勾选，减少误删风险。
    layer_boxes = []
    for spec in KEEP_LAYER_SPECS:
        box = pya.QCheckBox(_layer_label(*spec), dialog)
        box.setChecked(spec[0] in saved_keep_layers)
        layout.addWidget(box)
        layer_boxes.append((box, spec))

    layout.addSpacing(8)

    # 勾选后，会对最终保留下来的上述图层逐层做几何 merge。
    # 未勾选保留的图层会被删除，因此不会参与 merge。
    # 这个选项只影响 cell 表，不影响已经 flatten 到目标 Cell 的几何图形。
    delete_cells_box = pya.QCheckBox(
        "删除除 %s 之外的所有 Cell（不保存 GDS）" % target_name,
        dialog,
    )
    delete_cells_box.setChecked(False)
    layout.addWidget(delete_cells_box)

    # 用 QPushButton 手动连接 accept/reject。
    # 这是本机其它 KLayout 宏中更常见的写法，比 QDialogButtonBox 更兼容。
    buttons = pya.QHBoxLayout(dialog)
    cancel = pya.QPushButton("Cancel", dialog)
    ok = pya.QPushButton("OK", dialog)
    cancel.clicked(lambda _checked: dialog.reject())
    ok.clicked(lambda _checked: dialog.accept())
    buttons.addWidget(cancel)
    buttons.addWidget(ok)
    layout.addLayout(buttons)

    # 某些 KLayout 版本没有“弹窗接受状态”的类常量。
    # Qt/KLayout 中 reject 通常返回 0，accept/OK 返回非 0，因此这里直接判断返回值。
    if exec_dialog_with_persisted_size(dialog, "layer_exclude_options") == 0:
        return None

    # 从复选框读取用户最终选择。
    selected_specs = [spec for box, spec in layer_boxes if box.isChecked()]
    return selected_specs, delete_cells_box.isChecked()


def _show_merge_dialog(selected_specs):
    """第二个弹窗：只在被保留的图层中选择需要 merge 的图层。"""
    saved = _load_layer_exclude_params()
    saved_merge_layers = set(saved["merge_layers"])

    dialog = pya.QDialog(_main_window())
    dialog.setWindowTitle("选择需要 merge 的图层")

    layout = pya.QVBoxLayout(dialog)
    dialog.setLayout(layout)

    info = pya.QLabel(
        "只列出第一个弹窗中勾选保留的图层。\n"
        "默认勾选 LayerSi、LayerSi_rib、LayerM1、LayerM2。",
        dialog,
    )
    layout.addWidget(info)

    warning = pya.QLabel(
        "提示：如果版图很大，merge 将会很慢；Si 层结构特别多时建议谨慎勾选。",
        dialog,
    )
    layout.addWidget(warning)

    merge_layer_boxes = []
    for spec in selected_specs:
        box = pya.QCheckBox(_layer_label(*spec), dialog)
        box.setChecked(spec[0] in saved_merge_layers)
        layout.addWidget(box)
        merge_layer_boxes.append((box, spec))

    layout.addSpacing(8)
    path_to_polygon_box = pya.QCheckBox(
        "Path to polygon（将 Si 层 Path 按实际宽度转为 Polygon）",
        dialog,
    )
    path_to_polygon_box.setChecked(bool(saved["path_to_polygon"]))
    layout.addWidget(path_to_polygon_box)

    buttons = pya.QHBoxLayout(dialog)
    cancel = pya.QPushButton("Cancel", dialog)
    ok = pya.QPushButton("OK", dialog)
    cancel.clicked(lambda _checked: dialog.reject())
    ok.clicked(lambda _checked: dialog.accept())
    buttons.addWidget(cancel)
    buttons.addWidget(ok)
    layout.addLayout(buttons)

    if exec_dialog_with_persisted_size(dialog, "layer_exclude_merge") == 0:
        return None

    return (
        [spec for box, spec in merge_layer_boxes if box.isChecked()],
        path_to_polygon_box.isChecked(),
    )


def _matches_keep_spec(layer_info, selected_specs):
    """判断某个实际 layout layer 是否命中用户勾选的保留规则。"""
    layer = _value(layer_info, "layer")
    datatype = _value(layer_info, "datatype")

    for _, keep_layer, keep_datatype, _ in selected_specs:
        if layer != keep_layer:
            continue
        # keep_datatype 为 None 时，表示该 layer number 的所有 datatype 都保留。
        if keep_datatype is None or datatype == keep_datatype:
            return True
    return False


def _delete_unselected_layers(layout, selected_specs):
    """删除所有未勾选保留的 layout layer，并返回被删除的 layer/datatype 列表。"""
    deleted = []
    # layer_indexes() 在删除过程中会变化，因此先转成 list 固定快照。
    for layer_index in list(layout.layer_indexes()):
        info = layout.get_info(layer_index)
        if _matches_keep_spec(info, selected_specs):
            continue

        deleted.append("%s/%s" % (_value(info, "layer"), _value(info, "datatype")))
        layout.delete_layer(layer_index)
    return deleted


def _delete_cells_except(layout, keep_cell):
    """删除除 keep_cell 之外的所有 Cell，并返回被删除的 Cell 名称列表。"""
    keep_index = _value(keep_cell, "cell_index")
    to_delete = []
    deleted_names = []

    for cell in list(layout.each_cell()):
        cell_index = _value(cell, "cell_index")
        if cell_index == keep_index:
            continue
        to_delete.append(cell_index)
        deleted_names.append(_value(cell, "name"))

    if to_delete:
        # KLayout 的 delete_cells 接收 cell index 列表。
        layout.delete_cells(to_delete)

    return deleted_names


def _bool_method(obj, name):
    """安全调用 KLayout 的 bool 方法；旧版本没有某些 shape 类型判断方法。"""
    method = getattr(obj, name, None)
    return bool(method()) if callable(method) else False


def _shape_is_mergeable(shape):
    """只对能转成 polygon 的制造几何做局部 merge，跳过 text 等非几何对象。"""
    return (
        _bool_method(shape, "is_box")
        or _bool_method(shape, "is_polygon")
        or _bool_method(shape, "is_simple_polygon")
    )


def _box_tuple(box):
    """把 pya.Box 转成便于排序/比较的 tuple。"""
    return (
        _value(box, "left"),
        _value(box, "bottom"),
        _value(box, "right"),
        _value(box, "top"),
    )


def _boxes_touch_or_overlap(a, b):
    """判断两个 bbox 是否接触或重叠。"""
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _shape_to_region(shape):
    """把单个 shape 转成 Region。

    只用于局部相交判断和局部 merge。路径会转成其实际宽度对应的 polygon 区域。
    """
    region = pya.Region()

    if _bool_method(shape, "is_box"):
        region.insert(_value(shape, "box"))
    elif _bool_method(shape, "is_path"):
        region.insert(_value(shape, "path"))
    elif _bool_method(shape, "is_polygon"):
        region.insert(_value(shape, "polygon"))
    elif _bool_method(shape, "is_simple_polygon"):
        try:
            region.insert(_value(shape, "simple_polygon"))
        except Exception:
            region.insert(_value(shape, "polygon"))

    return region


def _region_count(region):
    """兼容读取 Region 中 polygon 数量。"""
    count = getattr(region, "count", None)
    if callable(count):
        return count()
    size = getattr(region, "size", None)
    return size() if callable(size) else 0


def _regions_overlap(region_a, region_b):
    """判断两个 Region 是否有实际面积重叠。"""
    return _region_count(region_a & region_b) > 0


def _find_overlapping_groups(records):
    """用 bbox sweep + 几何 AND 找出真正重叠的图形连通组。

    records 中每一项为 [bbox_tuple, shape, region_or_None]。返回值只包含大小大于 1
    的组，也就是确实存在实际面积重叠、值得局部 merge 的候选集合。
    """
    count = len(records)
    parent = list(range(count))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(a, b):
        root_a = find(a)
        root_b = find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    def get_region(index):
        if records[index][2] is None:
            records[index][2] = _shape_to_region(records[index][1])
        return records[index][2]

    order = sorted(range(count), key=lambda i: records[i][0][0])
    active = []

    for index in order:
        box = records[index][0]
        active = [i for i in active if records[i][0][2] >= box[0]]

        for other in active:
            if _boxes_touch_or_overlap(box, records[other][0]) and _regions_overlap(
                get_region(index), get_region(other)
            ):
                union(index, other)

        active.append(index)

    groups = {}
    for index in range(count):
        groups.setdefault(find(index), []).append(index)

    return [group for group in groups.values() if len(group) > 1]


def _convert_si_paths_to_polygons(layout, target_cell, selected_specs, path_to_polygon=True):
    """将保留后的 Si(1/0) 层 Path 按实际宽度转成 Polygon。

    该步骤独立于 merge：用户勾选 Path to polygon 时，目标是消除 Si 层 Path
    图形，便于后续写出或制造检查，而不是只处理发生重叠的 Path。
    """
    if not path_to_polygon:
        return 0

    # 只有 LayerSi 被保留时才处理；如果用户没有保留 Si 层，则不主动创建新层。
    if "LayerSi" not in set([spec[0] for spec in selected_specs]):
        return 0

    si_layer_index = layout.find_layer(1, 0)
    if si_layer_index is None:
        return 0

    converted = []
    dst_shapes = target_cell.shapes(si_layer_index)
    for shape in list(target_cell.each_shape(si_layer_index)):
        if not _bool_method(shape, "is_path"):
            continue
        region = pya.Region()
        region.insert(_value(shape, "path"))
        if _region_count(region) == 0:
            continue
        converted.append((shape, region))

    for shape, region in converted:
        shape.delete()
        dst_shapes.insert(region)

    return len(converted)


def _merge_selected_layers(layout, target_cell, selected_specs):
    """对用户勾选保留的实际 layer/datatype 分别做 merge。

    这里按实际 layout layer index 处理。对于 LayerFP/LayerCD 这种 datatype=None
    的规则，如果版图中有多个 datatype，会逐个 datatype 分别 merge。
    """
    layer_indexes = []
    merged_labels = []

    for layer_index in list(layout.layer_indexes()):
        info = layout.get_info(layer_index)
        if _matches_keep_spec(info, selected_specs):
            layer_indexes.append(layer_index)

    for layer_index in layer_indexes:
        info = layout.get_info(layer_index)
        merged_labels.append("%s/%s" % (_value(info, "layer"), _value(info, "datatype")))

        dst_shapes = target_cell.shapes(layer_index)

        # 版图已经 flatten 到 target_cell 后，只需要检查当前 Cell 里的这一层。
        # 先用 bbox 找局部重叠/接触的候选组；孤立图形完全不参与 Region merge。
        records = []
        for shape in target_cell.each_shape(layer_index):
            if not _shape_is_mergeable(shape):
                continue
            records.append([_box_tuple(_value(shape, "bbox")), shape, None])

        groups = _find_overlapping_groups(records)
        for group in groups:
            region = pya.Region()
            shapes_to_delete = []

            for index in group:
                shape = records[index][1]
                shape_region = records[index][2]
                if shape_region is None:
                    shape_region = _shape_to_region(shape)
                if _region_count(shape_region) == 0:
                    continue
                region += shape_region
                shapes_to_delete.append(shape)

            if not shapes_to_delete:
                continue

            region.merge()
            for shape in shapes_to_delete:
                shape.delete()
            dst_shapes.insert(region)

    return merged_labels


def flatten_keep_layers():
    """兼容旧入口：弹窗确认后执行 flatten、删层和可选删 Cell。"""
    view, layout, target_cell = _current_layout_and_cell()
    if view is None or layout is None or target_cell is None:
        _message("warning", TOOL_TITLE, "请先在 KLayout 中打开一个版图并选中目标 Cell。")
        return

    options = _show_options_dialog(target_cell)
    if options is None:
        return

    selected_specs, delete_other_cells = options
    if not selected_specs:
        # 用户一个图层都没勾选时，会删除所有 layer，所以额外二次确认。
        ok = _question(
            "确认删除所有图层",
            "没有勾选任何保留图层。继续将排除/删除当前 layout 中所有 layer。是否继续？",
        )
        if not ok:
            return

    if selected_specs:
        merge_options = _show_merge_dialog(selected_specs)
        if merge_options is None:
            return
        selected_merge_specs, path_to_polygon = merge_options
    else:
        selected_merge_specs = []
        path_to_polygon = True

    # 用户完整确认两个弹窗后保存 GUI 状态；取消弹窗时不覆盖旧设置。
    _save_layer_exclude_params(
        selected_specs,
        selected_merge_specs,
        path_to_polygon,
    )

    transaction_started = False
    try:
        # 使用 transaction，让这次操作在 KLayout 中可以作为一个整体 Undo。
        view.transaction("JNU Layer Exclude")
        transaction_started = True

        # -1 表示展开所有层级。
        # prune=False 表示 flatten 后暂时不删原 cell，由后面的复选框决定是否清理。
        layout.flatten(_value(target_cell, "cell_index"), -1, False)

        # flatten 后再删层，这样子 cell 中带进来的不需要图层也会一起被删除。
        deleted_layers = _delete_unselected_layers(layout, selected_specs)
        path_polygon_count = _convert_si_paths_to_polygons(
            layout,
            target_cell,
            selected_specs,
            path_to_polygon,
        )
        merged_layers = []
        if selected_merge_specs:
            selected_keep_names = set([spec[0] for spec in selected_specs])
            kept_merge_specs = [
                spec for spec in selected_merge_specs
                if spec[0] in selected_keep_names
            ]
            merged_layers = _merge_selected_layers(
                layout,
                target_cell,
                kept_merge_specs,
            )

        deleted_cells = []
        if delete_other_cells:
            deleted_cells = _delete_cells_except(layout, target_cell)

        # 提交 transaction。
        if transaction_started:
            view.commit()

        # 刷新显示；某些 KLayout 版本没有该接口，失败时忽略即可。
        try:
            view.update_content()
        except Exception:
            pass

        summary = (
            "完成。\n\n"
            "Flatten 目标 Cell：%s\n"
            "保留图层数量：%d\n"
            "Merge 图层数量：%d\n"
            "Path to polygon：%s（转换 %d 条 Si Path）\n"
            "删除图层数量：%d\n"
            "删除 Cell 数量：%d\n\n"
            "注意：脚本没有保存 GDS；如需写出请手动另存。"
            % (
                _value(target_cell, "name"),
                len(selected_specs),
                len(merged_layers),
                "是" if path_to_polygon else "否",
                path_polygon_count,
                len(deleted_layers),
                len(deleted_cells),
            )
        )
        _message("information", TOOL_TITLE, summary)

    except Exception as exc:
        # 如果中途出错，取消 transaction，避免留下半完成的操作。
        if transaction_started:
            try:
                view.cancel()
            except Exception:
                pass
        _message("critical", TOOL_TITLE + " 失败", str(exc))
        raise


def layer_exclude():
    """JNU_MWP_PDK 菜单入口：Layer Exclude。

    该入口保留“勾选即保留”的安全语义；未勾选图层才会被排除/删除。
    """
    flatten_keep_layers()


if __name__ == "__main__":
    # 直接从 KLayout Python 宏编辑器运行本文件时，会执行这里。
    layer_exclude()
