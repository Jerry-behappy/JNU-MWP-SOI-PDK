# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""批量生成 Bend/Waveguide/Paperclip，并通过 GDS 重读检查基本几何。"""

import os
from pathlib import Path
import sys
import tempfile

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

import JNULib  # noqa: F401,E402  注册 JNULib。
from JNU_MWP_tools.actions.path_to_waveguide import _create_waveguide_cell  # noqa: E402


LIBRARY_NAME = "JNULib"
SI_LAYER = pya.LayerInfo(1, 0)
PIN_LAYER = pya.LayerInfo(1, 10)
DEVREC_LAYER = pya.LayerInfo(68, 0)


def _count_recursive(cell, layer_index):
    count = 0
    iterator = cell.begin_shapes_rec(layer_index)
    while not iterator.at_end():
        count += 1
        iterator.next()
    return count


def _create_variant(layout, name, params, x_offset):
    cell = layout.create_cell(name, LIBRARY_NAME, params)
    if cell is None:
        raise RuntimeError("无法创建 PCell：%s" % name)
    return cell, pya.CellInstArray(cell.cell_index(), pya.Trans(x_offset, 0))


def _create_waveguide_variant(layout, params, x_offset):
    """用当前版图中的内部 Waveguide PCell 创建回归实例。"""
    dpath = pya.DPath(
        [pya.DPoint(0, 0), pya.DPoint(80, 0), pya.DPoint(80, 80)],
        0.5,
    )
    waveguide_params = dict(params)
    waveguide_params["width"] = 0.5
    cell = _create_waveguide_cell(layout, dpath, waveguide_params, 1)
    return cell, pya.CellInstArray(cell.cell_index(), pya.Trans(x_offset, 0))


def _assert_polygon_only(cell, layout, layer_info, label):
    """目标实体层必须存在且只包含 Polygon。"""

    shapes = list(cell.shapes(layout.layer(layer_info)).each())
    if not shapes:
        raise RuntimeError("%s 的 %s 层为空。" % (cell.name, label))
    if any(shape.is_path() for shape in shapes):
        raise RuntimeError("%s 的 %s 层仍包含 Path。" % (cell.name, label))
    if any(not (shape.is_polygon() or shape.is_simple_polygon()) for shape in shapes):
        raise RuntimeError("%s 的 %s 层包含非 Polygon 实体。" % (cell.name, label))


def _assert_pin_paths(cell, layout):
    """两个 PinRec 仍必须使用有方向的短 Path。"""

    paths = [
        shape.path
        for shape in cell.shapes(layout.layer(PIN_LAYER)).each()
        if shape.is_path()
    ]
    if len(paths) != 2:
        raise RuntimeError("%s 的 PinRec Path 数量不是 2。" % cell.name)


def _assert_connected_waveguide(cell, layout):
    """全部 Polygon 合并后必须仍是一条连续波导。"""

    region = pya.Region(cell.begin_shapes_rec(layout.layer(SI_LAYER)))
    region.merge()
    if sum(1 for _polygon in region.each()) != 1:
        raise RuntimeError("%s 的 Polygon 分段之间存在断接。" % cell.name)


def main():
    layout = pya.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("JNU_BEND_REGRESSION")
    offset = 0
    records = []
    for bend_type in ("Circular", "Bezier", "Euler"):
        common = {
            "bend_type": bend_type,
            "radius": 20.0,
            "bezier_k": 0.35,
            "bezier": 0.35,
            "Euler_Rmax": 30.0,
            "Euler_Rmin": 10.0,
        }
        bend_cell, bend_inst = _create_variant(layout, "Bend_90deg", common, offset)
        _assert_polygon_only(bend_cell, layout, SI_LAYER, "Si")
        _assert_polygon_only(bend_cell, layout, DEVREC_LAYER, "DevRec")
        _assert_pin_paths(bend_cell, layout)
        records.append((bend_cell.name, True))
        top.insert(bend_inst)
        offset += 120000
        waveguide_cell, waveguide_inst = _create_waveguide_variant(layout, common, offset)
        _assert_polygon_only(waveguide_cell, layout, SI_LAYER, "Si")
        _assert_polygon_only(waveguide_cell, layout, DEVREC_LAYER, "DevRec")
        _assert_pin_paths(waveguide_cell, layout)
        records.append((waveguide_cell.name, True))
        top.insert(waveguide_inst)
        offset += 180000
        paperclip = dict(common)
        paperclip.update({"length": 100.0, "loops": 2, "ports_type": "type3"})
        paperclip_cell, paperclip_inst = _create_variant(
            layout, "Paperclip_Spiral", paperclip, offset
        )
        _assert_polygon_only(paperclip_cell, layout, SI_LAYER, "Si")
        _assert_pin_paths(paperclip_cell, layout)
        _assert_connected_waveguide(paperclip_cell, layout)
        records.append((paperclip_cell.name, False))
        top.insert(paperclip_inst)
        offset += 500000
        composite = dict(paperclip)
        composite.update({"straight_width": 0.5, "bend_width": 1.0, "taper_length": 20.0})
        composite_cell, composite_inst = _create_variant(
            layout,
            "Paperclip_Spiral_with_Composite_Waveguide",
            composite,
            offset,
        )
        _assert_polygon_only(composite_cell, layout, SI_LAYER, "Si")
        _assert_pin_paths(composite_cell, layout)
        _assert_connected_waveguide(composite_cell, layout)
        records.append((composite_cell.name, False))
        top.insert(composite_inst)
        offset += 500000

    # 长 Paperclip 必须触发安全分段；每个分段均为 Polygon 且合并后无缝。
    long_params = {
        "bend_type": "Bezier",
        "bend_radius": 20.0,
        "bezier": 0.35,
        "length": 200.0,
        "loops": 16,
        "ports_type": "type3",
    }
    long_cell, long_inst = _create_variant(
        layout,
        "Paperclip_Spiral",
        long_params,
        offset,
    )
    _assert_polygon_only(long_cell, layout, SI_LAYER, "Si")
    _assert_pin_paths(long_cell, layout)
    if len(list(long_cell.shapes(layout.layer(SI_LAYER)).each())) < 2:
        raise RuntimeError("长 Paperclip 未覆盖 Polygon 安全分段路径。")
    _assert_connected_waveguide(long_cell, layout)
    records.append((long_cell.name, False))
    top.insert(long_inst)

    output = Path(tempfile.gettempdir()) / "jnu_bend_regression.gds"
    layout.write(str(output))

    reread = pya.Layout()
    reread.read(str(output))
    reread_top = reread.cell("JNU_BEND_REGRESSION")
    if reread_top is None:
        raise RuntimeError("GDS 重读后缺少顶层 cell。")
    si_count = _count_recursive(reread_top, reread.layer(SI_LAYER))
    pin_count = _count_recursive(reread_top, reread.layer(PIN_LAYER))
    if si_count < 12:
        raise RuntimeError("Si 图形数量不足：%d" % si_count)
    if pin_count < 24:
        raise RuntimeError("PinRec 图形数量不足：%d" % pin_count)
    for cell_name, check_devrec in records:
        cell = reread.cell(cell_name)
        if cell is None:
            raise RuntimeError("GDS 重读后缺少目标 cell：%s" % cell_name)
        _assert_polygon_only(cell, reread, SI_LAYER, "Si")
        _assert_connected_waveguide(cell, reread)
        if check_devrec:
            _assert_polygon_only(cell, reread, DEVREC_LAYER, "DevRec")
        _assert_pin_paths(cell, reread)
    print("OK: GDS=%s Si=%d PinRec=%d" % (output, si_count, pin_count))
    try:
        os.remove(str(output))
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
