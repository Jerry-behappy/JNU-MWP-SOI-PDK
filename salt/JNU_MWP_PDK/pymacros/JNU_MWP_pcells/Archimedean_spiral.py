# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""双臂 Archimedean 螺旋波导 PCell。

外侧采用固定 pitch 的双臂 Archimedean 螺线；中心 S 连接器使用四个
JNU 公共 90° Bend 映射，四个中心转角均跟随 PCell 弯曲设置。
"""

import math
import os
import sys

import pya

try:
    from .pcell_defaults import default_choice, default_float
except ImportError:
    PCELL_DIR = os.path.dirname(os.path.abspath(__file__))
    if PCELL_DIR not in sys.path:
        sys.path.insert(0, PCELL_DIR)
    from pcell_defaults import default_choice, default_float


PYMACROS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PYMACROS_DIR not in sys.path:
    sys.path.insert(0, PYMACROS_DIR)

from JNU_MWP_tools.core.bend_sampling import points_per_90
from JNU_MWP_tools.core.devrec import insert_device_devrec

from .bend_90deg import (
    BEND_TYPE_CHOICES,
    DEFAULT_BEZIER_K,
    DEFAULT_EULER_RMAX,
    DEFAULT_EULER_RMIN,
    PORT_STRAIGHT_UM,
    _normalize_bend_type,
    calculate_bend_derived,
    corner_points,
)


PCELL_NAME = "Archimedean_Spiral"
DEFAULT_WG_LAYER = "1/0"
DEFAULT_PIN_LAYER = "1/10"
TEXT_LAYER = pya.LayerInfo(10, 0)
WG_LAYER_CHOICES = (
    ("1/0", "Si - waveguide layer (1/0)"),
    ("1/99", "Waveguide - raw path (1/99)"),
)
PIN_LAYER_CHOICES = (
    ("1/10", "PinRec - optical pin layer (1/10)"),
)
PORTS_TYPE_CHOICES = (
    ("type1", "type1 - ports on same side"),
    ("type2", "type2 - ports on opposite sides"),
    ("type3", "type3 - opposite sides, aligned y"),
)
DEFAULT_TARGET_LENGTH = 1000.0
DEFAULT_WIDTH = 0.5
DEFAULT_MIN_RADIUS = 10.0
DEFAULT_GAP = 2.0
DEFAULT_VERTICAL_STRETCH = 0.0
MAX_TURNS = 256
MAX_GDS_PATH_POINTS = 4000
PATH_SEGMENT_OVERLAP_POINTS = 24
# waypoint 索引按传入点列计数；中心连接器四个转角和 type3 底部输出转角跟随 bend_type。
_CENTER_PCELL_BEND_CORNER_INDICES = frozenset((1, 2, 4, 5))
_TYPE3_PCELL_BEND_CORNER_INDICES = frozenset((1,))


def _choice_values(choices):
    """返回 TypeList 的内部可选值。"""
    return tuple(value for value, _label in choices)


def _normalize_ports_type(value):
    """把端口类型归一到 type1/type2/type3。"""
    text = str(value)
    return text if text in _choice_values(PORTS_TYPE_CHOICES) else "type1"


def _layer_info_from_choice(value, fallback):
    """把固定列表中的 layer/datatype 字符串转换为 LayerInfo。"""
    try:
        layer, datatype = str(value).split("/", 1)
        return pya.LayerInfo(int(layer), int(datatype))
    except Exception:
        return fallback


def _append_point(points, point, tolerance=1e-12):
    """追加非重复点。"""
    if not points or math.hypot(points[-1].x - point.x, points[-1].y - point.y) > tolerance:
        points.append(point)


def _merge_segments(segments):
    """把共享端点的多个折线段合并为一个连续点列。"""
    merged = []
    for segment in segments:
        for point in segment:
            _append_point(merged, point)
    return merged


def _quantize_points(points, dbu):
    """把微米坐标量化到 DBU 网格并清理重复点。"""
    quantized = []
    for point in points:
        x = int(round(float(point.x) / dbu)) * dbu
        y = int(round(float(point.y) / dbu)) * dbu
        _append_point(quantized, pya.DPoint(x, y), tolerance=max(1e-15, dbu * 0.1))
    return quantized


def _path_length(points):
    """计算点列中心线长度。"""
    return sum(
        math.hypot(points[index].x - points[index - 1].x, points[index].y - points[index - 1].y)
        for index in range(1, len(points))
    )


def _split_centerline_with_overlap(
    points,
    max_points=MAX_GDS_PATH_POINTS,
    overlap_points=PATH_SEGMENT_OVERLAP_POINTS,
):
    """把完整中心线分块；相邻块重叠多个点，供 Region 合并消除端帽缝隙。"""
    if len(points) <= max_points:
        return [list(points)]
    overlap = max(2, min(int(overlap_points), int(max_points) // 4))
    segments = []
    start = 0
    while start < len(points) - 1:
        end = min(len(points), start + int(max_points))
        segment = list(points[start:end])
        if len(segment) >= 2:
            segments.append(segment)
        if end >= len(points):
            break
        start = end - overlap
    return segments


def _round_manhattan_waypoints(
    waypoints,
    radius,
    bend_type,
    bend_points_per_90,
    bezier,
    euler_rmax,
    euler_rmin,
    pcell_bend_corner_indices,
):
    """用公共点列映射直角，指定索引跟随 PCell 弯曲设置。"""
    configured_indices = frozenset(int(value) for value in pcell_bend_corner_indices)
    rounded = [waypoints[0]]
    for index in range(1, len(waypoints) - 1):
        previous = waypoints[index - 1]
        corner = waypoints[index]
        following = waypoints[index + 1]

        in_dx = corner.x - previous.x
        in_dy = corner.y - previous.y
        out_dx = following.x - corner.x
        out_dy = following.y - corner.y
        in_length = math.hypot(in_dx, in_dy)
        out_length = math.hypot(out_dx, out_dy)
        if in_length <= 1e-12 or out_length <= 1e-12:
            _append_point(rounded, corner)
            continue

        ux, uy = in_dx / in_length, in_dy / in_length
        vx, vy = out_dx / out_length, out_dy / out_length
        dot = max(-1.0, min(1.0, ux * vx + uy * vy))
        cross = ux * vy - uy * vx
        if abs(cross) <= 1e-12 or abs(dot) >= 1.0 - 1e-12:
            _append_point(rounded, corner)
            continue
        if abs(dot) > 1e-9:
            raise ValueError("Archimedean_Spiral 只允许对正交 waypoint 映射 90° Bend。")
        if in_length + 1e-12 < radius or out_length + 1e-12 < radius:
            raise ValueError("Archimedean_Spiral 直段不足以容纳 90° Bend。")

        start = pya.DPoint(corner.x - ux * radius, corner.y - uy * radius)
        _append_point(rounded, start)
        normal_x, normal_y = -uy, ux
        turn_sign = 1.0 if cross > 0.0 else -1.0
        corner_bend_type = bend_type if index in configured_indices else "Circular"
        local_points = corner_points(
            radius,
            corner_bend_type,
            bend_points_per_90,
            bezier,
            euler_rmax,
            euler_rmin,
        )
        for local_x, local_y in local_points[1:]:
            _append_point(
                rounded,
                pya.DPoint(
                    start.x + ux * local_x + normal_x * turn_sign * local_y,
                    start.y + uy * local_x + normal_y * turn_sign * local_y,
                ),
            )

    _append_point(rounded, waypoints[-1])
    return rounded


def _horizontal_port_segment(body_endpoint, outward_sign, landing_length, dbu):
    """生成宽度级水平 landing，并把端口最外侧边固定为 10 nm。"""
    body_point = _quantize_points([body_endpoint], dbu)[0]
    port_edge_length = max(dbu, int(round(PORT_STRAIGHT_UM / dbu)) * dbu)
    straight_length = max(
        port_edge_length,
        int(round(float(landing_length) / dbu)) * dbu,
    )
    endpoint = pya.DPoint(
        body_point.x + float(outward_sign) * straight_length,
        body_point.y,
    )
    edge_start = pya.DPoint(
        endpoint.x - float(outward_sign) * port_edge_length,
        endpoint.y,
    )
    return _quantize_points([body_point, edge_start, endpoint], dbu)


def _build_type3_opt1_route(
    body_endpoint,
    target_y,
    radius,
    bend_type,
    bend_points_per_90,
    bezier,
    euler_rmax,
    euler_rmin,
    port_landing_length,
    dbu,
):
    """构造 type3 opt1 的外侧直段与底部公共 90° Bend。

    type3 外侧转向由 Archimedean 左臂连续延伸生成；本函数只负责从其
    竖直切线端点向下延伸，并在 opt2 高度映射一个可配置的 90° 输出 Bend。
    """
    jog_x = int(round(float(body_endpoint.x) / dbu)) * dbu
    bend_exit = pya.DPoint(jog_x - float(radius), float(target_y))
    waypoints = [
        body_endpoint,
        pya.DPoint(jog_x, target_y),
        bend_exit,
    ]
    rounded = _round_manhattan_waypoints(
        waypoints,
        radius,
        bend_type,
        bend_points_per_90,
        bezier,
        euler_rmax,
        euler_rmin,
        _TYPE3_PCELL_BEND_CORNER_INDICES,
    )
    bend_route = _quantize_points(rounded, dbu)
    port_segment = _horizontal_port_segment(
        bend_route[-1], -1.0, port_landing_length, dbu
    )
    points = _merge_segments([bend_route, port_segment])
    return {
        "points": points,
        "jog_x": int(round(jog_x / dbu)) * dbu,
        "port_center": points[-1],
    }


def _center_connector_points(
    radius,
    arm_inner_radius,
    vertical_stretch,
    bend_type,
    bend_points_per_90,
    bezier,
    euler_rmax,
    euler_rmin,
):
    """构造连接双臂内端点的 S 形中心连接器。"""
    half_stretch = 0.5 * vertical_stretch
    waypoints = [
        pya.DPoint(-arm_inner_radius, 0.0),
        pya.DPoint(-arm_inner_radius, radius + half_stretch),
        pya.DPoint(0.0, radius + half_stretch),
        pya.DPoint(0.0, 0.0),
        pya.DPoint(0.0, -radius - half_stretch),
        pya.DPoint(arm_inner_radius, -radius - half_stretch),
        pya.DPoint(arm_inner_radius, 0.0),
    ]
    return _round_manhattan_waypoints(
        waypoints,
        radius,
        bend_type,
        bend_points_per_90,
        bezier,
        euler_rmax,
        euler_rmin,
        _CENTER_PCELL_BEND_CORNER_INDICES,
    )


def _archimedean_arc_length(radius0, radial_slope, theta0, theta1):
    """返回 r=radius0+radial_slope*theta 的解析弧长。"""
    slope = float(radial_slope)
    if slope <= 0.0:
        return abs(theta1 - theta0) * radius0

    def primitive(radius):
        root = math.sqrt(radius * radius + slope * slope)
        return 0.5 * (radius * root + slope * slope * math.asinh(radius / slope)) / slope

    start_radius = radius0 + slope * theta0
    end_radius = radius0 + slope * theta1
    return abs(primitive(end_radius) - primitive(start_radius))


def _archimedean_point_and_tangent(radius0, pitch, theta, phase):
    """返回 Archimedean 中心线点和解析切向量。"""
    radial_slope = pitch / math.pi
    radius = radius0 + radial_slope * theta
    angle = phase + theta
    cos_angle = math.cos(angle)
    sin_angle = math.sin(angle)
    point = pya.DPoint(radius * cos_angle, radius * sin_angle)
    tangent = pya.DVector(
        radial_slope * cos_angle - radius * sin_angle,
        radial_slope * sin_angle + radius * cos_angle,
    )
    return point, tangent


def _archimedean_axis_tangent_theta(
    radius0,
    pitch,
    theta_guess,
    phase,
    axis,
):
    """在 cardinal guess 后求使解析切线严格水平或竖直的 theta。"""
    if axis not in ("horizontal", "vertical"):
        raise ValueError("axis 必须是 horizontal 或 vertical。")

    def residual(theta):
        _point, tangent = _archimedean_point_and_tangent(
            radius0, pitch, theta, phase
        )
        return tangent.y if axis == "horizontal" else tangent.x

    low = float(theta_guess)
    high = low + 0.25 * math.pi
    low_value = residual(low)
    high_value = residual(high)
    if low_value == 0.0:
        return low
    if low_value * high_value > 0.0:
        raise ValueError("无法在 Archimedean 四分之一圈内找到指定轴向切线。")
    for _index in range(80):
        middle = 0.5 * (low + high)
        middle_value = residual(middle)
        if abs(middle_value) <= 1e-14:
            return middle
        if low_value * middle_value <= 0.0:
            high = middle
        else:
            low = middle
            low_value = middle_value
    return 0.5 * (low + high)


def _archimedean_quarter_segments(radius0, pitch, theta_end, phase, dbu):
    """按不超过 90° 的连续分段生成一条 Archimedean Spiral 臂。"""
    radial_slope = pitch / math.pi
    segments = []
    theta0 = 0.0
    while theta0 < theta_end - 1e-14:
        theta1 = min(theta_end, theta0 + 0.5 * math.pi)
        outer_radius = radius0 + radial_slope * theta1
        angle_ratio = (theta1 - theta0) / (0.5 * math.pi)
        sample_count = max(2, int(math.ceil(points_per_90(outer_radius, dbu) * angle_ratio)))
        segment = []
        for sample_index in range(sample_count + 1):
            theta = theta0 + (theta1 - theta0) * sample_index / sample_count
            radius = radius0 + radial_slope * theta
            angle = phase + theta
            segment.append(pya.DPoint(radius * math.cos(angle), radius * math.sin(angle)))
        segments.append(segment)
        theta0 = theta1
    return segments


def _build_spiral_paths_for_turns(
    turns,
    port_key,
    radius0,
    pitch,
    center_points,
    bend,
    port_landing_length,
    dbu,
):
    """生成固定圈数的实际绘制段与完整量化中心线。"""
    theta_base = 2.0 * math.pi * turns - 0.5 * math.pi
    if port_key == "type3":
        # 左臂继续生成约 90° 的 Archimedean 外圈，直到切线严格竖直向下。
        theta_left = _archimedean_axis_tangent_theta(
            radius0, pitch, 2.0 * math.pi * turns, math.pi, "vertical"
        )
    else:
        theta_left = _archimedean_axis_tangent_theta(
            radius0, pitch, theta_base, math.pi, "horizontal"
        )
    theta_right_guess = theta_base + (math.pi if port_key == "type1" else 0.0)
    theta_right = _archimedean_axis_tangent_theta(
        radius0, pitch, theta_right_guess, 0.0, "horizontal"
    )
    left_segments = _archimedean_quarter_segments(radius0, pitch, theta_left, math.pi, dbu)
    right_segments = _archimedean_quarter_segments(radius0, pitch, theta_right, 0.0, dbu)

    left_draw_segments = [_quantize_points(segment, dbu) for segment in left_segments]
    right_draw_segments = [_quantize_points(segment, dbu) for segment in right_segments]
    left_points = _quantize_points(_merge_segments(left_draw_segments), dbu)
    right_points = _quantize_points(_merge_segments(right_draw_segments), dbu)
    body_min_x = min(point.x for point in left_points + right_points)

    type3_jog = None
    if port_key == "type3":
        type3_jog = _build_type3_opt1_route(
            left_points[-1],
            right_points[-1].y,
            bend["effective_radius"],
            bend["bend_type"],
            bend["points_per_90"],
            bend["bezier_k"],
            bend["Euler_Rmax"],
            bend["Euler_Rmin"],
            port_landing_length,
            dbu,
        )
        type3_jog["reference_min_x"] = min(point.x for point in right_points)
        opt1_segment = type3_jog["points"]
    else:
        opt1_segment = _horizontal_port_segment(
            left_points[-1], -1.0, port_landing_length, dbu
        )

    opt2_sign = -1.0 if port_key == "type1" else 1.0
    opt2_segment = _horizontal_port_segment(
        right_points[-1], opt2_sign, port_landing_length, dbu
    )
    left_points = _merge_segments([left_points, opt1_segment])
    right_points = _merge_segments([right_points, opt2_segment])

    metric_points = _merge_segments([list(reversed(left_points)), center_points, right_points])
    metric_points = _quantize_points(metric_points, dbu)
    draw_segments = _split_centerline_with_overlap(metric_points)
    total_length = _path_length(metric_points)
    left_endpoint, left_tangent = _archimedean_point_and_tangent(
        radius0, pitch, theta_left, math.pi
    )
    right_endpoint, right_tangent = _archimedean_point_and_tangent(
        radius0, pitch, theta_right, 0.0
    )
    return {
        "draw_segments": draw_segments,
        "metric_points": metric_points,
        "total_length": total_length,
        "body_min_x": body_min_x,
        "port_segments": {"opt1": opt1_segment, "opt2": opt2_segment},
        "type3_jog": type3_jog,
        "theta_left": theta_left,
        "theta_right": theta_right,
        "theta_base": theta_base,
        "left_archimedean_endpoint": left_endpoint,
        "right_archimedean_endpoint": right_endpoint,
        "left_archimedean_tangent": left_tangent,
        "right_archimedean_tangent": right_tangent,
    }


def _estimated_total_length(
    turns,
    target_ports_type,
    radius0,
    pitch,
    center_length,
    effective_radius,
    bend_length,
    port_landing_length,
):
    """用解析弧长估算指定圈数的总长度，并计入实际端口路由。"""
    radial_slope = pitch / math.pi
    theta_base = 2.0 * math.pi * turns - 0.5 * math.pi
    if target_ports_type == "type3":
        theta_left = _archimedean_axis_tangent_theta(
            radius0, pitch, 2.0 * math.pi * turns, math.pi, "vertical"
        )
    else:
        theta_left = _archimedean_axis_tangent_theta(
            radius0, pitch, theta_base, math.pi, "horizontal"
        )
    theta_right = _archimedean_axis_tangent_theta(
        radius0,
        pitch,
        theta_base + (math.pi if target_ports_type == "type1" else 0.0),
        0.0,
        "horizontal",
    )
    left_length = _archimedean_arc_length(radius0, radial_slope, 0.0, theta_left)
    right_length = _archimedean_arc_length(radius0, radial_slope, 0.0, theta_right)
    if target_ports_type != "type3":
        port_length = 2.0 * port_landing_length
    else:
        left_endpoint, _left_tangent = _archimedean_point_and_tangent(
            radius0, pitch, theta_left, math.pi
        )
        right_endpoint, _right_tangent = _archimedean_point_and_tangent(
            radius0, pitch, theta_right, 0.0
        )
        vertical_distance = abs(left_endpoint.y - right_endpoint.y)
        opt1_route = (
            vertical_distance
            - effective_radius
            + port_landing_length
            + bend_length
        )
        port_length = opt1_route + port_landing_length
    return center_length + left_length + right_length + port_length


def calculate_spiral_geometry(
    length,
    wg_width,
    min_radius,
    gap,
    ports_type,
    bend_type,
    bezier,
    euler_rmax,
    euler_rmin,
    vertical_stretch,
    dbu=0.001,
):
    """纯计算 Spiral 几何与只读派生值，供 coerce、GUI 和绘制共用。"""
    dbu = max(abs(float(dbu)), 1e-9)
    target_length = float(length)
    width = float(wg_width)
    radius_value = float(min_radius)
    gap_value = float(gap)
    stretch = float(vertical_stretch)
    if target_length <= 0.0:
        raise ValueError("Target length 必须大于 0。")
    if width <= 0.0:
        raise ValueError("Waveguide width 必须大于 0。")
    if gap_value < 0.0:
        raise ValueError("Waveguide gap 不得小于 0。")
    if stretch < 0.0:
        raise ValueError("Vertical stretch 不得小于 0。")

    bend = calculate_bend_derived(
        radius_value,
        bend_type,
        bezier,
        euler_rmax,
        euler_rmin,
        dbu,
    )
    effective_radius = float(bend["effective_radius"])
    if effective_radius < width:
        raise ValueError("有效中心弯曲半径不得小于波导宽度。")

    port_key = _normalize_ports_type(ports_type)
    pitch = width + gap_value
    # 10 nm 仍作为最外侧独立端段；完整水平 landing 至少等于一个波导宽度，
    # 避免宽波导的曲线 Polygon 侵入端口区域并形成非零物理角度。
    port_landing_length = max(
        max(dbu, int(round(PORT_STRAIGHT_UM / dbu)) * dbu),
        int(round(width / dbu)) * dbu,
    )
    # vertical_stretch 同步扩大中心内孔，避免拉长后的 S 连接器碰到内圈波导；
    # 外侧双臂仍保持固定 pitch，不做比例缩放。
    radius0 = 2.0 * effective_radius + 0.5 * stretch
    center_points = _quantize_points(
        _center_connector_points(
            effective_radius,
            radius0,
            stretch,
            bend["bend_type"],
            bend["points_per_90"],
            bend["bezier_k"],
            bend["Euler_Rmax"],
            bend["Euler_Rmin"],
        ),
        dbu,
    )
    center_length = _path_length(center_points)

    turns = None
    for candidate in range(1, MAX_TURNS + 1):
        estimate = _estimated_total_length(
            candidate,
            port_key,
            radius0,
            pitch,
            center_length,
            effective_radius,
            bend["bend_length"],
            port_landing_length,
        )
        if estimate + dbu >= target_length:
            turns = candidate
            break
    if turns is None:
        raise ValueError("Target length 过大，超过 %d 圈的计算上限。" % MAX_TURNS)

    built = _build_spiral_paths_for_turns(
        turns, port_key, radius0, pitch, center_points, bend, port_landing_length, dbu
    )
    previous_turn_length = None

    # 解析估算只负责快速定位；最终用 DBU 量化后的实际 Si 路径保证圈数最小。
    while turns > 1:
        previous = _build_spiral_paths_for_turns(
            turns - 1,
            port_key,
            radius0,
            pitch,
            center_points,
            bend,
            port_landing_length,
            dbu,
        )
        if previous["total_length"] + dbu < target_length:
            previous_turn_length = previous["total_length"]
            break
        turns -= 1
        built = previous

    while built["total_length"] + dbu < target_length and turns < MAX_TURNS:
        previous_turn_length = built["total_length"]
        turns += 1
        built = _build_spiral_paths_for_turns(
            turns,
            port_key,
            radius0,
            pitch,
            center_points,
            bend,
            port_landing_length,
            dbu,
        )
    if built["total_length"] + dbu < target_length:
        raise ValueError("Target length 过大，超过 %d 圈的计算上限。" % MAX_TURNS)
    if turns > 1 and previous_turn_length is None:
        previous_turn_length = _build_spiral_paths_for_turns(
            turns - 1,
            port_key,
            radius0,
            pitch,
            center_points,
            bend,
            port_landing_length,
            dbu,
        )["total_length"]

    metric_points = built["metric_points"]
    draw_segments = built["draw_segments"]
    total_length = built["total_length"]
    start = metric_points[0]
    end = metric_points[-1]
    delta_l = total_length - abs(end.x - start.x)
    outer_radius = max(
        math.hypot(point.x, point.y)
        for point in metric_points
    )
    return {
        "target_length": target_length,
        "wg_width": width,
        "min_radius": bend["radius"],
        "gap": gap_value,
        "pitch": pitch,
        "arm_inner_radius": radius0,
        "ports_type": port_key,
        "bend_type": bend["bend_type"],
        "bezier": bend["bezier_k"],
        "Bezier_Rmax": bend["Bezier_Rmax"],
        "Bezier_Rmin": bend["Bezier_Rmin"],
        "Euler_Rmax": bend["Euler_Rmax"],
        "Euler_Rmin": bend["Euler_Rmin"],
        "Euler_Reff": bend["Euler_Reff"],
        "effective_radius": effective_radius,
        "points_per_90": bend["points_per_90"],
        "port_landing_length": port_landing_length,
        "vertical_stretch": stretch,
        "turns": turns,
        "previous_turn_length": previous_turn_length,
        "outer_radius": outer_radius,
        "total_length": total_length,
        "delta_L": delta_l,
        "metric_points": metric_points,
        "draw_segments": draw_segments,
        "port_segments": built["port_segments"],
        "body_min_x": built["body_min_x"],
        "type3_jog": built["type3_jog"],
        "theta_left": built["theta_left"],
        "theta_right": built["theta_right"],
        "theta_base": built["theta_base"],
        "left_archimedean_endpoint": built["left_archimedean_endpoint"],
        "right_archimedean_endpoint": built["right_archimedean_endpoint"],
        "left_archimedean_tangent": built["left_archimedean_tangent"],
        "right_archimedean_tangent": built["right_archimedean_tangent"],
        "center_points": center_points,
    }


class ArchimedeanSpiral(pya.PCellDeclarationHelper):
    """JNU 双臂 Archimedean Spiral PCell。"""

    def __init__(self):
        super(ArchimedeanSpiral, self).__init__()

        wg_layer_default = default_choice(
            PCELL_NAME, "wg_layer", DEFAULT_WG_LAYER, _choice_values(WG_LAYER_CHOICES)
        )
        pin_layer_default = default_choice(
            PCELL_NAME, "pin_layer", DEFAULT_PIN_LAYER, _choice_values(PIN_LAYER_CHOICES)
        )
        bend_type_default = _normalize_bend_type(
            default_choice(PCELL_NAME, "bend_type", "Circular", BEND_TYPE_CHOICES)
        )
        ports_type_default = _normalize_ports_type(
            default_choice(PCELL_NAME, "ports_type", "type1", _choice_values(PORTS_TYPE_CHOICES))
        )

        wg_layer_param = self.param(
            "wg_layer", self.TypeList, "Waveguide layer", default=wg_layer_default
        )
        for value, label in WG_LAYER_CHOICES:
            wg_layer_param.add_choice(label, value)

        pin_layer_param = self.param(
            "pin_layer", self.TypeList, "Pin recognition layer", default=pin_layer_default
        )
        for value, label in PIN_LAYER_CHOICES:
            pin_layer_param.add_choice(label, value)

        self.param(
            "length",
            self.TypeDouble,
            "Target waveguide length",
            unit="um",
            default=default_float(PCELL_NAME, "length", DEFAULT_TARGET_LENGTH),
        )
        self.param(
            "wg_width",
            self.TypeDouble,
            "Waveguide width",
            unit="um",
            default=default_float(PCELL_NAME, "wg_width", DEFAULT_WIDTH),
        )
        self.min_radius_param = self.param(
            "min_radius",
            self.TypeDouble,
            "Minimum / center bend radius",
            unit="um",
            default=default_float(PCELL_NAME, "min_radius", DEFAULT_MIN_RADIUS),
        )
        self.param(
            "gap",
            self.TypeDouble,
            "Waveguide gap",
            unit="um",
            default=default_float(PCELL_NAME, "gap", DEFAULT_GAP),
        )

        ports_param = self.param(
            "ports_type", self.TypeList, "Ports type", default=ports_type_default
        )
        for value, label in PORTS_TYPE_CHOICES:
            ports_param.add_choice(label, value)

        bend_param = self.param(
            "bend_type", self.TypeList, "Center bend type", default=bend_type_default
        )
        for choice in BEND_TYPE_CHOICES:
            bend_param.add_choice(choice, choice)

        self.bezier_param = self.param(
            "bezier",
            self.TypeDouble,
            "Bezier shape factor",
            default=default_float(PCELL_NAME, "bezier", DEFAULT_BEZIER_K),
        )
        self.Euler_Rmax_param = self.param(
            "Euler_Rmax",
            self.TypeDouble,
            "Euler max radius (endpoint)",
            unit="um",
            default=default_float(PCELL_NAME, "Euler_Rmax", DEFAULT_EULER_RMAX),
        )
        self.Euler_Rmin_param = self.param(
            "Euler_Rmin",
            self.TypeDouble,
            "Euler min radius (midpoint)",
            unit="um",
            default=default_float(PCELL_NAME, "Euler_Rmin", DEFAULT_EULER_RMIN),
        )
        self.param(
            "vertical_stretch",
            self.TypeDouble,
            "Vertical stretch",
            unit="um",
            default=default_float(
                PCELL_NAME, "vertical_stretch", DEFAULT_VERTICAL_STRETCH
            ),
        )

        # 只读派生参数统一放在全部可编辑参数之后，保持 PCell 面板顺序一致。
        self.Bezier_Rmax_param = self.param(
            "Bezier_Rmax",
            self.TypeDouble,
            "Bezier max radius [uneditable]",
            unit="um",
            default=0.0,
            readonly=True,
        )
        self.Bezier_Rmin_param = self.param(
            "Bezier_Rmin",
            self.TypeDouble,
            "Bezier min radius [uneditable]",
            unit="um",
            default=0.0,
            readonly=True,
        )
        self.Euler_Reff_param = self.param(
            "Euler_Reff",
            self.TypeDouble,
            "Euler effective radius [uneditable]",
            unit="um",
            default=0.0,
            readonly=True,
        )
        self.param(
            "points_per_90",
            self.TypeInt,
            "Center bend points per 90° [uneditable]",
            default=points_per_90(DEFAULT_MIN_RADIUS, 0.001),
            readonly=True,
        )
        self.param(
            "turns",
            self.TypeInt,
            "Calculated full turns [uneditable]",
            default=1,
            readonly=True,
        )
        self.param(
            "total_length",
            self.TypeDouble,
            "Calculated centerline length [uneditable]",
            unit="um",
            default=0.0,
            readonly=True,
        )
        self.param(
            "delta_L",
            self.TypeDouble,
            "delta_L [uneditable]",
            unit="um",
            default=0.0,
            readonly=True,
        )

        self._set_declared_visibility(bend_type_default)

    def _set_declared_visibility(self, bend_type):
        """设置首次打开参数面板时的弯曲参数可见性。"""
        is_bezier = bend_type == "Bezier"
        is_euler = bend_type == "Euler"
        try:
            self.min_radius_param.hidden = is_euler
            self.bezier_param.hidden = not is_bezier
            self.Bezier_Rmax_param.hidden = not is_bezier
            self.Bezier_Rmin_param.hidden = not is_bezier
            self.Euler_Rmax_param.hidden = not is_euler
            self.Euler_Rmin_param.hidden = not is_euler
            self.Euler_Reff_param.hidden = not is_euler
        except Exception:
            pass

    def display_text_impl(self):
        """返回包含全部用户几何参数的 PCell 名称。"""
        radius_text = (
            "Reff=%.3f,Rmax=%.3f,Rmin=%.3f"
            % (self.Euler_Reff, self.Euler_Rmax, self.Euler_Rmin)
            if self.bend_type == "Euler"
            else "R=%.3f" % self.min_radius
        )
        bezier_text = ",B=%.3f" % self.bezier if self.bend_type == "Bezier" else ""
        return (
            "Archimedean_Spiral(%s,%s,target=%.3f,L=%.3f,dL=%.3f,%s,w=%.3f,gap=%.3f,vs=%.3f%s)"
            % (
                self.ports_type,
                self.bend_type,
                self.length,
                self.total_length,
                self.delta_L,
                radius_text,
                self.wg_width,
                self.gap,
                self.vertical_stretch,
                bezier_text,
            )
        )

    def _current_geometry(self, dbu):
        """按当前实例参数执行统一纯计算。"""
        return calculate_spiral_geometry(
            self.length,
            self.wg_width,
            self.min_radius,
            self.gap,
            self.ports_type,
            self.bend_type,
            self.bezier,
            self.Euler_Rmax,
            self.Euler_Rmin,
            self.vertical_stretch,
            dbu,
        )

    def coerce_parameters_impl(self):
        """约束输入并刷新圈数、计算长度和 delta_L。"""
        dbu = self.layout.dbu if self.layout is not None else 0.001
        self.wg_layer = (
            str(self.wg_layer)
            if str(self.wg_layer) in _choice_values(WG_LAYER_CHOICES)
            else DEFAULT_WG_LAYER
        )
        self.pin_layer = (
            str(self.pin_layer)
            if str(self.pin_layer) in _choice_values(PIN_LAYER_CHOICES)
            else DEFAULT_PIN_LAYER
        )
        self.length = max(dbu, float(self.length))
        self.wg_width = max(dbu, float(self.wg_width))
        self.min_radius = max(self.wg_width, float(self.min_radius))
        self.gap = max(0.0, float(self.gap))
        self.vertical_stretch = max(0.0, float(self.vertical_stretch))
        self.ports_type = _normalize_ports_type(self.ports_type)
        self.bend_type = _normalize_bend_type(self.bend_type)
        self.bezier = max(0.05, min(0.95, float(self.bezier)))
        self.Euler_Rmax = max(dbu, float(self.Euler_Rmax))
        self.Euler_Rmin = max(dbu, float(self.Euler_Rmin))
        if self.Euler_Rmin >= self.Euler_Rmax:
            self.Euler_Rmin = 0.5 * self.Euler_Rmax

        geometry = self._current_geometry(dbu)
        self.points_per_90 = geometry["points_per_90"]
        if geometry["Bezier_Rmax"] is not None:
            self.Bezier_Rmax = round(geometry["Bezier_Rmax"], 3)
            self.Bezier_Rmin = round(geometry["Bezier_Rmin"], 3)
        if geometry["Euler_Reff"] is not None:
            self.Euler_Reff = round(geometry["Euler_Reff"], 3)
        self.turns = geometry["turns"]
        self.total_length = round(geometry["total_length"], 3)
        self.delta_L = round(geometry["delta_L"], 3)

    def callback(self, layout, name, states):
        """保存 callback 使用的 DBU，并进入 KLayout 标准回调流程。"""
        try:
            self._jnu_callback_dbu = layout.dbu
        except Exception:
            self._jnu_callback_dbu = 0.001
        return super(ArchimedeanSpiral, self).callback(layout, name, states)

    @staticmethod
    def _state_to_string(state):
        """兼容读取 PCellParameterState.value 的属性/方法形式。"""
        try:
            value = state.value
            value = value() if callable(value) else value
            return str(value)
        except Exception:
            return ""

    @staticmethod
    def _set_state_value(state, value):
        """兼容写入不同 KLayout 版本的参数状态。"""
        try:
            state.value = value
            return True
        except Exception:
            return False

    def callback_impl(self, name):
        """实时更新弯曲可见性、圈数、总长度和 delta_L。"""
        dbu = getattr(self, "_jnu_callback_dbu", 0.001)
        try:
            bend_type = _normalize_bend_type(self._state_to_string(self.bend_type))
            is_bezier = bend_type == "Bezier"
            is_euler = bend_type == "Euler"
            self.min_radius.visible = not is_euler
            self.bezier.visible = is_bezier
            self.Bezier_Rmax.visible = is_bezier
            self.Bezier_Rmin.visible = is_bezier
            self.Euler_Rmax.visible = is_euler
            self.Euler_Rmin.visible = is_euler
            self.Euler_Reff.visible = is_euler

            geometry = calculate_spiral_geometry(
                float(self._state_to_string(self.length)),
                float(self._state_to_string(self.wg_width)),
                float(self._state_to_string(self.min_radius)),
                float(self._state_to_string(self.gap)),
                _normalize_ports_type(self._state_to_string(self.ports_type)),
                bend_type,
                float(self._state_to_string(self.bezier)),
                float(self._state_to_string(self.Euler_Rmax)),
                float(self._state_to_string(self.Euler_Rmin)),
                float(self._state_to_string(self.vertical_stretch)),
                dbu,
            )
            if geometry["Bezier_Rmax"] is not None:
                self._set_state_value(self.Bezier_Rmax, round(geometry["Bezier_Rmax"], 3))
                self._set_state_value(self.Bezier_Rmin, round(geometry["Bezier_Rmin"], 3))
            if geometry["Euler_Reff"] is not None:
                self._set_state_value(self.Euler_Reff, round(geometry["Euler_Reff"], 3))
            self._set_state_value(self.points_per_90, geometry["points_per_90"])
            self._set_state_value(self.turns, geometry["turns"])
            self._set_state_value(self.total_length, round(geometry["total_length"], 3))
            self._set_state_value(self.delta_L, round(geometry["delta_L"], 3))
        except Exception:
            for state in (
                self.Bezier_Rmax,
                self.Bezier_Rmin,
                self.Euler_Reff,
                self.points_per_90,
                self.turns,
                self.total_length,
                self.delta_L,
            ):
                self._set_state_value(state, "")
            self._set_declared_visibility(
                _normalize_bend_type(self._state_to_string(self.bend_type))
            )

    @staticmethod
    def _cardinal_direction(dx, dy):
        """把端口外向矢量归一到 0/90/180/270 度。"""
        if abs(dx) >= abs(dy):
            return 0 if dx >= 0.0 else 180
        return 90 if dy >= 0.0 else 270

    def _insert_pins(self, points, pin_layer):
        """在完整中心线两端插入 SiEPIC 兼容光学端口。"""
        if len(points) < 2:
            return
        # pymacros 父目录已在模块顶层加入 sys.path。
        from JNU_MWP_tools.core.make_pin import make_pin

        start = points[0]
        following = points[1]
        previous = points[-2]
        end = points[-1]
        start_direction = self._cardinal_direction(
            start.x - following.x, start.y - following.y
        )
        end_direction = self._cardinal_direction(
            end.x - previous.x, end.y - previous.y
        )
        make_pin(self.cell, "opt1", start, float(self.wg_width), pin_layer, start_direction)
        make_pin(self.cell, "opt2", end, float(self.wg_width), pin_layer, end_direction)

    def _insert_parameter_text(self, geometry, text_layer):
        """在中心区域写入计算长度和 delta_L。"""
        label = "Archimedean_Spiral type=%s bend=%s L=%.3fum delta_L=%.3fum" % (
            self.ports_type,
            self.bend_type,
            self.total_length,
            self.delta_L,
        )
        if self.bend_type == "Euler":
            label += " Reff=%.3fum" % self.Euler_Reff
        text = pya.Text(label, pya.Trans(pya.Trans.R0, 0, 0))
        shape = self.cell.shapes(text_layer).insert(text)
        shape.text_halign = 1
        shape.text_valign = 1
        diameter = max(2.0 * geometry["outer_radius"], self.wg_width)
        shape.text_dsize = max(0.05, min(diameter * 0.025, diameter / max(1, len(label))))

    def produce_impl(self):
        """生成双臂 Spiral、中心 Bend、Paperclip 风格端口引出和参数文字。"""
        dbu = self.layout.dbu
        geometry = self._current_geometry(dbu)
        waveguide_layer = self.layout.layer(
            _layer_info_from_choice(self.wg_layer, pya.LayerInfo(1, 0))
        )
        pin_layer = self.layout.layer(
            _layer_info_from_choice(self.pin_layer, pya.LayerInfo(1, 10))
        )
        text_layer = self.layout.layer(TEXT_LAYER)
        width_dbu = max(1, int(round(float(self.wg_width) / dbu)))

        paths = []
        for segment in geometry["draw_segments"]:
            integer_points = []
            for point in segment:
                integer_point = pya.Point(
                    int(round(point.x / dbu)), int(round(point.y / dbu))
                )
                if not integer_points or integer_points[-1] != integer_point:
                    integer_points.append(integer_point)
            if len(integer_points) >= 2:
                paths.append(pya.Path(integer_points, width_dbu))

        if str(self.wg_layer) == "1/0":
            # 物理 Si 层先把重叠 Path 转成 Region 合并，消除弯/直与分块端帽的楔形缝。
            waveguide_region = pya.Region()
            for path in paths:
                waveguide_region.insert(path.polygon())
            waveguide_region.merge()
            # 闭合因分块 DBU 舍入产生的 ≤1 DBU 微小缝隙，避免 DRC 误报。
            waveguide_region.size(1)
            waveguide_region.size(-1)
            self.cell.shapes(waveguide_layer).insert(waveguide_region)
        else:
            # raw waveguide 层保留 Path 语义；分块间已有多点重叠，避免曲线断接。
            for path in paths:
                self.cell.shapes(waveguide_layer).insert(path)

        self._insert_pins(geometry["metric_points"], pin_layer)
        insert_device_devrec(self.cell, waveguide_layer, pin_layer)
        self._insert_parameter_text(geometry, text_layer)


__all__ = [
    "ArchimedeanSpiral",
    "calculate_spiral_geometry",
    "PORTS_TYPE_CHOICES",
]
