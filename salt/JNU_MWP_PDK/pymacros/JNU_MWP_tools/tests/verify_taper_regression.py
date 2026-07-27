# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""验证 Taper 两端直波导延伸、端口位置和 GDS 重读。"""

from pathlib import Path
import sys
import tempfile

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

import JNULib  # noqa: E402,F401  注册 JNULib。


LIBRARY_NAME = "JNULib"
SI_LAYER = pya.LayerInfo(1, 0)
PIN_LAYER = pya.LayerInfo(1, 10)
DEVREC_LAYER = pya.LayerInfo(68, 0)
DBU = 0.001


def _create(layout, params=None):
    cell = layout.create_cell("Taper", LIBRARY_NAME, params or {})
    if cell is None:
        raise RuntimeError("无法创建 Taper PCell。")
    return cell


def _assert_si_polygon(cell, layout):
    shapes = list(cell.shapes(layout.layer(SI_LAYER)).each())
    if len(shapes) != 1:
        raise RuntimeError("Taper Si 层应只包含一个连续 Polygon。")
    shape = shapes[0]
    if shape.is_path() or not (shape.is_polygon() or shape.is_simple_polygon()):
        raise RuntimeError("Taper Si 实体不是 Polygon。")


def _pin_records(cell, layout):
    records = []
    for shape in cell.shapes(layout.layer(PIN_LAYER)).each():
        if not shape.is_path():
            continue
        points = list(shape.path.each_point())
        if len(points) != 2 or points[0].y != points[1].y:
            raise RuntimeError("Taper PinRec 不是水平短 Path。")
        records.append(
            (
                (points[0].x + points[1].x) // 2,
                shape.path.width,
                1 if points[1].x > points[0].x else -1,
            )
        )
    return sorted(records)


def _section_height(cell, layout, x_dbu):
    region = pya.Region(cell.begin_shapes_rec(layout.layer(SI_LAYER)))
    probe = pya.Region(pya.Box(x_dbu, -10000, x_dbu + 1, 10000))
    bbox = (region & probe).bbox()
    if bbox.empty():
        raise RuntimeError("Taper 截面探针未命中 Si。")
    return bbox.height()


def _check_default_compatibility(layout):
    cell = _create(layout)
    params = cell.pcell_parameters_by_name()
    if float(params.get("port1_extension_length")) != 0.0:
        raise RuntimeError("Port 1 默认延伸长度不是 0 µm。")
    if float(params.get("port2_extension_length")) != 0.0:
        raise RuntimeError("Port 2 默认延伸长度不是 0 µm。")
    _assert_si_polygon(cell, layout)
    if cell.bbox(layout.layer(SI_LAYER)) != pya.Box(0, -1500, 50000, 1500):
        raise RuntimeError("零延伸默认 Taper 几何不再兼容旧版。")
    if _pin_records(cell, layout) != [(0, 500, -1), (50000, 3000, 1)]:
        raise RuntimeError("零延伸默认 Taper 端口位置或方向错误。")
    return cell


def _check_extended_geometry(layout):
    cell = _create(
        layout,
        {
            "width1": 0.5,
            "width2": 3.0,
            "length": 50.0,
            "port1_extension_length": 10.0,
            "port2_extension_length": 20.0,
        },
    )
    _assert_si_polygon(cell, layout)
    si_bbox = cell.bbox(layout.layer(SI_LAYER))
    if si_bbox != pya.Box(0, -1500, 80000, 1500):
        raise RuntimeError("非零延伸 Taper 的总长度或宽度错误：%s。" % si_bbox)
    if _section_height(cell, layout, 5000) != 500:
        raise RuntimeError("Port 1 延伸直段宽度错误。")
    if _section_height(cell, layout, 70000) != 3000:
        raise RuntimeError("Port 2 延伸直段宽度错误。")
    if _pin_records(cell, layout) != [(0, 500, -1), (80000, 3000, 1)]:
        raise RuntimeError("非零延伸 Taper 的端口未移动到外侧端面。")
    devrec_bbox = cell.bbox(layout.layer(DEVREC_LAYER))
    if devrec_bbox != pya.Box(0, -1500, 80000, 1500):
        raise RuntimeError("Taper DevRec 未覆盖完整三段结构。")
    return cell


def _check_negative_extension_coercion(layout):
    cell = _create(
        layout,
        {
            "port1_extension_length": -10.0,
            "port2_extension_length": -20.0,
        },
    )
    if cell.bbox(layout.layer(SI_LAYER)) != pya.Box(0, -1500, 50000, 1500):
        raise RuntimeError("负延伸长度仍改变了 Taper 实际几何。")
    if _pin_records(cell, layout) != [(0, 500, -1), (50000, 3000, 1)]:
        raise RuntimeError("负延伸长度仍改变了 Taper 端口位置。")


def main():
    layout = pya.Layout()
    layout.dbu = DBU
    top = layout.create_cell("JNU_TAPER_REGRESSION")
    default_cell = _check_default_compatibility(layout)
    extended_cell = _check_extended_geometry(layout)
    _check_negative_extension_coercion(layout)
    top.insert(pya.CellInstArray(default_cell.cell_index(), pya.Trans()))
    top.insert(pya.CellInstArray(extended_cell.cell_index(), pya.Trans(100000, 0)))

    with tempfile.TemporaryDirectory(prefix="jnu_taper_") as temp_dir:
        output = str(Path(temp_dir) / "taper_regression.gds")
        layout.write(output)
        reread = pya.Layout()
        reread.read(output)
        if [cell.name for cell in reread.top_cells()] != ["JNU_TAPER_REGRESSION"]:
            raise RuntimeError("Taper GDS 重读后出现额外顶层 cell。")
        for source_cell in (default_cell, extended_cell):
            cell = reread.cell(source_cell.name)
            if cell is None:
                raise RuntimeError("Taper GDS 重读后缺少 cell：%s。" % source_cell.name)
            _assert_si_polygon(cell, reread)
            if len(_pin_records(cell, reread)) != 2:
                raise RuntimeError("Taper GDS 重读后 PinRec 丢失。")

    print("Taper regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
