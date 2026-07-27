# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""Numerical text array 的序列、Basic.Text、净距、层级和 GDS 重读回归。"""

import os
import sys
import tempfile

import pya


PYMACROS_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if PYMACROS_DIR not in sys.path:
    sys.path.insert(0, PYMACROS_DIR)

from JNU_MWP_tools.actions.numerical_text_array import (
    MAX_ITEMS,
    create_numerical_text_array_cell,
    generate_number_sequence,
)


DBU = 0.001


def _expect_error(callback, text):
    try:
        callback()
    except ValueError:
        return
    raise RuntimeError(text)


def _instances(cell):
    return list(cell.each_inst())


def _check_sequence_helpers():
    assert generate_number_sequence(1, 5, 2) == [1, 3, 5]
    assert generate_number_sequence(5, 1, -2) == [5, 3, 1]
    assert generate_number_sequence(-2, 2, 2) == [-2, 0, 2]
    assert generate_number_sequence(7, 7, 1) == [7]
    assert generate_number_sequence(7, 7, -1) == [7]
    _expect_error(lambda: generate_number_sequence(1, 2, 0), "零步长未报错。")
    _expect_error(lambda: generate_number_sequence(1, 2, -1), "递增负步长未报错。")
    _expect_error(lambda: generate_number_sequence(2, 1, 1), "递减正步长未报错。")
    _expect_error(
        lambda: generate_number_sequence(1, MAX_ITEMS + 1, 1),
        "超出数量上限未报错。",
    )


def _check_basic_text_instances(cell, expected, layer_info, magnification):
    instances = _instances(cell)
    if len(instances) != len(expected):
        raise RuntimeError("Basic.Text 实例数量不正确。")
    for inst, value in zip(instances, expected):
        child = inst.cell
        if not child.is_pcell_variant():
            raise RuntimeError("子实例不是 PCell variant。")
        library = child.pcell_library()
        library_name = library.name() if callable(library.name) else library.name
        if str(library_name) != "Basic":
            raise RuntimeError("子实例不是 Basic library PCell。")
        params = child.pcell_parameters_by_name()
        if str(params.get("text")) != str(value):
            raise RuntimeError("Basic.Text 内容不正确。")
        selected_layer = params.get("layer")
        if selected_layer.layer != layer_info.layer or selected_layer.datatype != layer_info.datatype:
            raise RuntimeError("Basic.Text 图层不正确。")
        if abs(float(params.get("mag")) - magnification) > 1e-9:
            raise RuntimeError("Basic.Text magnification 不正确。")
        if inst.trans.angle != 0 or inst.trans.is_mirror():
            raise RuntimeError("Basic.Text 实例发生了旋转或镜像。")


def _center(box):
    return 0.5 * (box.left + box.right), 0.5 * (box.bottom + box.top)


def _check_center_pitch(cell, direction, pitch_dbu):
    boxes = [inst.bbox() for inst in _instances(cell)]
    for previous, current in zip(boxes, boxes[1:]):
        previous_x, previous_y = _center(previous)
        current_x, current_y = _center(current)
        if direction == "Horizontal":
            if abs((current_x - previous_x) - pitch_dbu) > 1.0:
                raise RuntimeError("横排文字中心距不正确。")
            if abs(current_y - previous_y) > 1.0:
                raise RuntimeError("横排文字中心未对齐。")
        else:
            if abs((current_y - previous_y) - pitch_dbu) > 1.0:
                raise RuntimeError("竖排文字中心距不正确。")
            if abs(current_x - previous_x) > 1.0:
                raise RuntimeError("竖排文字中心未对齐。")
    bbox = cell.bbox()
    if bbox.left != 0 or bbox.bottom != 0:
        raise RuntimeError("容器 Cell 未归一化到原点。")


def main():
    _check_sequence_helpers()

    layout = pya.Layout()
    layout.dbu = DBU
    top = layout.create_cell("NUMERICAL_TEXT_ARRAY_TOP")
    layer_info = pya.LayerInfo(10, 0, "Text")
    pitch_um = 7.25
    magnification = 10.0
    pitch_dbu = int(round(pitch_um / DBU))

    horizontal_values = [8, 9, 10, 11]
    horizontal = create_numerical_text_array_cell(
        layout,
        horizontal_values,
        "Horizontal",
        layer_info,
        pitch_um,
        magnification,
    )
    _check_basic_text_instances(horizontal, horizontal_values, layer_info, magnification)
    _check_center_pitch(horizontal, "Horizontal", pitch_dbu)

    vertical_values = [-1, 0, 1]
    vertical = create_numerical_text_array_cell(
        layout,
        vertical_values,
        "Vertical",
        layer_info,
        pitch_um,
        magnification,
    )
    _check_basic_text_instances(vertical, vertical_values, layer_info, magnification)
    _check_center_pitch(vertical, "Vertical", pitch_dbu)

    duplicate = create_numerical_text_array_cell(
        layout,
        horizontal_values,
        "Horizontal",
        layer_info,
        pitch_um,
        magnification,
    )
    if duplicate.name != horizontal.name + "_2":
        raise RuntimeError("重复 Cell 名称未按 _2 规则处理。")

    top.insert(pya.CellInstArray(horizontal.cell_index(), pya.Trans()))
    top.insert(pya.CellInstArray(vertical.cell_index(), pya.Trans(200000, 0)))
    expected_bbox = top.bbox()
    expected_shapes = sum(1 for _ in top.begin_shapes_rec(layout.layer(layer_info)))

    output = os.path.join(tempfile.gettempdir(), "jnu_numerical_text_array_regression.gds")
    layout.write(output)
    reread = pya.Layout()
    reread.read(output)
    reread_top = reread.cell("NUMERICAL_TEXT_ARRAY_TOP")
    if reread_top is None:
        raise RuntimeError("GDS 重读后缺少顶层 Cell。")
    if reread_top.bbox() != expected_bbox:
        raise RuntimeError("GDS 重读后 bbox 发生变化。")
    reread_layer = reread.layer(layer_info)
    reread_shapes = sum(1 for _ in reread_top.begin_shapes_rec(reread_layer))
    if reread_shapes != expected_shapes:
        raise RuntimeError("GDS 重读后文字几何数量发生变化。")
    try:
        os.remove(output)
    except OSError:
        pass

    print("Numerical text array regression: PASS")


if __name__ == "__main__":
    main()
