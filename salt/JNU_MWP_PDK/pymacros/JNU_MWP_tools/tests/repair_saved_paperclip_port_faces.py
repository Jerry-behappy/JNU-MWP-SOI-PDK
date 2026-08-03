# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-08
"""在副本 GDS 中修复已保存 Paperclip_Spiral 的 Si 水平端口端面。"""

import json
import os

import pya


SI_LAYER = pya.LayerInfo(1, 0)
PIN_LAYER = pya.LayerInfo(1, 10)


def _horizontal_pin_data(cell, pin_layer):
    """读取严格水平 PinRec 的中心、外端与内侧方向。"""
    pins = []
    for shape in cell.shapes(pin_layer).each():
        if not shape.is_path():
            continue
        points = list(shape.path.each_point())
        if len(points) != 2:
            continue
        dx = points[1].x - points[0].x
        dy = points[1].y - points[0].y
        if dx == 0 or dy != 0:
            continue
        center = pya.Point(
            int(round(0.5 * (points[0].x + points[1].x))),
            int(round(0.5 * (points[0].y + points[1].y))),
        )
        pins.append({
            "center": center,
            "outer": points[1],
            "inward_sign": 1 if dx < 0 else -1,
            "width": shape.path.width,
        })
    return pins


def _port_rectangle(port):
    """生成从 PinRec 中心到内侧 10 nm 的全宽矩形 landing。"""
    center = port["center"]
    outer = port["outer"]
    landing = max(1, abs(outer.x - center.x))
    inward_x = center.x + port["inward_sign"] * landing
    width = max(1, int(port["width"]))
    lower_half = width // 2
    upper_half = width - lower_half
    left = min(center.x, inward_x)
    right = max(center.x, inward_x)
    bottom = center.y - lower_half
    top = center.y + upper_half
    return pya.Polygon([
        pya.Point(left, bottom),
        pya.Point(right, bottom),
        pya.Point(right, top),
        pya.Point(left, top),
    ])


def _matching_si_shapes(cell, si_layer, port):
    """找出包围端口中心的 Si 面积图形，包括主体与独立端口矩形。"""
    center = port["center"]
    probe = pya.Region(
        pya.Box(center.x - 1, center.y - 1, center.x + 1, center.y + 1)
    )
    result = []
    for shape in cell.shapes(si_layer).each():
        if not (shape.is_polygon() or shape.is_simple_polygon() or shape.is_box()):
            continue
        shape_region = (
            pya.Region(shape.box) if shape.is_box() else pya.Region(shape.polygon)
        )
        if not (shape_region & probe).is_empty():
            result.append(shape)
    return result


def _shape_region(shape):
    """把 Polygon 或 Box shape 转为 Region。"""
    if shape.is_box():
        return pya.Region(shape.box)
    return pya.Region(shape.polygon)


def _replace_shapes_with_fixed_port(cell, si_layer, shapes, port):
    """局部合并端口主体与 landing，并把 Si 外端裁到 PinRec 中心。"""
    region = pya.Region()
    for shape in shapes:
        region += _shape_region(shape)
    bbox = region.bbox()
    left = bbox.left
    right = bbox.right
    if port["inward_sign"] > 0:
        left = max(left, port["center"].x)
    else:
        right = min(right, port["center"].x)
    if left >= right:
        raise RuntimeError("Paperclip_Spiral 端口裁剪范围无效。")

    clip_box = pya.Box(left, bbox.bottom - 1, right, bbox.top + 1)
    region &= pya.Region(clip_box)
    region.insert(_port_rectangle(port))
    region.merge()
    for shape in shapes:
        shape.delete()
    for polygon in region.each():
        cell.shapes(si_layer).insert(polygon)


def _has_vertical_port_face(cell, si_layer, port):
    """验证 PinRec 中心处存在覆盖全波导宽度的严格竖直 Si 端面。"""
    center = port["center"]
    half_width = max(1, int(port["width"]) // 2)
    for shape in cell.shapes(si_layer).each():
        if shape.is_box():
            box = shape.box
            if (
                center.x in (box.left, box.right)
                and box.bottom <= center.y - half_width
                and box.top >= center.y + half_width
            ):
                return True
            continue
        if not (shape.is_polygon() or shape.is_simple_polygon()):
            continue
        points = list(shape.polygon.each_point_hull())
        for index, point1 in enumerate(points):
            point2 = points[(index + 1) % len(points)]
            if point1.x != center.x or point2.x != center.x:
                continue
            if (
                min(point1.y, point2.y) <= center.y - half_width
                and max(point1.y, point2.y) >= center.y + half_width
            ):
                return True
    return False


def _repair_layout(layout):
    """只修复保存后的 Paperclip_Spiral cell，不触及其它器件或层级。"""
    si_layer = layout.find_layer(SI_LAYER)
    pin_layer = layout.find_layer(PIN_LAYER)
    if si_layer is None or si_layer < 0 or pin_layer is None or pin_layer < 0:
        raise RuntimeError("GDS 缺少 Si (1/0) 或 PinRec (1/10) 图层。")

    changed_cells = []
    for cell in layout.each_cell():
        if "paperclip_spiral" not in cell.name.lower():
            continue
        ports = _horizontal_pin_data(cell, pin_layer)
        if len(ports) != 2:
            continue
        for port in ports:
            matches = _matching_si_shapes(cell, si_layer, port)
            if not matches:
                raise RuntimeError("%s 中找不到端口对应的 Si polygon。" % cell.name)
            _replace_shapes_with_fixed_port(cell, si_layer, matches, port)
        for port in ports:
            if not _has_vertical_port_face(cell, si_layer, port):
                raise RuntimeError("%s 的 Si 端口端面修复失败。" % cell.name)
        changed_cells.append(cell.name)
    if not changed_cells:
        raise RuntimeError("未找到可修复的 Paperclip_Spiral cell。")
    return changed_cells


def main():
    """读取输入 GDS，修复副本并重新读回验证。"""
    input_path = os.path.abspath(str(input_file))
    output_path = os.path.abspath(str(output_file))
    if os.path.normcase(input_path) == os.path.normcase(output_path):
        raise RuntimeError("输出文件必须与原始 GDS 不同。")

    layout = pya.Layout()
    layout.read(input_path)
    changed_cells = _repair_layout(layout)
    layout.write(output_path)

    reread = pya.Layout()
    reread.read(output_path)
    verified_cells = _repair_layout(reread)
    print(json.dumps({
        "output_file": output_path,
        "changed_cells": changed_cells,
        "verified_cells": verified_cells,
    }, ensure_ascii=True))


main()
