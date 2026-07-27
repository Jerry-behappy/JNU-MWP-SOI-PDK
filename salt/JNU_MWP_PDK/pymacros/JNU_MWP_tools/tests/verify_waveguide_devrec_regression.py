# -*- coding: utf-8 -*-
"""验证 JNU Waveguide PCell 的几何与 Path 可逆数据。"""

import json
import os
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))
TOOLS_DIR = PYMACROS_DIR / "JNU_MWP_tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from JNU_MWP_tools.core.common import (  # noqa: E402
    RAW_PATH_CELL_SUFFIX,
    RAW_PATH_GDS_PROPERTY,
    RAW_PATH_PROPERTY,
    WG_LAYER,
)
import JNU_MWP_tools.actions.path_to_waveguide as path_tool  # noqa: E402
from JNU_MWP_tools.actions.path_to_waveguide import (  # noqa: E402
    JNULIB_NAME,
    _create_waveguide_cell,
    _path_to_dpath,
    _store_waveguide_recovery_property,
)
from JNU_MWP_tools.actions.waveguide_to_path import (  # noqa: E402
    _cleanup_unreferenced_waveguide_cells,
    _dpath_to_integer_path,
    _path_from_waveguide_cell,
)


SI_LAYER = pya.LayerInfo(1, 0)
PIN_LAYER = pya.LayerInfo(1, 10)
DEVREC_LAYER = pya.LayerInfo(68, 0)
DBU = 0.001
DEVREC_SIDE_CLEARANCE_DBU = 1000
LAYER_PROPERTIES_FILE = PYMACROS_DIR.parent / "layers.lyp"
EXPECTED_POINTS = [pya.Point(0, 0), pya.Point(80000, 0), pya.Point(80000, 80000)]


def _section_bbox(cell, layer_index, x_dbu, y_dbu):
    """返回水平直段指定 x 位置的窄截面包围盒。"""
    region = pya.Region(cell.begin_shapes_rec(layer_index))
    probe = pya.Region(pya.Box(x_dbu, y_dbu - 10000, x_dbu + 1, y_dbu + 10000))
    bbox = (region & probe).bbox()
    if bbox.empty():
        raise RuntimeError("截面探针未命中波导图形。")
    return bbox


def _check_cell_devrec(cell, layout, width_um):
    """检查 DevRec 与 Si 截面同心，并在两侧各保留 1 µm 净空。"""
    si_bbox = _section_bbox(cell, layout.layer(SI_LAYER), 20000, 0)
    devrec_bbox = _section_bbox(cell, layout.layer(DEVREC_LAYER), 20000, 0)
    expected_si_width = int(round(width_um / layout.dbu))
    expected_devrec_width = expected_si_width + 2 * DEVREC_SIDE_CLEARANCE_DBU
    if si_bbox.height() != expected_si_width:
        raise RuntimeError("Si 截面宽度错误。")
    if devrec_bbox.height() != expected_devrec_width:
        raise RuntimeError("DevRec 截面宽度错误。")
    if (
        si_bbox.bottom - devrec_bbox.bottom != DEVREC_SIDE_CLEARANCE_DBU
        or devrec_bbox.top - si_bbox.top != DEVREC_SIDE_CLEARANCE_DBU
    ):
        raise RuntimeError("DevRec 未在 Si 两侧分别保留 1 µm 净空。")


def _check_polygon_layers_and_pin_paths(cell, layout):
    """实体和识别层必须为 Polygon，只有 PinRec 保留短 Path。"""

    for layer_info, label in ((SI_LAYER, "Si"), (DEVREC_LAYER, "DevRec")):
        shapes = list(cell.shapes(layout.layer(layer_info)).each())
        if not shapes:
            raise RuntimeError("Waveguide %s 层为空。" % label)
        if any(shape.is_path() for shape in shapes):
            raise RuntimeError("Waveguide %s 层仍包含 Path。" % label)
        if any(not (shape.is_polygon() or shape.is_simple_polygon()) for shape in shapes):
            raise RuntimeError("Waveguide %s 层包含非 Polygon 实体。" % label)

    pin_paths = [
        shape.path
        for shape in cell.shapes(layout.layer(PIN_LAYER)).each()
        if shape.is_path()
    ]
    if len(pin_paths) != 2:
        raise RuntimeError("Waveguide 必须保留两个 PinRec Path。")


def _path_signature(path):
    return (
        list(path.each_point()),
        int(path.width),
        int(path.bgn_ext),
        int(path.end_ext),
    )


def _check_expected_path(path, width_um):
    expected = (EXPECTED_POINTS, int(round(width_um / DBU)), 0, 0)
    actual = _path_signature(path)
    if actual != expected:
        raise RuntimeError(
            "恢复的 Manhattan Path 与输入不一致：%s != %s。"
            % (actual, expected)
        )


def _check_no_embedded_raw_path(cell, layout):
    """新 Waveguide 不得在 1/99 写入任何恢复图形。"""
    if not cell.shapes(layout.layer(WG_LAYER)).is_empty():
        raise RuntimeError("新 Waveguide cell 的 1/99 必须严格为空。")


def _check_pcell_parameters(cell, layout, width_um, bend_type):
    """当前会话必须由本地 PCell path 参数保存可编辑路径。"""
    if not cell.is_pcell_variant():
        raise RuntimeError("Path to Waveguide 输出不是 PCell variant。")
    declaration = cell.pcell_declaration()
    declaration_name = declaration.name() if declaration is not None else ""
    library = cell.pcell_library()
    if declaration_name != "Waveguide" or library is not None:
        raise RuntimeError("PCell 声明不是当前版图中的本地 Waveguide。")
    params = cell.pcell_parameters_by_name()
    dpath = params.get("path")
    if dpath is None:
        raise RuntimeError("Waveguide PCell 缺少 path 参数。")
    _check_expected_path(dpath.to_itype(layout.dbu), width_um)
    if abs(float(params.get("width")) - width_um) > 1e-12:
        raise RuntimeError("Waveguide PCell width 参数错误。")
    if str(params.get("bend_type")) != bend_type:
        raise RuntimeError("Waveguide PCell bend_type 参数错误。")


def _check_raw_property(cell, width_um):
    """无图形属性必须记录 GDS 重读所需的点列与宽度。"""
    raw = cell.property(RAW_PATH_PROPERTY)
    if not raw:
        raw = cell.property(RAW_PATH_GDS_PROPERTY)
    if not raw:
        raise RuntimeError("Waveguide 缺少原始路径恢复属性。")
    data = json.loads(str(raw))
    if data.get("points_um") != [[0.0, 0.0], [80.0, 0.0], [80.0, 80.0]]:
        raise RuntimeError("恢复属性中的点列错误。")
    if abs(float(data.get("width_um")) - width_um) > 1e-12:
        raise RuntimeError("恢复属性中的宽度错误。")
    if float(data.get("bgn_ext_um", 0.0)) != 0.0 or float(data.get("end_ext_um", 0.0)) != 0.0:
        raise RuntimeError("恢复属性中的端部延伸错误。")


def _check_no_raw_helper_cells(layout):
    helpers = [cell.name for cell in layout.each_cell() if cell.name.endswith(RAW_PATH_CELL_SUFFIX)]
    if helpers:
        raise RuntimeError("检测到多余 raw helper cell：%s" % ", ".join(helpers))


def _check_path_extensions():
    """输入 Path 的端部延伸必须进入 PCell path 参数和恢复属性。"""
    source = pya.Path(EXPECTED_POINTS, 500, 700, 900)
    dpath = _path_to_dpath(source, DBU, 2.0)
    converted = _dpath_to_integer_path(dpath, DBU, 2.0)
    expected = (EXPECTED_POINTS, 2000, 700, 900)
    actual = _path_signature(converted)
    if actual != expected:
        raise RuntimeError(
            "Path 的宽度或端部延伸未完整映射到 PCell 参数：%s != %s。"
            % (actual, expected)
        )


def _check_unreferenced_cell_cleanup():
    """仅在最后一个实例删除后清理 PCell variant。"""
    layout = pya.Layout()
    layout.dbu = DBU
    top = layout.create_cell("ROUNDTRIP_TOP")
    dpath = pya.DPath([pya.DPoint(0, 0), pya.DPoint(80, 0), pya.DPoint(80, 80)], 0.5)
    params = {
        "width": 0.5,
        "radius": 20.0,
        "bend_type": "Circular",
        "bezier": 0.35,
        "Euler_Rmax": 30.0,
        "Euler_Rmin": 10.0,
        "npoints": 0,
    }
    cell = _create_waveguide_cell(layout, dpath, params, 1)
    cell_index = cell.cell_index()
    inst1 = top.insert(pya.CellInstArray(cell_index, pya.Trans()))
    inst2 = top.insert(pya.CellInstArray(cell_index, pya.Trans(100000, 0)))
    inst1.delete()
    if _cleanup_unreferenced_waveguide_cells(layout, [cell_index]) != 0:
        raise RuntimeError("仍有实例引用时不应删除共享 Waveguide cell。")
    inst2.delete()
    if _cleanup_unreferenced_waveguide_cells(layout, [cell_index]) != 1:
        raise RuntimeError("最后一个实例删除后未清理 Waveguide cell。")


def _check_legacy_embedded_path():
    """旧版 cell 内 1/99 Path 仍可读取，但不迁移写回。"""
    layout = pya.Layout()
    layout.dbu = DBU
    cell = layout.create_cell("Legacy_Embedded_Waveguide")
    cell.shapes(layout.layer(WG_LAYER)).insert(pya.Path(EXPECTED_POINTS, 500))
    restored = _path_from_waveguide_cell(cell, layout)
    _check_expected_path(restored, 0.5)


def _check_legacy_raw_cell():
    """旧版 helper cell 可读取，读取后删除且不向 1/99 写回。"""
    layout = pya.Layout()
    layout.dbu = DBU
    cell = layout.create_cell("Legacy_Waveguide")
    helper = layout.create_cell(cell.name + RAW_PATH_CELL_SUFFIX)
    helper_name = helper.name
    helper.shapes(layout.layer(WG_LAYER)).insert(pya.Path(EXPECTED_POINTS, 500))
    restored = _path_from_waveguide_cell(cell, layout)
    _check_expected_path(restored, 0.5)
    if layout.cell(helper_name) is not None:
        raise RuntimeError("旧版 raw helper cell 读取后仍未删除。")
    _check_no_embedded_raw_path(cell, layout)


def _check_waveguide_layer_default_visibility():
    """1/99 继续保留且默认隐藏，不要求转换动作改写当前视图状态。"""
    root = ET.parse(str(LAYER_PROPERTIES_FILE)).getroot()
    matches = []
    for node in root.iter("group-members"):
        if node.findtext("source", default="").strip() == "1/99@1":
            matches.append(node.findtext("visible", default="").strip().lower())
    if matches != ["false"]:
        raise RuntimeError("layers.lyp 中 Waveguide (1/99) 未严格设置为默认隐藏。")


def _check_public_library_excludes_internal_pcells():
    """公开 JNULib 只展示可直接放置器件，不包含工具内部波导 PCell。"""
    import JNULib  # noqa: F401  导入入口会注册 JNULib。

    library = pya.Library.library_by_name(JNULIB_NAME)
    if library is None:
        raise RuntimeError("未找到 %s。" % JNULIB_NAME)
    public_names = set(library.layout().pcell_names())
    unexpected = public_names.intersection({"Waveguide", "Composite_Waveguide"})
    if unexpected:
        raise RuntimeError(
            "公开 JNULib 仍包含工具内部 PCell：%s" % ", ".join(sorted(unexpected))
        )


def _check_gui_transaction_pre_registration():
    """在隐藏 GUI 中执行两次完整 Path to Waveguide 转换。"""
    main_window = pya.Application.instance().main_window()
    if main_window is None:
        raise RuntimeError("该检查需要使用 KLayout -z -e 隐藏 GUI 模式运行。")
    cellview = main_window.create_layout(1)
    view = main_window.current_view()
    layout = cellview.layout()
    layout.dbu = DBU
    top = layout.create_cell("JNU_LOCAL_PCELL_TRANSACTION_REGRESSION")
    view.select_cell(top.cell_index(), 0)
    single_params = {
        "mode": "single",
        "width": 0.5,
        "radius": 20.0,
        "bend_type": "Bezier",
        "bezier": 0.35,
        "Euler_Rmax": 30.0,
        "Euler_Rmin": 10.0,
    }
    single_params.update(path_tool._calculate_waveguide_derived(
        20.0, "Bezier", 0.35, 30.0, 10.0, DBU
    ))
    composite_params = {
        "mode": "composite",
        "straight_width": 2.0,
        "start_width": 2.0,
        "end_width": 2.0,
        "bend_width": 0.5,
        "taper_length": 20.0,
        "transition_length": 2.0,
        "radius": 30.0,
        "bend_type": "Bezier",
        "bezier": 0.3,
        "Euler_Rmax": 30.0,
        "Euler_Rmin": 10.0,
    }
    composite_params.update(path_tool._calculate_waveguide_derived(
        30.0, "Bezier", 0.3, 30.0, 10.0, DBU
    ))

    original_dialog = path_tool._show_waveguide_dialog
    original_message = path_tool._message
    messages = []
    try:
        path_tool._message = lambda title, text: messages.append((title, text))
        for y_dbu, params in ((0, single_params), (300000, composite_params)):
            layer_index = layout.layer(SI_LAYER)
            shape = top.shapes(layer_index).insert(pya.Path(
                [
                    pya.Point(0, y_dbu),
                    pya.Point(120000, y_dbu),
                    pya.Point(120000, y_dbu + 120000),
                ],
                500,
            ))
            selected = pya.ObjectInstPath()
            selected.layer = layer_index
            selected.shape = shape
            selected.top = top.cell_index()
            view.object_selection = [selected]
            path_tool._show_waveguide_dialog = lambda _dbu, value=params: dict(value)
            path_tool.path_to_waveguide()
    finally:
        path_tool._show_waveguide_dialog = original_dialog
        path_tool._message = original_message

    if sum(1 for _inst in top.each_inst()) != 2:
        raise RuntimeError("隐藏 GUI 中未完成两类 Path to Waveguide 转换：%s" % messages)
    if any(path_tool._is_waveguide_container_cell(inst.cell) for inst in top.each_inst()):
        raise RuntimeError("Path to Waveguide 不应再创建内部波导容器。")
    if not all(inst.cell.is_pcell_variant() for inst in top.each_inst()):
        raise RuntimeError("Path to Waveguide 未直接插入真实 PCell。")
    if not top.shapes(layout.layer(SI_LAYER)).is_empty():
        raise RuntimeError("Path to Waveguide 完成后仍残留输入 Path。")
    if view.is_transacting():
        raise RuntimeError("Path to Waveguide 完成后仍处于 Undo transaction。")


def main():
    """生成六种 Waveguide PCell，并执行 GDS 重读和旧版兼容检查。"""
    _check_public_library_excludes_internal_pcells()
    _check_gui_transaction_pre_registration()
    _check_waveguide_layer_default_visibility()
    _check_path_extensions()
    layout = pya.Layout()
    layout.dbu = DBU
    top = layout.create_cell("JNU_WAVEGUIDE_DEVREC_REGRESSION")
    records = []
    x_offset = 0
    index = 1
    for bend_type in ("Circular", "Bezier", "Euler"):
        for width_um in (0.5, 2.0):
            dpath = pya.DPath(
                [pya.DPoint(0, 0), pya.DPoint(80, 0), pya.DPoint(80, 80)],
                width_um,
            )
            params = {
                "width": width_um,
                "radius": 20.0,
                "bend_type": bend_type,
                "bezier": 0.35,
                "Euler_Rmax": 30.0,
                "Euler_Rmin": 10.0,
                "npoints": 0,
            }
            cell = _create_waveguide_cell(layout, dpath, params, index)
            _check_pcell_parameters(cell, layout, width_um, bend_type)
            _check_cell_devrec(cell, layout, width_um)
            _check_polygon_layers_and_pin_paths(cell, layout)
            _check_no_embedded_raw_path(cell, layout)
            _check_raw_property(cell, width_um)
            _check_expected_path(_path_from_waveguide_cell(cell, layout), width_um)
            inst = top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans(x_offset, 0)))
            _store_waveguide_recovery_property(inst, dpath)
            records.append((cell.name, width_um))
            x_offset += int(round(120.0 / layout.dbu))
            index += 1

    _check_no_raw_helper_cells(layout)
    output = Path(tempfile.gettempdir()) / "jnu_waveguide_devrec_regression.gds"
    try:
        save_options = pya.SaveLayoutOptions()
        save_options.set_format_from_filename(str(output))
        save_options.gds2_write_cell_properties = True
        save_options.write_context_info = True
        layout.write(str(output), save_options)
        reread = pya.Layout()
        reread.read(str(output))
        top_cells = [cell.name for cell in reread.top_cells()]
        if top_cells != ["JNU_WAVEGUIDE_DEVREC_REGRESSION"]:
            raise RuntimeError("GDS 重读后存在额外顶层 cell：%s" % top_cells)
        reread_top = reread.cell("JNU_WAVEGUIDE_DEVREC_REGRESSION")
        instances_by_cell = {inst.cell.name: inst for inst in reread_top.each_inst()}
        for cell_name, width_um in records:
            cell = reread.cell(cell_name)
            if cell is None:
                raise RuntimeError("GDS 重读后缺少 Waveguide cell：%s" % cell_name)
            _check_cell_devrec(cell, reread, width_um)
            _check_polygon_layers_and_pin_paths(cell, reread)
            _check_no_embedded_raw_path(cell, reread)
            inst = instances_by_cell.get(cell_name)
            if inst is None:
                raise RuntimeError("GDS 重读后缺少 Waveguide 实例：%s" % cell_name)
            _check_raw_property(inst, width_um)
            _check_expected_path(_path_from_waveguide_cell(cell, reread, inst), width_um)
        _check_no_raw_helper_cells(reread)
        _check_unreferenced_cell_cleanup()
        _check_legacy_embedded_path()
        _check_legacy_raw_cell()
        print("OK: local Waveguide variants=%d GDS=%s" % (len(records), output))
    finally:
        try:
            os.remove(str(output))
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
