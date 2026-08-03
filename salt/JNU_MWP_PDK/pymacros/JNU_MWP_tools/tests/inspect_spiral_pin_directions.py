# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-08
"""只读报告 GDS 中 Spiral cell 的 PinRec 路径方向。"""

import json
import math
import os

import pya


def _path_points(path):
    """兼容不同 KLayout 版本的 Path 点迭代接口。"""
    return [(point.x, point.y) for point in path.each_point()]


def _path_angle_degrees(points):
    """返回 PinRec 中心线首尾连线的角度及其非水平偏差。"""
    if len(points) < 2:
        return None, None, None
    x1, y1 = points[0]
    x2, y2 = points[-1]
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return None, dx, dy
    return math.degrees(math.atan2(dy, dx)), dx, dy


def _shape_report(shape, dbu):
    """提取 PinRec 上的路径或文字，保留 DBU 与微米坐标。"""
    if shape.is_path():
        points = _path_points(shape.path)
        angle, dx, dy = _path_angle_degrees(points)
        return {
            "kind": "path",
            "points_dbu": points,
            "points_um": [[round(x * dbu, 6), round(y * dbu, 6)] for x, y in points],
            "width_um": round(shape.path.width * dbu, 6),
            "angle_deg": None if angle is None else round(angle, 9),
            "dx_dbu": dx,
            "dy_dbu": dy,
            "horizontal_exact": dy == 0,
        }
    if shape.is_text():
        text = shape.text
        return {
            "kind": "text",
            "text": text.string,
            "position_um": [round(text.x * dbu, 6), round(text.y * dbu, 6)],
            "rotation": text.trans.rot,
        }
    return {"kind": "other", "bbox_dbu": shape.bbox().to_s()}


def _terminal_angle(points, from_start):
    """从中心线起点或终点寻找首个非零长度线段并计算切线角。"""
    if len(points) < 2:
        return None
    sequence = zip(points, points[1:]) if from_start else zip(reversed(points[:-1]), reversed(points[1:]))
    for point1, point2 in sequence:
        if from_start:
            x1, y1 = point1
            x2, y2 = point2
        else:
            x1, y1 = point2
            x2, y2 = point1
        if x1 != x2 or y1 != y2:
            return round(math.degrees(math.atan2(y2 - y1, x2 - x1)), 9)
    return None


def _si_shape_report(shape, dbu):
    """报告 Si 层 Path 的端点切线；polygon 只保留 bbox 作为辅助信息。"""
    if shape.is_path():
        points = _path_points(shape.path)
        return {
            "kind": "path",
            "point_count": len(points),
            "width_um": round(shape.path.width * dbu, 6),
            "start_um": [round(points[0][0] * dbu, 6), round(points[0][1] * dbu, 6)],
            "end_um": [round(points[-1][0] * dbu, 6), round(points[-1][1] * dbu, 6)],
            "start_tangent_deg": _terminal_angle(points, True),
            "end_tangent_deg": _terminal_angle(points, False),
        }
    return {"kind": "area", "bbox_dbu": shape.bbox().to_s()}


def _point_segment_distance_squared(x, y, point1, point2):
    """计算点到边界线段的最小距离平方，单位为 DBU 平方。"""
    x1, y1 = point1.x, point1.y
    x2, y2 = point2.x, point2.y
    dx = x2 - x1
    dy = y2 - y1
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return (x - x1) ** 2 + (y - y1) ** 2
    ratio = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / float(length_squared)))
    near_x = x1 + ratio * dx
    near_y = y1 + ratio * dy
    return (x - near_x) ** 2 + (y - near_y) ** 2


def _nearby_si_edges(cell, si_layer, center, dbu):
    """列出端口附近的 Si polygon 边，辅助判断实际出射切线方向。"""
    candidates = []
    for shape in cell.shapes(si_layer).each():
        if not (shape.is_polygon() or shape.is_simple_polygon()):
            continue
        polygon = shape.polygon
        points = list(polygon.each_point_hull())
        if len(points) < 2:
            continue
        for index, point1 in enumerate(points):
            point2 = points[(index + 1) % len(points)]
            dx = point2.x - point1.x
            dy = point2.y - point1.y
            if dx == 0 and dy == 0:
                continue
            candidates.append((
                _point_segment_distance_squared(center.x, center.y, point1, point2),
                point1,
                point2,
                math.degrees(math.atan2(dy, dx)),
            ))
    candidates.sort(key=lambda item: item[0])
    return [
        {
            "distance_um": round(math.sqrt(distance_squared) * dbu, 6),
            "p1_um": [round(point1.x * dbu, 6), round(point1.y * dbu, 6)],
            "p2_um": [round(point2.x * dbu, 6), round(point2.y * dbu, 6)],
            "angle_deg": round(angle, 9),
        }
        for distance_squared, point1, point2, angle in candidates[:6]
    ]


def _spiral_cells(layout):
    """筛选名称含 Spiral 的保存后 cell。"""
    return [cell for cell in layout.each_cell() if "spiral" in cell.name.lower()]


def main():
    """读入输入 GDS 并输出 Spiral PinRec 的 JSON 报告。"""
    path = os.path.abspath(str(input_file))
    layout = pya.Layout()
    layout.read(path)

    pin_layer = layout.find_layer(pya.LayerInfo(1, 10))
    if pin_layer is None or pin_layer < 0:
        raise RuntimeError("GDS 中不存在 PinRec (1/10) 图层")
    si_layer = layout.find_layer(pya.LayerInfo(1, 0))
    if si_layer is None or si_layer < 0:
        raise RuntimeError("GDS 中不存在 Si (1/0) 图层")

    report = {
        "input_file": path,
        "dbu_um": layout.dbu,
        "spiral_cells": [],
    }
    for cell in _spiral_cells(layout):
        shapes = [_shape_report(shape, layout.dbu) for shape in cell.shapes(pin_layer).each()]
        si_shapes = [_si_shape_report(shape, layout.dbu) for shape in cell.shapes(si_layer).each()]
        pin_edges = []
        for shape in cell.shapes(pin_layer).each():
            if not shape.is_path():
                continue
            pin_points = list(shape.path.each_point())
            center = pya.Point(
                int(round(0.5 * (pin_points[0].x + pin_points[-1].x))),
                int(round(0.5 * (pin_points[0].y + pin_points[-1].y))),
            )
            pin_edges.append({
                "pin_center_um": [round(center.x * layout.dbu, 6), round(center.y * layout.dbu, 6)],
                "nearby_si_edges": _nearby_si_edges(cell, si_layer, center, layout.dbu),
            })
        report["spiral_cells"].append({
            "cell": cell.name,
            "bbox_um": [
                round(cell.bbox().left * layout.dbu, 6),
                round(cell.bbox().bottom * layout.dbu, 6),
                round(cell.bbox().right * layout.dbu, 6),
                round(cell.bbox().top * layout.dbu, 6),
            ],
            "pinrec_shapes": shapes,
            "si_shapes": si_shapes,
            "pin_nearby_si_edges": pin_edges,
        })

    print(json.dumps(report, ensure_ascii=True, indent=2))


main()
