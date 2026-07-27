# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-06

# JNU_MWP_PDK Waveguide to Path 功能。
# 将波导 instance 还原为 Si 层原始 Manhattan Path，便于再次执行 Path to Waveguide。

import json

import pya

from JNU_MWP_tools.core.common import (
    SI_LAYER,
    WG_LAYER,
    RAW_PATH_GDS_PROPERTY,
    RAW_PATH_PROPERTY,
    _active_context,
    _debug_log,
    _dedupe_path_points,
    _is_array_instance,
    _main_window,
    _message,
    _raw_path_cell_name,
    _value,
    WAVEGUIDE_CONTAINER_GDS_PROPERTY,
    WAVEGUIDE_CONTAINER_PREFIX,
    WAVEGUIDE_CONTAINER_PROPERTY,
    WAVEGUIDE_KIND_GDS_PROPERTY,
    WAVEGUIDE_KIND_PROPERTY,
)


INTERNAL_WAVEGUIDE_PCELL_NAMES = ("Waveguide", "Composite_Waveguide")


def _cell_basic_name(cell):
    """读取 cell 的 basic_name；若普通 cell 不支持该接口，则退回 name。"""
    try:
        basic_name = cell.basic_name()
    except Exception:
        basic_name = None
    if basic_name:
        return basic_name
    try:
        return _value(cell, "name")
    except Exception:
        return ""


def _property_value(target, property_name, gds_property):
    """读取命名属性；GDS 重开后退回读取数字属性镜像。"""
    for key in (property_name, gds_property):
        try:
            value = target.property(key)
        except Exception:
            value = None
        if value not in (None, ""):
            return str(value)
    return ""


def _raw_property_marks_waveguide(cell):
    """兼容标记属性尚未写入的早期内部波导 cell。"""
    raw_value = _property_value(cell, RAW_PATH_PROPERTY, RAW_PATH_GDS_PROPERTY)
    if not raw_value:
        return False
    try:
        data = json.loads(raw_value)
    except Exception:
        return False
    return data.get("jnu_waveguide_kind") in ("single", "composite")


def _is_waveguide_cell(cell):
    """识别新版标记波导、当前 PCell variant 与旧版名称式 Waveguide cell。"""
    if cell is None:
        return False
    if _property_value(
        cell, WAVEGUIDE_KIND_PROPERTY, WAVEGUIDE_KIND_GDS_PROPERTY
    ) in ("single", "composite"):
        return True
    if _raw_property_marks_waveguide(cell):
        return True
    try:
        declaration = cell.pcell_declaration()
        if declaration is not None and declaration.name() in INTERNAL_WAVEGUIDE_PCELL_NAMES:
            return True
    except Exception:
        pass
    return "Waveguide" in _cell_basic_name(cell)


def _is_waveguide_container_cell(cell):
    """识别承载 Path to Waveguide 内部实例的可折叠容器。"""
    if cell is None:
        return False
    if _property_value(
        cell, WAVEGUIDE_CONTAINER_PROPERTY, WAVEGUIDE_CONTAINER_GDS_PROPERTY
    ) == "v1":
        return True
    return _cell_basic_name(cell).startswith(WAVEGUIDE_CONTAINER_PREFIX)


def _copy_path(path):
    """复制一个整数 Path，避免直接修改源 cell 中已有图形。"""
    return pya.Path(
        [pya.Point(point.x, point.y) for point in path.each_point()],
        path.width,
        path.bgn_ext,
        path.end_ext,
    )


def _dpath_to_integer_path(dpath, dbu, width_um):
    """显式量化 DPath，避免部分 KLayout 版本的 to_itype 遗失端部延伸。"""
    points = [
        pya.Point(
            int(round(point.x / dbu)),
            int(round(point.y / dbu)),
        )
        for point in dpath.each_point()
    ]
    try:
        bgn_ext_um = float(dpath.bgn_ext)
    except Exception:
        bgn_ext_um = 0.0
    try:
        end_ext_um = float(dpath.end_ext)
    except Exception:
        end_ext_um = 0.0
    return pya.Path(
        points,
        max(1, int(round(float(width_um) / dbu))),
        int(round(bgn_ext_um / dbu)),
        int(round(end_ext_um / dbu)),
    )


def _path_is_manhattan(path):
    """判断 Path 是否为 Manhattan 路径，供 Waveguide to Path 还原原始输入路径使用。"""
    try:
        if hasattr(path, "is_manhattan"):
            result = path.is_manhattan()
            if result:
                return True
    except Exception:
        pass

    points = list(path.each_point())
    if len(points) < 2:
        return False
    for index in range(1, len(points)):
        p0 = points[index - 1]
        p1 = points[index]
        if p0.x != p1.x and p0.y != p1.y:
            return False
    return True


def _path_from_raw_property(wg_cell, layout):
    """从新版 Waveguide cell 的隐藏 property 中恢复原始 Manhattan Path。"""
    try:
        raw_value = wg_cell.property(RAW_PATH_PROPERTY)
    except Exception:
        raw_value = None
    if not raw_value:
        try:
            raw_value = wg_cell.property(RAW_PATH_GDS_PROPERTY)
        except Exception:
            raw_value = None
    if not raw_value:
        return None

    try:
        data = json.loads(str(raw_value))
        width_um = float(data.get("width_um", 0.5))
        bgn_ext_um = float(data.get("bgn_ext_um", 0.0))
        end_ext_um = float(data.get("end_ext_um", 0.0))

        points = []
        for item in data.get("points_um", []):
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            points.append(
                pya.Point(
                    int(round(float(item[0]) / layout.dbu)),
                    int(round(float(item[1]) / layout.dbu)),
                )
            )
        points = _dedupe_path_points(points)
        if len(points) < 2:
            return None

        path = pya.Path(
            points,
            max(1, int(round(width_um / layout.dbu))),
            int(round(bgn_ext_um / layout.dbu)),
            int(round(end_ext_um / layout.dbu)),
        )
        return path if _path_is_manhattan(path) else None
    except Exception:
        return None


def _path_from_raw_cell(wg_cell, layout):
    """从旧版 raw helper cell 恢复 Path，并删除无引用 helper。"""
    try:
        raw_cell = layout.cell(_raw_path_cell_name(wg_cell))
    except Exception:
        raw_cell = None
    if raw_cell is None:
        return None

    wg_layer_index = layout.layer(WG_LAYER)
    for shape in raw_cell.shapes(wg_layer_index):
        if shape.is_path():
            path = _copy_path(shape.path)
            if _path_is_manhattan(path):
                try:
                    layout.delete_cell(raw_cell.cell_index())
                except Exception:
                    pass
                return path
    return None


def _path_from_waveguide_cell(wg_cell, layout, instance=None):
    """从 Waveguide cell 中取回原始 Manhattan 输入 Path。

    读取顺序为：PCell 参数 path、cell 恢复属性、实例上的 GDS 属性镜像、
    旧版 Waveguide cell 内的 WG 层 path、旧版 raw cell。
    若某些旧 cell 只保存弯曲 path，会被跳过，避免输出无法再次 Path to Waveguide 的非 Manhattan 路径。
    """
    width_um = 0.5

    try:
        params = wg_cell.pcell_parameters_by_name()
    except Exception:
        params = {}

    if params:
        dpath = params.get("path")
        width_um = float(params.get("straight_width", params.get("width", width_um)))
        if dpath is not None:
            if isinstance(dpath, pya.DPath):
                path = _dpath_to_integer_path(dpath, layout.dbu, width_um)
            else:
                path = _copy_path(dpath)
                path.width = max(1, int(round(width_um / layout.dbu)))
            return path if _path_is_manhattan(path) else None

    path = _path_from_raw_property(wg_cell, layout)
    if path is not None:
        return path

    # GDSII 写出 PCell 时会展开 variant；实例属性是同一恢复数据的文件载体。
    if instance is not None:
        path = _path_from_raw_property(instance, layout)
        if path is not None:
            return path

    wg_layer_index = layout.layer(WG_LAYER)
    for shape in wg_cell.shapes(wg_layer_index):
        if shape.is_path():
            path = _copy_path(shape.path)
            if _path_is_manhattan(path):
                return path

    path = _path_from_raw_cell(wg_cell, layout)
    if path is not None:
        return path

    return None


def _cleanup_unreferenced_waveguide_cells(layout, cell_indices):
    """删除已无任何父实例引用的 Waveguide cell 及其旧版 raw helper。"""
    removed = 0
    for cell_index in set(cell_indices):
        try:
            wg_cell = layout.cell(cell_index)
        except Exception:
            wg_cell = None
        if wg_cell is None:
            continue
        try:
            if any(True for _ in wg_cell.each_parent_inst()):
                continue
        except Exception:
            continue

        raw_cell = layout.cell(_raw_path_cell_name(wg_cell))
        try:
            layout.delete_cell(cell_index)
            removed += 1
        except Exception:
            continue
        if raw_cell is not None:
            try:
                if not any(True for _ in raw_cell.each_parent_inst()):
                    layout.delete_cell(raw_cell.cell_index())
            except Exception:
                pass
    return removed


def _container_waveguide_instances(container_instance, full_container_trans=None):
    """列出容器内直接波导及其相对当前父 cell 的完整变换。"""
    container_cell = container_instance.cell
    if container_cell is None:
        return []
    container_trans = (
        full_container_trans
        if full_container_trans is not None
        else _value(container_instance, "trans")
    )
    instances = []
    for instance in list(container_cell.each_inst()):
        if instance is None or not _is_waveguide_cell(instance.cell):
            continue
        instances.append((instance, container_trans * _value(instance, "trans")))
    return instances


def _collect_waveguide_instances(view, cell):
    """收集直接或内部容器中的 Waveguide 实例及其完整层级变换。"""
    instances = []

    # 优先处理用户选中的实例；ObjectInstPath.trans 是完整层级变换。
    for obj in view.object_selection:
        if not obj.is_cell_inst():
            continue
        inst = obj.inst()
        if inst is None:
            continue
        try:
            trans = _value(obj, "trans")
        except Exception:
            trans = _value(inst, "trans")
        if _is_waveguide_cell(inst.cell):
            instances.append((inst, trans))
        elif _is_waveguide_container_cell(inst.cell):
            instances.extend(_container_waveguide_instances(inst, trans))

    if instances:
        return instances

    # 未选中时扫描当前 cell 的直接内部波导和一个层级的内部容器。
    for inst in list(cell.each_inst()):
        if inst is None:
            continue
        if _is_waveguide_cell(inst.cell):
            instances.append((inst, _value(inst, "trans")))
        elif _is_waveguide_container_cell(inst.cell):
            instances.extend(_container_waveguide_instances(inst))

    return instances


def _cleanup_empty_waveguide_containers(layout, parent_cell, cleanup_cell_indices):
    """移除已无内部实例的容器，并交由既有流程清理失去父引用的 variant。"""
    removed = 0
    for container_instance in list(parent_cell.each_inst()):
        container_cell = container_instance.cell
        if not _is_waveguide_container_cell(container_cell):
            continue
        if any(True for _instance in container_cell.each_inst()):
            continue
        if not container_cell.bbox().empty():
            continue
        try:
            container_instance.delete()
            layout.delete_cell(container_cell.cell_index())
            removed += 1
        except Exception:
            continue
    _ = cleanup_cell_indices
    return removed


def waveguide_to_path():
    """把选中的 Waveguide PCell 反转换为 Si 层原始 Manhattan Path。

    从 PCell 参数中读取并恢复原始 Manhattan path，避免从圆角实体反推而丢失拐点。
    若未选中任何波导，自动扫描当前 cell 中所有 Waveguide 实例并转换。
    """
    transaction_started = False
    try:
        view, layout, cell = _active_context()

        selected_instances = _collect_waveguide_instances(view, cell)
        if not selected_instances:
            _message("JNU_MWP_PDK", "当前 cell 中没有找到 Waveguide 实例。")
            return

        view.transaction("JNU Waveguide to Path")
        transaction_started = True

        si_layer_index = layout.layer(SI_LAYER)
        if si_layer_index is None:
            raise RuntimeError("布局中没有 Si 层。")

        converted_count = 0
        skipped_arrays = 0
        skipped_missing_path = 0
        cleanup_cell_indices = []

        for inst, trans in selected_instances:
            try:
                if _is_array_instance(inst):
                    skipped_arrays += 1
                    continue

                wg_cell = inst.cell
                if wg_cell is None:
                    skipped_missing_path += 1
                    continue

                new_path = _path_from_waveguide_cell(wg_cell, layout, inst)
                if new_path is None:
                    skipped_missing_path += 1
                    continue

                # 将子 cell 坐标变换到当前父 cell 坐标后写回 Si 层，便于再次 Path to Waveguide。
                cell.shapes(si_layer_index).insert(new_path.transformed(trans))

                # 删除原 PCell 实例；Instance.delete() 才是删除 cell instance 的正确接口。
                cleanup_cell_indices.append(wg_cell.cell_index())
                inst.delete()
                converted_count += 1
            except Exception as error:
                _debug_log("Waveguide to Path skipped instance: %s" % error)
                skipped_missing_path += 1

        _cleanup_empty_waveguide_containers(layout, cell, cleanup_cell_indices)
        _cleanup_unreferenced_waveguide_cells(layout, cleanup_cell_indices)

        if converted_count == 0 and skipped_arrays == 0 and skipped_missing_path == 0:
            _message("JNU_MWP_PDK", "当前 cell 中没有找到 Waveguide 实例。")
            transaction_started = False
            # 未转换任何波导，直接提交并重绘视图，避免 view 状态异常。
            view.commit()
            _main_window().redraw()
            return

        # 删除实例后，KLayout 选择集可能仍保存已失效对象句柄；
        # 先清空选择，避免紧接着执行 Path to Waveguide 时访问旧 Shape/Instance。
        view.clear_object_selection()
        view.commit()
        transaction_started = False

        if converted_count > 0:
            _main_window().redraw()
            # 转换成功时不弹窗，静默完成。
        else:
            _message(
                "JNU_MWP_PDK",
                "未能转换任何 Waveguide 实例。\n"
                "跳过阵列实例 %d 个；缺少原始 Manhattan path 的实例 %d 个。"
                % (skipped_arrays, skipped_missing_path),
            )
    except Exception as error:
        if transaction_started:
            try:
                # 出错时提交事务而非取消，避免视图状态残留导致版图界面空白。
                view.commit()
                _main_window().redraw()
            except Exception:
                pass
        _message("JNU_MWP_PDK", "Waveguide to Path 失败：\n%s" % error)

__all__ = [
    "waveguide_to_path",
    "_path_from_waveguide_cell",
    "_path_is_manhattan",
    "_cleanup_unreferenced_waveguide_cells",
    "_cleanup_empty_waveguide_containers",
    "_is_waveguide_cell",
    "_is_waveguide_container_cell",
]
