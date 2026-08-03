# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-08
"""只读渲染保存后 Paperclip_Spiral 的 opt1 端口局部图。"""

import os

import pya


PIN_LAYER = pya.LayerInfo(1, 10)


def _first_horizontal_pin_center(cell, pin_layer, dbu):
    """返回当前 cell 第一个水平 PinRec 的中心坐标，单位为 um。"""
    for shape in cell.shapes(pin_layer).each():
        if not shape.is_path():
            continue
        points = list(shape.path.each_point())
        if len(points) != 2 or points[0].y != points[1].y:
            continue
        return (
            0.5 * (points[0].x + points[1].x) * dbu,
            0.5 * (points[0].y + points[1].y) * dbu,
        )
    raise RuntimeError("目标 Paperclip_Spiral 中没有水平 PinRec。")


def main():
    """载入 GDS，选择目标 cell 并把 opt1 附近保存为 PNG。"""
    input_path = os.path.abspath(str(input_file))
    output_path = os.path.abspath(str(output_file))
    requested_name = str(cell_name) if "cell_name" in globals() else ""

    view = pya.LayoutView()
    cellview_index = view.load_layout(input_path, False)
    layout = view.cellview(cellview_index).layout()
    pin_layer = layout.find_layer(PIN_LAYER)
    if pin_layer is None or pin_layer < 0:
        raise RuntimeError("GDS 缺少 PinRec (1/10) 图层。")

    target = layout.cell(requested_name) if requested_name else None
    if target is None:
        target = next(
            (
                cell
                for cell in layout.each_cell()
                if "paperclip_spiral" in cell.name.lower()
            ),
            None,
        )
    if target is None:
        raise RuntimeError("GDS 中没有 Paperclip_Spiral cell。")

    view.select_cell(target.cell_index(), cellview_index)
    center_x, center_y = _first_horizontal_pin_center(
        target, pin_layer, layout.dbu
    )
    view.zoom_box(
        pya.DBox(center_x - 0.25, center_y - 0.6, center_x + 0.8, center_y + 0.6)
    )
    view.save_image(output_path, 1400, 900)
    print("Rendered %s -> %s" % (target.name, output_path))


main()
