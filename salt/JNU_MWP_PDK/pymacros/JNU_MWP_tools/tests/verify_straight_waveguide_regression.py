# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""验证公开 Straight_Waveguide 的几何、端口、DevRec 和 GDS 往返。"""

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
TEXT_LAYER = pya.LayerInfo(10, 0)
DBU = 0.001


def _assert(condition, message):
    if not condition:
        raise RuntimeError(message)


def _direct_shapes(cell, layer_index):
    return list(cell.shapes(layer_index).each())


def _recursive_region(cell, layer_index):
    region = pya.Region()
    iterator = cell.begin_shapes_rec(layer_index)
    while not iterator.at_end():
        shape = iterator.shape()
        transform = iterator.trans()
        if shape.is_box():
            region.insert(shape.box.transformed(transform))
        elif shape.is_path():
            region.insert(shape.path.polygon().transformed(transform))
        elif shape.is_polygon():
            region.insert(shape.polygon.transformed(transform))
        elif shape.is_simple_polygon():
            region.insert(shape.simple_polygon.transformed(transform))
        iterator.next()
    return region.merged()


def _pin_paths(cell, pin_layer_index):
    paths = []
    for shape in _direct_shapes(cell, pin_layer_index):
        if shape.is_path():
            paths.append(shape.path)
    return sorted(paths, key=lambda path: path.bbox().center().x)


def main():
    library = pya.Library.library_by_name(LIBRARY_NAME)
    _assert(library is not None, "未找到 %s。" % LIBRARY_NAME)
    public_names = tuple(sorted(library.layout().pcell_names()))
    _assert("Straight_Waveguide" in public_names, "公开库缺少 Straight_Waveguide。")
    _assert("Waveguide" not in public_names, "内部 Waveguide 被错误公开。")
    _assert("Composite_Waveguide" not in public_names, "内部 Composite_Waveguide 被错误公开。")

    declaration = library.layout().pcell_declaration("Straight_Waveguide")
    defaults = {parameter.name: parameter.default for parameter in declaration.get_parameters()}
    _assert(abs(float(defaults["width"]) - 0.5) < 1e-12, "默认宽度不是 0.5 um。")
    _assert(abs(float(defaults["length"]) - 50.0) < 1e-12, "默认长度不是 50 um。")

    layout = pya.Layout()
    layout.dbu = DBU
    cell = layout.create_cell(
        "Straight_Waveguide",
        LIBRARY_NAME,
        {"width": 0.75, "length": 12.345},
    )
    _assert(cell is not None, "无法创建 Straight_Waveguide 变体。")

    si_index = layout.layer(SI_LAYER)
    pin_index = layout.layer(PIN_LAYER)
    devrec_index = layout.layer(DEVREC_LAYER)
    text_index = layout.layer(TEXT_LAYER)

    si_shapes = _direct_shapes(cell, si_index)
    _assert(len(si_shapes) == 1 and si_shapes[0].is_box(), "Si 不是单一矩形。")
    _assert(si_shapes[0].box == pya.Box(0, -375, 12345, 375), "Si 尺寸或 DBU 量化错误。")

    pins = _pin_paths(cell, pin_index)
    _assert(len(pins) == 2, "PinRec Path 数量不是 2。")
    left_points = list(pins[0].each_point())
    right_points = list(pins[1].each_point())
    _assert(left_points == [pya.Point(10, 0), pya.Point(-10, 0)], "opt1 不是 180°。")
    _assert(right_points == [pya.Point(12335, 0), pya.Point(12355, 0)], "opt2 不是 0°。")
    _assert(pins[0].width == 750 and pins[1].width == 750, "PinRec 宽度不等于波导宽度。")

    devrec_shapes = _direct_shapes(cell, devrec_index)
    _assert(len(devrec_shapes) == 1 and devrec_shapes[0].is_box(), "DevRec 不是单一矩形。")
    _assert(
        devrec_shapes[0].box == pya.Box(0, -1375, 12345, 1375),
        "DevRec 未在非端口侧保留 1 um 净空。",
    )
    _assert(
        len([shape for shape in _direct_shapes(cell, text_index) if shape.is_text()]) == 1,
        "Text 10/0 标识数量错误。",
    )

    top = layout.create_cell("STRAIGHT_WAVEGUIDE_REGRESSION")
    top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans()))
    with tempfile.TemporaryDirectory(prefix="jnu_straight_waveguide_") as temp_dir:
        gds_path = str(Path(temp_dir) / "straight_waveguide.gds")
        layout.write(gds_path)
        reread = pya.Layout()
        reread.read(gds_path)
        reread_top = reread.cell("STRAIGHT_WAVEGUIDE_REGRESSION")
        _assert(reread_top is not None, "GDS 重读后缺少顶层 Cell。")
        _assert(
            _recursive_region(reread_top, reread.layer(SI_LAYER)).bbox()
            == pya.Box(0, -375, 12345, 375),
            "GDS 重读后 Si 几何变化。",
        )
        _assert(
            _recursive_region(reread_top, reread.layer(DEVREC_LAYER)).bbox()
            == pya.Box(0, -1375, 12345, 1375),
            "GDS 重读后 DevRec 变化。",
        )

    print("OK: Straight_Waveguide geometry, pins, DevRec and GDS round-trip passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
