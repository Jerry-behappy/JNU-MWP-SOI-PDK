# -*- coding: utf-8 -*-
"""验证复合宽度Waveguide、半径降级和Path往返。"""

import os
from pathlib import Path
import sys
import tempfile

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
TOOLS_DIR = PYMACROS_DIR / "JNU_MWP_tools"
for path in (PYMACROS_DIR, TOOLS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from JNU_MWP_tools.core.bend_curvature import euler_Reff  # noqa: E402
from JNU_MWP_tools.actions.path_to_waveguide import (  # noqa: E402
    _analyze_path_capacity,
    _create_waveguide_cell,
    _normalize_width_role,
    _params_with_effective_radius,
    _store_waveguide_recovery_property,
)
from JNU_MWP_tools.actions.sbend_connect import (  # noqa: E402
    DEFAULT_SBEND_CONNECT_BEZIER,
    DEFAULT_SBEND_CONNECT_RADIUS,
)
from JNU_MWP_tools.actions.waveguide_to_path import _path_from_waveguide_cell  # noqa: E402


DBU = 0.001
SI = pya.LayerInfo(1, 0)
WG = pya.LayerInfo(1, 99)
PIN = pya.LayerInfo(1, 10)
DEVREC = pya.LayerInfo(68, 0)


def _section_height(cell, layer, x, y, half_span=10000):
    region = pya.Region(cell.begin_shapes_rec(layer))
    probe = pya.Region(pya.Box(x, y - half_span, x + 1, y + half_span))
    bbox = (region & probe).bbox()
    if bbox.empty():
        raise RuntimeError("截面探针未命中图形。")
    return bbox.height()


def _section_width(cell, layer, x, y, half_span=10000):
    region = pya.Region(cell.begin_shapes_rec(layer))
    probe = pya.Region(pya.Box(x - half_span, y, x + half_span, y + 1))
    bbox = (region & probe).bbox()
    if bbox.empty():
        raise RuntimeError("截面探针未命中图形。")
    return bbox.width()


def _assert_equal(actual, expected, message, tolerance=1):
    if abs(actual - expected) > tolerance:
        raise RuntimeError("%s：期望 %s，实际 %s。" % (message, expected, actual))


def _base_params(bend_type="Bezier"):
    return {
        "mode": "composite",
        "straight_width": 2.0,
        "start_width": 2.0,
        "end_width": 2.0,
        "bend_width": 0.5,
        "taper_length": 20.0,
        "transition_length": 2.0,
        "radius": 30.0,
        "bend_type": bend_type,
        "bezier": 0.3,
        "Euler_Rmax": 45.0,
        "Euler_Rmin": 15.0,
        "npoints": 0,
    }


def _check_capacity_helpers():
    reducible = pya.Path(
        [pya.Point(0, 0), pya.Point(40000, 0), pya.Point(40000, 100000)], 2000
    )
    analysis = _analyze_path_capacity(reducible, 30.0, 20.0, DBU, 1)
    _assert_equal(analysis["actual_radius_um"], 20.0, "单拐角可行半径", 1e-12)
    if not analysis["possible"] or analysis["issues"][0]["segment_number"] != 1:
        raise RuntimeError("半径不足线段识别错误。")

    impossible = pya.Path(
        [pya.Point(0, 0), pya.Point(15000, 0), pya.Point(15000, 50000)], 2000
    )
    if _analyze_path_capacity(impossible, 30.0, 20.0, DBU, 2)["possible"]:
        raise RuntimeError("固定taper已占满直段时仍被判定为可生成。")

    endpoint_taper = pya.Path(
        [pya.Point(0, 0), pya.Point(30000, 0)], 2000
    )
    if _analyze_path_capacity(endpoint_taper, 30.0, 0.0, DBU, 3, 20.0, 20.0)["possible"]:
        raise RuntimeError("首末端taper无法容纳时仍被判定为可生成。")
    single_endpoint_taper = pya.Path(
        [pya.Point(0, 0), pya.Point(15000, 0)], 2000
    )
    if _analyze_path_capacity(single_endpoint_taper, 30.0, 0.0, DBU, 4, 20.0, 0.0)["possible"]:
        raise RuntimeError("纯直Path单端taper无法容纳时仍被判定为可生成。")
    terminal_bend = pya.Path(
        [pya.Point(0, 0), pya.Point(35000, 0), pya.Point(35000, 100000)], 2000
    )
    analysis = _analyze_path_capacity(
        terminal_bend, 40.0, 24.0, DBU, 5, 0.0, 0.0, 0.0, 24.0
    )
    _assert_equal(analysis["actual_radius_um"], 35.0, "起始端弯宽时首段可行半径", 1e-12)

    euler = _base_params("Euler")
    requested = euler_Reff(euler["Euler_Rmax"], euler["Euler_Rmin"])
    adjusted = _params_with_effective_radius(euler, requested * 0.5, DBU)
    _assert_equal(
        euler_Reff(adjusted["Euler_Rmax"], adjusted["Euler_Rmin"]),
        requested * 0.5,
        "Euler Reff比例缩放",
        1e-9,
    )
    if _normalize_width_role(None, 0.55, 2.0, 0.5) != "bend":
        raise RuntimeError("旧数值宽度未迁移为bend角色。")
    if _normalize_width_role(None, 1.8, 2.0, 0.5) != "straight":
        raise RuntimeError("旧数值宽度未迁移为straight角色。")


def _check_bend_variants_and_equal_width():
    """三种弯曲均可生成；等宽模式不得产生宽度变化。"""
    for bend_type in ("Circular", "Bezier", "Euler"):
        layout = pya.Layout()
        layout.dbu = DBU
        dpath = pya.DPath(
            [pya.DPoint(0, 0), pya.DPoint(120, 0), pya.DPoint(120, 120)], 2.0
        )
        params = _base_params(bend_type)
        if bend_type == "Euler":
            params = _params_with_effective_radius(params, 30.0, DBU)
        cell = _create_waveguide_cell(layout, dpath, params, 1)
        if cell is None or cell.bbox().empty():
            raise RuntimeError("%s Composite_Waveguide生成失败。" % bend_type)
        if not cell.shapes(layout.layer(WG)).is_empty():
            raise RuntimeError("%s Composite_Waveguide写入了1/99。" % bend_type)

    layout = pya.Layout()
    layout.dbu = DBU
    params = _base_params("Circular")
    params["bend_width"] = params["straight_width"]
    dpath = pya.DPath([pya.DPoint(0, 0), pya.DPoint(100, 0)], 2.0)
    cell = _create_waveguide_cell(layout, dpath, params, 1)
    _assert_equal(
        _section_height(cell, layout.layer(SI), 50000, 0), 2000,
        "等宽复合波导截面",
    )

    layout = pya.Layout()
    layout.dbu = DBU
    multi = pya.DPath(
        [
            pya.DPoint(0, 0), pya.DPoint(120, 0),
            pya.DPoint(120, 120), pya.DPoint(240, 120),
        ],
        2.0,
    )
    cell = _create_waveguide_cell(layout, multi, _base_params("Bezier"), 1)
    region = pya.Region(cell.begin_shapes_rec(layout.layer(SI))).merged()
    if region.count() != 1:
        raise RuntimeError("多拐角复合波导Si几何不连通。")


def _check_terminal_width_geometry():
    """起始端和终端宽度应真实写入Si、DevRec和PinRec。"""
    layout = pya.Layout()
    layout.dbu = DBU
    params = _base_params("Circular")
    params["start_width"] = 1.0
    params["end_width"] = 3.0
    params["bend_width"] = 2.0
    dpath = pya.DPath([pya.DPoint(0, 0), pya.DPoint(100, 0)], 2.0)
    cell = _create_waveguide_cell(layout, dpath, params, 1)
    si_layer = layout.layer(SI)
    devrec_layer = layout.layer(DEVREC)
    _assert_equal(_section_height(cell, si_layer, 0, 0), 1000, "起始端Si宽度")
    _assert_equal(_section_height(cell, si_layer, 10000, 0), 1500, "起始端taper中点宽度", 2)
    _assert_equal(_section_height(cell, si_layer, 50000, 0), 2000, "中间直段Si宽度")
    _assert_equal(_section_height(cell, si_layer, 90000, 0), 2500, "终端taper中点宽度", 2)
    _assert_equal(_section_height(cell, si_layer, 99999, 0), 3000, "终端Si宽度")
    _assert_equal(_section_height(cell, devrec_layer, 0, 0), 3000, "起始端DevRec宽度")
    _assert_equal(_section_height(cell, devrec_layer, 99999, 0), 5000, "终端DevRec宽度")
    pins = [shape.path for shape in cell.shapes(layout.layer(PIN)).each() if shape.is_path()]
    widths = sorted(path.width for path in pins)
    if widths != [1000, 3000]:
        raise RuntimeError("起始端/终端PinRec宽度错误：%s。" % widths)
    restored = _path_from_waveguide_cell(cell, layout)
    if restored is None or restored.width != 2000:
        raise RuntimeError("端部变宽复合波导反向Path应恢复为直波导宽度。")


def _check_terminal_bend_role_geometry():
    """端部选择弯宽时，端部到相邻弯曲的直段保持弯宽。"""
    layout = pya.Layout()
    layout.dbu = DBU
    params = _base_params("Circular")
    params["start_width"] = params["bend_width"]
    params["end_width"] = params["bend_width"]
    dpath = pya.DPath(
        [pya.DPoint(0, 0), pya.DPoint(100, 0), pya.DPoint(100, 100)], 2.0
    )
    cell = _create_waveguide_cell(layout, dpath, params, 1)
    si_layer = layout.layer(SI)
    _assert_equal(_section_height(cell, si_layer, 10000, 0), 500, "起始端到第一个弯曲入口宽度")
    _assert_equal(_section_height(cell, si_layer, 60000, 0), 500, "第一个弯曲入口前宽度")
    _assert_equal(_section_width(cell, si_layer, 100000, 40000), 500, "最后一个弯曲出口后宽度")
    _assert_equal(_section_width(cell, si_layer, 100000, 90000), 500, "最后一个弯曲到终端宽度")
    pins = [shape.path for shape in cell.shapes(layout.layer(PIN)).each() if shape.is_path()]
    if sorted(path.width for path in pins) != [500, 500]:
        raise RuntimeError("端部弯宽角色的PinRec宽度错误。")

    straight = pya.DPath([pya.DPoint(0, 0), pya.DPoint(100, 0)], 2.0)
    both_bend = _base_params("Circular")
    both_bend["start_width"] = both_bend["bend_width"]
    both_bend["end_width"] = both_bend["bend_width"]
    straight_cell = _create_waveguide_cell(layout, straight, both_bend, 2)
    _assert_equal(_section_height(straight_cell, si_layer, 50000, 0), 500, "纯直Path两端弯宽时整段宽度")

    one_side = _base_params("Circular")
    one_side["start_width"] = one_side["bend_width"]
    one_side["end_width"] = one_side["straight_width"]
    one_side_cell = _create_waveguide_cell(layout, straight, one_side, 3)
    _assert_equal(_section_height(one_side_cell, si_layer, 0, 0), 500, "纯直Path起始弯宽")
    _assert_equal(_section_height(one_side_cell, si_layer, 10000, 0), 1250, "纯直Path异宽taper中点", 2)
    _assert_equal(_section_height(one_side_cell, si_layer, 50000, 0), 2000, "纯直Path异宽后直段")


def _check_geometry_and_roundtrip():
    layout = pya.Layout()
    layout.dbu = DBU
    top = layout.create_cell("COMPOSITE_WAVEGUIDE_REGRESSION")
    dpath = pya.DPath(
        [pya.DPoint(0, 0), pya.DPoint(100, 0), pya.DPoint(100, 100)], 2.0
    )
    params = _base_params()
    cell = _create_waveguide_cell(layout, dpath, params, 1)
    if cell is None or not cell.is_pcell_variant():
        raise RuntimeError("未创建Composite_Waveguide PCell variant。")
    if cell.pcell_declaration().name() != "Composite_Waveguide":
        raise RuntimeError("PCell声明名称错误。")
    if cell.pcell_library() is not None:
        raise RuntimeError("Composite_Waveguide不应来自公开Library。")
    pcell_params = cell.pcell_parameters_by_name()
    for key, value in (
        ("straight_width", 2.0),
        ("start_width", 2.0),
        ("end_width", 2.0),
        ("bend_width", 0.5),
        ("taper_length", 20.0),
        ("transition_length", 2.0),
        ("radius", 30.0),
        ("bezier_k", 0.3),
    ):
        _assert_equal(float(pcell_params[key]), value, "PCell参数%s" % key, 1e-12)

    si_layer = layout.layer(SI)
    devrec_layer = layout.layer(DEVREC)
    _assert_equal(_section_height(cell, si_layer, 20000, 0), 2000, "直段宽度")
    _assert_equal(_section_height(cell, si_layer, 47000, 0), 2000, "taper前直宽transition宽度")
    _assert_equal(_section_height(cell, si_layer, 58000, 0), 1250, "taper中点宽度", 2)
    _assert_equal(_section_height(cell, si_layer, 69000, 0), 500, "taper后弯宽transition宽度", 2)
    _assert_equal(_section_height(cell, si_layer, 70000, 0), 500, "弯曲切点宽度", 2)
    _assert_equal(_section_height(cell, devrec_layer, 20000, 0), 4000, "直段DevRec宽度")
    _assert_equal(_section_height(cell, devrec_layer, 58000, 0), 3250, "taper DevRec宽度", 2)
    _assert_equal(_section_height(cell, devrec_layer, 70000, 0), 2500, "弯曲DevRec宽度", 2)

    if not cell.shapes(layout.layer(WG)).is_empty():
        raise RuntimeError("Composite_Waveguide不应向1/99写入Path。")
    pins = [shape.path for shape in cell.shapes(layout.layer(PIN)).each() if shape.is_path()]
    if len(pins) != 2 or any(path.width != 2000 for path in pins):
        raise RuntimeError("复合波导端口宽度不是直波导宽度。")
    restored = _path_from_waveguide_cell(cell, layout)
    if restored is None or restored.width != 2000:
        raise RuntimeError("当前会话未从Composite PCell参数恢复2um Path。")

    inst = top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans()))
    _store_waveguide_recovery_property(inst, dpath)
    output = Path(tempfile.gettempdir()) / "jnu_composite_waveguide_regression.gds"
    try:
        options = pya.SaveLayoutOptions()
        options.set_format_from_filename(str(output))
        options.gds2_write_cell_properties = True
        layout.write(str(output), options)
        reread = pya.Layout()
        reread.read(str(output))
        if [item.name for item in reread.top_cells()] != ["COMPOSITE_WAVEGUIDE_REGRESSION"]:
            raise RuntimeError("GDS重读后出现额外顶层cell。")
        reread_top = reread.cell("COMPOSITE_WAVEGUIDE_REGRESSION")
        reread_inst = next(iter(reread_top.each_inst()))
        reread_cell = reread_inst.cell
        if not reread_cell.shapes(reread.layer(WG)).is_empty():
            raise RuntimeError("GDS重读后1/99不为空。")
        restored = _path_from_waveguide_cell(reread_cell, reread, reread_inst)
        if restored is None or restored.width != 2000:
            raise RuntimeError("GDS重读后未从实例属性恢复2um Path。")
    finally:
        try:
            os.remove(str(output))
        except OSError:
            pass


def main():
    _assert_equal(DEFAULT_SBEND_CONNECT_BEZIER, 0.3, "SBend connect默认B", 1e-12)
    _assert_equal(DEFAULT_SBEND_CONNECT_RADIUS, 30.0, "SBend connect默认R", 1e-12)
    _check_capacity_helpers()
    _check_bend_variants_and_equal_width()
    _check_terminal_width_geometry()
    _check_terminal_bend_role_geometry()
    _check_geometry_and_roundtrip()
    print("Composite Waveguide regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
