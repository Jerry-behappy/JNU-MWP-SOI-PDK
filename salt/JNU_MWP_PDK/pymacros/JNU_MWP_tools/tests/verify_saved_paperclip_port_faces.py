# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-08
"""纯只读验证保存 GDS 中 Paperclip_Spiral 的 Si 水平端口端面。"""

import json
import os

import pya


SI_LAYER = pya.LayerInfo(1, 0)
PIN_LAYER = pya.LayerInfo(1, 10)


def _pin_data(cell, pin_layer):
    """读取严格水平的 PinRec 路径和其外端点。"""
    ports = []
    for shape in cell.shapes(pin_layer).each():
        if not shape.is_path():
            continue
        points = list(shape.path.each_point())
        if len(points) != 2:
            continue
        dx = points[1].x - points[0].x
        dy = points[1].y - points[0].y
        if dx == 0 or dy != 0:
            raise RuntimeError("%s 存在非水平 PinRec。" % cell.name)
        center = pya.Point(
                int(round(0.5 * (points[0].x + points[1].x))),
                int(round(0.5 * (points[0].y + points[1].y))),
            )
        ports.append({
            "center": center,
            "outer": points[1],
            "inward_sign": 1 if dx < 0 else -1,
            "width": shape.path.width,
        })
    if len(ports) != 2:
        raise RuntimeError("%s 应有两个水平 PinRec。" % cell.name)
    return ports


def _has_vertical_face(cell, si_layer, center, outer, width):
    """检查 PinRec 中心处是否存在覆盖全宽度的严格竖直 Si 端面。"""
    half_width = max(1, int(width) // 2)
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


def _si_region(cell, si_layer):
    """合并当前 cell 的 Si 面积图形，用于检查端口桥接区域是否完整。"""
    region = pya.Region()
    for shape in cell.shapes(si_layer).each():
        if shape.is_polygon() or shape.is_simple_polygon():
            region.insert(shape.polygon)
        elif shape.is_box():
            region.insert(shape.box)
    return region.merged()


def _shape_covers_point(shape, point):
    """用 2×2 DBU 探针判断面积 shape 是否真实覆盖指定点。"""
    if shape.is_box():
        shape_region = pya.Region(shape.box)
    elif shape.is_polygon() or shape.is_simple_polygon():
        shape_region = pya.Region(shape.polygon)
    else:
        return False
    probe = pya.Region(
        pya.Box(point.x - 1, point.y - 1, point.x + 1, point.y + 1)
    )
    return not (shape_region & probe).is_empty()


def _port_bridge_box(port):
    """返回从 PinRec 中心到内侧 10 nm 的全宽 landing。"""
    center = port["center"]
    outer = port["outer"]
    landing = max(1, abs(outer.x - center.x))
    inner_x = center.x + port["inward_sign"] * landing
    width = max(1, int(port["width"]))
    lower_half = width // 2
    upper_half = width - lower_half
    return pya.Box(
        min(center.x, inner_x),
        center.y - lower_half,
        max(center.x, inner_x),
        center.y + upper_half,
    )


def _port_outer_box(port):
    """返回 PinRec 外侧一半区域，用于确认该区域没有 Si 面积。"""
    center = port["center"]
    outer = port["outer"]
    width = max(1, int(port["width"]))
    lower_half = width // 2
    upper_half = width - lower_half
    return pya.Box(
        min(center.x, outer.x),
        center.y - lower_half,
        max(center.x, outer.x),
        center.y + upper_half,
    )


def main():
    """打开 GDS 并只读检查全部保存后的 Paperclip Spiral。"""
    path = os.path.abspath(str(input_file))
    layout = pya.Layout()
    layout.read(path)
    si_layer = layout.find_layer(SI_LAYER)
    pin_layer = layout.find_layer(PIN_LAYER)
    if si_layer is None or pin_layer is None:
        raise RuntimeError("GDS 缺少 Si 或 PinRec 图层。")

    verified = []
    for cell in layout.each_cell():
        if "paperclip_spiral" not in cell.name.lower():
            continue
        si_region = _si_region(cell, si_layer)
        component_count = sum(1 for _polygon in si_region.each())
        if component_count != 1:
            raise RuntimeError(
                "%s 的 Si 波导包含 %d 个断开的区域。"
                % (cell.name, component_count)
            )
        for port in _pin_data(cell, pin_layer):
            inner_probe = pya.Point(
                port["center"].x + port["inward_sign"],
                port["center"].y,
            )
            port_shape_count = sum(
                1
                for shape in cell.shapes(si_layer).each()
                if _shape_covers_point(shape, inner_probe)
            )
            if port_shape_count != 1:
                raise RuntimeError(
                    "%s 的端口中心仍由 %d 个 Si shape 拼接。"
                    % (cell.name, port_shape_count)
                )
            if not _has_vertical_face(
                cell,
                si_layer,
                port["center"],
                port["outer"],
                port["width"],
            ):
                raise RuntimeError("%s 的 Si 外端面仍不严格竖直。" % cell.name)
            missing = pya.Region(_port_bridge_box(port)) - si_region
            if not missing.is_empty():
                raise RuntimeError(
                    "%s 的 Si 端口内侧 10 nm landing 不完整。" % cell.name
                )
            outside_si = pya.Region(_port_outer_box(port)) & si_region
            if not outside_si.is_empty():
                raise RuntimeError(
                    "%s 的 PinRec 外侧一半仍被 Si 覆盖。" % cell.name
                )
        verified.append(cell.name)
    if not verified:
        raise RuntimeError("未找到 Paperclip_Spiral cell。")
    print(json.dumps({"verified_cells": sorted(verified)}, ensure_ascii=True))


main()
