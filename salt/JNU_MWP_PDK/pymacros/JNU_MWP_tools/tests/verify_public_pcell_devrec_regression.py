# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""验证全部公开 JNU PCell 均具有可重读的 DevRec 器件识别层。"""

from pathlib import Path
import sys
import tempfile

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

import JNULib  # noqa: E402,F401  注册 JNULib。
from JNU_MWP_tools.core.devrec import (  # noqa: E402
    _pin_sides,
    calculate_device_devrec_box,
)


LIBRARY_NAME = "JNULib"
SI_LAYER = pya.LayerInfo(1, 0)
PIN_LAYER = pya.LayerInfo(1, 10)
DEVREC_LAYER = pya.LayerInfo(68, 0)
DBU = 0.001
NEW_DEVREC_PCELLS = (
    "Microring_DoubleBus",
    "Archimedean_Spiral",
    "Paperclip_Spiral",
    "Paperclip_Spiral_with_Composite_Waveguide",
)


def _direct_shapes(cell, layer_index):
    return list(cell.shapes(layer_index).each())


def _shape_region(shape):
    if shape.is_box():
        return pya.Region(shape.box)
    if shape.is_path():
        return pya.Region(shape.path.polygon())
    if shape.is_polygon():
        return pya.Region(shape.polygon)
    if shape.is_simple_polygon():
        return pya.Region(shape.simple_polygon)
    return pya.Region()


def _layer_region(cell, layer_index):
    region = pya.Region()
    for shape in _direct_shapes(cell, layer_index):
        region += _shape_region(shape)
    return region.merged()


def _assert_new_devrec(cell, layout, pcell_name, variant_label):
    si_index = layout.layer(SI_LAYER)
    pin_index = layout.layer(PIN_LAYER)
    devrec_index = layout.layer(DEVREC_LAYER)
    shapes = _direct_shapes(cell, devrec_index)
    if len(shapes) != 1 or not shapes[0].is_box():
        raise RuntimeError(
            "%s/%s 应只包含一个矩形 DevRec，实际图形数为 %d。"
            % (pcell_name, variant_label, len(shapes))
        )

    si_bbox = cell.bbox(si_index)
    expected = calculate_device_devrec_box(
        si_bbox,
        _pin_sides(cell, pin_index),
        int(round(1.0 / layout.dbu)),
    )
    actual = shapes[0].box
    if actual != expected:
        raise RuntimeError(
            "%s/%s DevRec 不符合端口边/1 um 非端口边规则：%s != %s。"
            % (pcell_name, variant_label, actual, expected)
        )

    outside = _layer_region(cell, si_index) - pya.Region(actual)
    if not outside.is_empty():
        raise RuntimeError("%s/%s 存在位于 DevRec 外的 Si。" % (pcell_name, variant_label))


def _create(layout, pcell_name, params=None):
    cell = layout.create_cell(pcell_name, LIBRARY_NAME, params or {})
    if cell is None:
        raise RuntimeError("无法创建公开 PCell：%s。" % pcell_name)
    return cell


def _recursive_shape_count(cell, layer_index):
    count = 0
    iterator = cell.begin_shapes_rec(layer_index)
    while not iterator.at_end():
        shape = iterator.shape()
        if shape.is_box() or shape.is_path() or shape.is_polygon() or shape.is_simple_polygon():
            count += 1
        iterator.next()
    return count


def main():
    layout = pya.Layout()
    layout.dbu = DBU
    library = pya.Library.library_by_name(LIBRARY_NAME)
    if library is None:
        raise RuntimeError("未找到 %s。" % LIBRARY_NAME)

    public_names = sorted(library.layout().pcell_names())
    expected_public = sorted(
        (
            "Bend_90deg",
            "Microring_DoubleBus",
            "Archimedean_Spiral",
            "Paperclip_Spiral",
            "Paperclip_Spiral_with_Composite_Waveguide",
            "Taper",
            "S_Bend",
            "Straight_Waveguide",
        )
    )
    if public_names != expected_public:
        raise RuntimeError("公开 PCell 列表发生变化：%s。" % public_names)

    devrec_index = layout.layer(DEVREC_LAYER)
    top = layout.create_cell("JNU_PUBLIC_PCELL_DEVREC_REGRESSION")
    x_offset = 0
    created = []

    for pcell_name in public_names:
        cell = _create(layout, pcell_name)
        if cell.bbox(devrec_index).empty():
            raise RuntimeError("%s 默认变体缺少 DevRec。" % pcell_name)
        top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans(x_offset, 0)))
        x_offset += max(100000, cell.bbox().width() + 10000)
        created.append(cell)

    microring_variants = (
        ("right_vertical", {"drop_bus_position": "right_vertical"}),
        ("top_parallel", {"drop_bus_position": "top_parallel"}),
    )
    for label, params in microring_variants:
        cell = _create(layout, "Microring_DoubleBus", params)
        _assert_new_devrec(cell, layout, "Microring_DoubleBus", label)
        top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans(x_offset, 0)))
        x_offset += max(100000, cell.bbox().width() + 10000)
        created.append(cell)

    straight = _create(
        layout,
        "Straight_Waveguide",
        {"width": 0.75, "length": 12.345},
    )
    _assert_new_devrec(straight, layout, "Straight_Waveguide", "custom")
    top.insert(pya.CellInstArray(straight.cell_index(), pya.Trans(x_offset, 0)))
    x_offset += max(100000, straight.bbox().width() + 10000)
    created.append(straight)

    for pcell_name in NEW_DEVREC_PCELLS[1:]:
        for ports_type in ("type1", "type2", "type3"):
            cell = _create(layout, pcell_name, {"ports_type": ports_type})
            _assert_new_devrec(cell, layout, pcell_name, ports_type)
            top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans(x_offset, 0)))
            x_offset += max(100000, cell.bbox().width() + 10000)
            created.append(cell)

    with tempfile.TemporaryDirectory(prefix="jnu_pcell_devrec_") as temp_dir:
        gds_path = str(Path(temp_dir) / "public_pcell_devrec.gds")
        layout.write(gds_path)
        reread = pya.Layout()
        reread.read(gds_path)
        reread_top = reread.cell("JNU_PUBLIC_PCELL_DEVREC_REGRESSION")
        if reread_top is None:
            raise RuntimeError("GDS 重读后缺少回归顶层 Cell。")
        reread_devrec = reread.layer(DEVREC_LAYER)
        if _recursive_shape_count(reread_top, reread_devrec) < len(created):
            raise RuntimeError("GDS 重读后部分公开 PCell 变体的 DevRec 丢失。")

    print(
        "OK: public PCell=%d, checked variants=%d, DevRec 68/0 and GDS round-trip passed."
        % (len(public_names), len(created))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
