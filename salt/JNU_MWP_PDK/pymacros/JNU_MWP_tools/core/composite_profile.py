# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""复合波导绘图与长度统计共用的直弯分段和宽度分配规则。"""

import math

import pya


def _unit_step(delta):
    if abs(delta.x) >= abs(delta.y):
        return pya.Point(1 if delta.x >= 0 else -1, 0)
    return pya.Point(0, 1 if delta.y >= 0 else -1)


def _distance(start, end):
    return math.hypot(end.x - start.x, end.y - start.y)


def _canonical_points(points):
    """移除重复点和同向共线点，保留真实 Manhattan 转角。"""
    result = []
    for point in points:
        point = pya.Point(int(round(point.x)), int(round(point.y)))
        if result and result[-1] == point:
            continue
        result.append(point)
        while len(result) >= 3:
            a, b, c = result[-3:]
            if _unit_step(b - a) == _unit_step(c - b):
                result.pop(-2)
            else:
                break
    return result


def build_route_skeleton(points, radius_dbu):
    """只确定直段与弯曲切点，曲线形状由公共 Bend 生成器填充。"""
    points = _canonical_points(points)
    if len(points) < 2:
        return [], points
    primitives = []
    straight_start = points[0]
    for previous, corner, following in zip(points, points[1:], points[2:]):
        unit_in = _unit_step(corner - previous)
        unit_out = _unit_step(following - corner)
        cross = unit_in.x * unit_out.y - unit_in.y * unit_out.x
        if cross == 0:
            raise ValueError("Path包含180度折返或无效共线转角。")
        entry = corner - unit_in * int(radius_dbu)
        exit_point = corner + unit_out * int(radius_dbu)
        if straight_start != entry:
            primitives.append({"type": "straight", "start": straight_start, "end": entry})
        primitives.append({
            "type": "bend", "start": entry, "end": exit_point,
            "unit_in": unit_in, "turn": 1 if cross > 0 else -1,
            "points": [],
        })
        straight_start = exit_point
    if straight_start != points[-1]:
        primitives.append({"type": "straight", "start": straight_start, "end": points[-1]})
    return primitives, points


def _point_along(start, end, distance):
    total = _distance(start, end)
    if total <= 0:
        return pya.Point(start.x, start.y)
    ratio = float(distance) / total
    return pya.Point(
        int(round(start.x + (end.x - start.x) * ratio)),
        int(round(start.y + (end.y - start.y) * ratio)),
    )


def _bend_transition_parts(boundary_width, straight_width, taper_length, transition_length, reverse=False):
    if int(boundary_width) == int(straight_width):
        return []
    parts = [
        {"length": int(transition_length), "w0": int(boundary_width), "w1": int(boundary_width)},
        {"length": int(taper_length), "w0": int(boundary_width), "w1": int(straight_width)},
        {"length": int(transition_length), "w0": int(straight_width), "w1": int(straight_width)},
    ]
    if reverse:
        return [dict(length=p["length"], w0=p["w1"], w1=p["w0"]) for p in reversed(parts)]
    return parts


def _terminal_taper_parts(boundary_width, straight_width, taper_length, reverse=False):
    if int(boundary_width) == int(straight_width):
        return []
    widths = (straight_width, boundary_width) if reverse else (boundary_width, straight_width)
    return [{"length": int(taper_length), "w0": int(widths[0]), "w1": int(widths[1])}]


def _scale_part_lengths(parts, scale):
    return [dict(part, length=max(0, int(math.floor(int(part["length"]) * scale)))) for part in parts]


def profile_sections(primitives, straight_width, bend_width, taper_length,
                     transition_length=None, start_width=None, end_width=None):
    """按绘图顺序返回（点列、起始宽度、终止宽度、是否弯曲）。"""
    start_width = straight_width if start_width is None else start_width
    end_width = straight_width if end_width is None else end_width
    transition_length = taper_length if transition_length is None else transition_length
    for index, primitive in enumerate(primitives):
        if primitive["type"] == "bend":
            yield primitive["points"], bend_width, bend_width, True
            continue
        start, end = primitive["start"], primitive["end"]
        before = index > 0 and primitives[index - 1]["type"] == "bend"
        after = index + 1 < len(primitives) and primitives[index + 1]["type"] == "bend"
        if len(primitives) == 1 and int(start_width) == int(end_width):
            yield [start, end], start_width, start_width, False
            continue
        if (index == 0 and after and int(start_width) == int(bend_width)) or (
            index == len(primitives) - 1 and before and int(end_width) == int(bend_width)
        ):
            yield [start, end], bend_width, bend_width, False
            continue
        start_parts = (
            _bend_transition_parts(bend_width, straight_width, taper_length, transition_length)
            if before else _terminal_taper_parts(start_width, straight_width, taper_length) if index == 0 else []
        )
        end_parts = (
            _bend_transition_parts(bend_width, straight_width, taper_length, transition_length, reverse=True)
            if after else _terminal_taper_parts(end_width, straight_width, taper_length, reverse=True)
            if index == len(primitives) - 1 else []
        )
        total = sum(p["length"] for p in start_parts + end_parts)
        length = _distance(start, end)
        if total > length and total > 0:
            # 与绘图一致：容量不足时压缩局部过渡，DBU 取整后余量归入直宽段。
            start_parts = _scale_part_lengths(start_parts, length / total)
            end_parts = _scale_part_lengths(end_parts, length / total)
        cursor, consumed = start, 0
        for part in start_parts:
            if part["length"] <= 0:
                continue
            next_point = _point_along(start, end, consumed + part["length"])
            yield [cursor, next_point], part["w0"], part["w1"], False
            cursor, consumed = next_point, consumed + part["length"]
        end_length = sum(p["length"] for p in end_parts)
        center_end = _point_along(end, start, end_length) if end_length > 0 else end
        if cursor != center_end:
            yield [cursor, center_end], straight_width, straight_width, False
        cursor, consumed = center_end, 0
        for part in end_parts:
            if part["length"] <= 0:
                continue
            next_point = _point_along(center_end, end, consumed + part["length"])
            yield [cursor, next_point], part["w0"], part["w1"], False
            cursor, consumed = next_point, consumed + part["length"]


def profile_length_breakdown(primitives, total_length_um, dbu, straight_width,
                             bend_width, taper_length, transition_length,
                             start_width, end_width):
    """恒宽段按实际宽度计长，渐变段单独排除；弯曲使用已保存的圆滑总长。"""
    lengths = {}
    excluded = 0.0
    straight_length = math.fsum(
        _distance(p["start"], p["end"]) * dbu for p in primitives if p["type"] == "straight"
    )
    for points, width_start, width_end, is_bend in profile_sections(
        primitives, straight_width, bend_width, taper_length, transition_length, start_width, end_width,
    ):
        if is_bend:
            continue
        length = _distance(points[0], points[-1]) * dbu
        if int(width_start) != int(width_end):
            excluded += length
        else:
            width = int(width_start) * dbu
            lengths[width] = lengths.get(width, 0.0) + length
    # 全部弯曲均为弯宽；扣除直段即可得到原始 Circular/Bezier/Euler 的圆滑长度，
    # 无需用历史名称中已舍入的 B/Rmax/Rmin 重新生成曲线。
    bend_length = total_length_um - straight_length
    if bend_length < -0.001:
        raise ValueError("保存的波导长度小于实际直段长度。")
    if any(p["type"] == "bend" for p in primitives):
        width = int(bend_width) * dbu
        lengths[width] = lengths.get(width, 0.0) + max(0.0, bend_length)
    return lengths, excluded
