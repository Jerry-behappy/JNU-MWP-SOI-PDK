# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""为 JNU PCell 生成统一的 DevRec 器件识别边界。"""

import pya

from JNU_MWP_tools.core.common import DEVREC_LAYER


DEFAULT_DEVREC_CLEARANCE_UM = 1.0


def _pin_sides(cell, pin_layer):
    """根据 PinRec Path 的点序返回器件具有端口的外向边集合。"""

    sides = set()
    for shape in cell.shapes(pin_layer).each():
        if not shape.is_path():
            continue
        points = list(shape.path.each_point())
        if len(points) < 2:
            continue
        dx = points[-1].x - points[0].x
        dy = points[-1].y - points[0].y
        if dx == 0 and dy == 0:
            continue
        if abs(dx) >= abs(dy):
            sides.add("R" if dx > 0 else "L")
        else:
            sides.add("T" if dy > 0 else "B")
    return sides


def calculate_device_devrec_box(device_bbox, port_sides, clearance_dbu):
    """计算器件边界：端口边保持原界面，其余边增加识别净空。"""

    if device_bbox is None or device_bbox.empty():
        return pya.Box()

    clearance = max(0, int(round(clearance_dbu)))
    left = int(device_bbox.left)
    right = int(device_bbox.right)
    bottom = int(device_bbox.bottom)
    top = int(device_bbox.top)

    if "L" not in port_sides:
        left -= clearance
    if "R" not in port_sides:
        right += clearance
    if "B" not in port_sides:
        bottom -= clearance
    if "T" not in port_sides:
        top += clearance

    return pya.Box(left, bottom, right, top)


def insert_device_devrec(
    cell,
    device_layer,
    pin_layer,
    clearance_um=DEFAULT_DEVREC_CLEARANCE_UM,
):
    """在固定 68/0 层插入单一矩形 DevRec，并返回其整数 bbox。"""

    layout = cell.layout()
    device_bbox = cell.bbox(device_layer)
    if device_bbox.empty():
        return pya.Box()

    clearance_dbu = float(clearance_um) / float(layout.dbu)
    devrec_box = calculate_device_devrec_box(
        device_bbox,
        _pin_sides(cell, pin_layer),
        clearance_dbu,
    )
    devrec_layer = layout.layer(DEVREC_LAYER)
    cell.shapes(devrec_layer).clear()
    cell.shapes(devrec_layer).insert(devrec_box)
    return devrec_box


__all__ = [
    "DEFAULT_DEVREC_CLEARANCE_UM",
    "calculate_device_devrec_box",
    "insert_device_devrec",
]
