# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-08

"""批量验证 JNU Archimedean_Spiral 的弯曲、端口、拉伸、长度与 GDS 重读。"""

import math
import os
from pathlib import Path
import sys
import tempfile

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

import JNULib  # noqa: F401,E402  注册 JNULib。
from JNU_MWP_pcells.Archimedean_spiral import (  # noqa: E402
    ArchimedeanSpiral,
    _CENTER_PCELL_BEND_CORNER_INDICES,
    _TYPE3_PCELL_BEND_CORNER_INDICES,
    _build_type3_opt1_route,
    _center_connector_points,
    calculate_spiral_geometry,
)
from JNU_MWP_pcells.bend_90deg import (  # noqa: E402
    calculate_bend_derived,
    corner_points,
)


LIBRARY_NAME = "JNULib"
SI_LAYER = pya.LayerInfo(1, 0)
PIN_LAYER = pya.LayerInfo(1, 10)
TEXT_LAYER = pya.LayerInfo(10, 0)
DBU = 0.001


def _point_keys(points):
    """把点列量化为 DBU 整数坐标，并清理相邻重复点。"""
    keys = []
    for point in points:
        key = (int(round(point.x / DBU)), int(round(point.y / DBU)))
        if not keys or keys[-1] != key:
            keys.append(key)
    return keys


def _contains_subsequence(points, expected):
    """判断量化点列是否完整包含指定连续 Bend 点列。"""
    if not expected or len(expected) > len(points):
        return False
    width = len(expected)
    return any(points[index:index + width] == expected for index in range(len(points) - width + 1))


def _mapped_corner_keys(
    previous,
    corner,
    following,
    radius,
    bend_type,
    bend_points_per_90,
    bezier,
    euler_rmax,
    euler_rmin,
):
    """独立映射一个公共 90° Bend，供可配置/固定转角的形状断言使用。"""
    in_dx = corner.x - previous.x
    in_dy = corner.y - previous.y
    out_dx = following.x - corner.x
    out_dy = following.y - corner.y
    in_length = math.hypot(in_dx, in_dy)
    out_length = math.hypot(out_dx, out_dy)
    ux, uy = in_dx / in_length, in_dy / in_length
    vx, vy = out_dx / out_length, out_dy / out_length
    cross = ux * vy - uy * vx
    normal_x, normal_y = -uy, ux
    turn_sign = 1.0 if cross > 0.0 else -1.0
    start = pya.DPoint(corner.x - ux * radius, corner.y - uy * radius)
    mapped = []
    for local_x, local_y in corner_points(
        radius,
        bend_type,
        bend_points_per_90,
        bezier,
        euler_rmax,
        euler_rmin,
    ):
        mapped.append(
            pya.DPoint(
                start.x + ux * local_x + normal_x * turn_sign * local_y,
                start.y + uy * local_x + normal_y * turn_sign * local_y,
            )
        )
    return _point_keys(mapped)


def _assert_corner_shape(
    points,
    waypoints,
    corner_index,
    radius,
    expected_type,
    rejected_type,
    bend,
):
    """断言指定 waypoint 的完整曲线采用期望类型且不是被拒绝类型。"""
    expected = _mapped_corner_keys(
        waypoints[corner_index - 1],
        waypoints[corner_index],
        waypoints[corner_index + 1],
        radius,
        expected_type,
        bend["points_per_90"],
        bend["bezier_k"],
        bend["Euler_Rmax"],
        bend["Euler_Rmin"],
    )
    if not _contains_subsequence(points, expected):
        raise RuntimeError("waypoint %d 未映射 %s Bend。" % (corner_index, expected_type))
    if rejected_type == expected_type:
        return
    rejected = _mapped_corner_keys(
        waypoints[corner_index - 1],
        waypoints[corner_index],
        waypoints[corner_index + 1],
        radius,
        rejected_type,
        bend["points_per_90"],
        bend["bezier_k"],
        bend["Euler_Rmax"],
        bend["Euler_Rmin"],
    )
    if _contains_subsequence(points, rejected):
        raise RuntimeError("waypoint %d 错误映射为 %s Bend。" % (corner_index, rejected_type))


def _check_configurable_bend_regions():
    """验证中心四个转角和 type3 底部输出转角跟随 bend_type。"""
    if _CENTER_PCELL_BEND_CORNER_INDICES != frozenset((1, 2, 4, 5)):
        raise RuntimeError("中心 S 四个可配置 Bend 索引不是 1/2/4/5。")
    if _TYPE3_PCELL_BEND_CORNER_INDICES != frozenset((1,)):
        raise RuntimeError("type3 底部可配置输出 Bend 索引不是 1。")

    for bend_type in ("Bezier", "Euler"):
        bend = calculate_bend_derived(10.0, bend_type, 0.35, 30.0, 10.0, DBU)
        radius = float(bend["effective_radius"])
        stretch = 20.0
        arm_inner_radius = 2.0 * radius + 0.5 * stretch
        waypoints = [
            pya.DPoint(-arm_inner_radius, 0.0),
            pya.DPoint(-arm_inner_radius, radius + 0.5 * stretch),
            pya.DPoint(0.0, radius + 0.5 * stretch),
            pya.DPoint(0.0, 0.0),
            pya.DPoint(0.0, -radius - 0.5 * stretch),
            pya.DPoint(arm_inner_radius, -radius - 0.5 * stretch),
            pya.DPoint(arm_inner_radius, 0.0),
        ]
        center = _center_connector_points(
            radius,
            arm_inner_radius,
            stretch,
            bend["bend_type"],
            bend["points_per_90"],
            bend["bezier_k"],
            bend["Euler_Rmax"],
            bend["Euler_Rmin"],
        )
        center_keys = _point_keys(center)
        for corner_index in (1, 2, 4, 5):
            _assert_corner_shape(
                center_keys, waypoints, corner_index, radius, bend_type, "Circular", bend
            )

        body_endpoint = pya.DPoint(-50.0, 30.0)
        target_y = -30.0
        route = _build_type3_opt1_route(
            body_endpoint,
            target_y,
            radius,
            bend["bend_type"],
            bend["points_per_90"],
            bend["bezier_k"],
            bend["Euler_Rmax"],
            bend["Euler_Rmin"],
            0.5,
            DBU,
        )
        route_waypoints = [
            body_endpoint,
            pya.DPoint(body_endpoint.x, target_y),
            pya.DPoint(body_endpoint.x - radius, target_y),
        ]
        _assert_corner_shape(
            _point_keys(route["points"]),
            route_waypoints,
            1,
            radius,
            bend_type,
            "Circular",
            bend,
        )
        last_dx = route["points"][-1].x - route["points"][-2].x
        last_dy = route["points"][-1].y - route["points"][-2].y
        if abs(last_dx + 0.010) > 1e-9 or abs(last_dy) > 1e-12:
            raise RuntimeError("type3 opt1 底部 Bend 后缺少严格 10 nm 水平端段。")


def _count_recursive(cell, layer_index):
    """递归统计指定图层的图形数量。"""
    count = 0
    iterator = cell.begin_shapes_rec(layer_index)
    while not iterator.at_end():
        count += 1
        iterator.next()
    return count


def _check_pinrec_directions(cell, layout, ports_type, geometry):
    """按实际 PinRec Path 点序验证 opt1/opt2 的严格水平朝向。"""
    pin_paths = []
    for shape in cell.shapes(layout.layer(PIN_LAYER)).each():
        if not shape.is_path():
            continue
        points = list(shape.path.each_point())
        if len(points) != 2:
            raise RuntimeError("PinRec Path 不是两点短路径。")
        pin_paths.append(points)
    if len(pin_paths) != 2:
        raise RuntimeError("%s 缺少两个 PinRec Path。" % ports_type)

    expected = (
        ("opt1", geometry["metric_points"][0], -1),
        (
            "opt2",
            geometry["metric_points"][-1],
            -1 if ports_type == "type1" else 1,
        ),
    )
    unused = list(pin_paths)
    for name, center, expected_dx_sign in expected:
        center_x = int(round(center.x / layout.dbu))
        center_y = int(round(center.y / layout.dbu))
        points = min(
            unused,
            key=lambda path: (
                path[0].x + path[1].x - 2 * center_x
            ) ** 2
            + (
                path[0].y + path[1].y - 2 * center_y
            ) ** 2,
        )
        unused.remove(points)
        midpoint_x = (points[0].x + points[1].x) // 2
        midpoint_y = (points[0].y + points[1].y) // 2
        dx = points[1].x - points[0].x
        dy = points[1].y - points[0].y
        if midpoint_x != center_x or midpoint_y != center_y:
            raise RuntimeError("%s PinRec 中心未与实际端口重合。" % name)
        if dy != 0 or dx * expected_dx_sign <= 0:
            expected_angle = 180 if expected_dx_sign < 0 else 0
            raise RuntimeError(
                "%s PinRec 点序方向不是严格 %d°。" % (name, expected_angle)
            )


def _create_variant(layout, params, x_offset, geometry):
    """创建 Spiral 变体，验证 PinRec 后返回平移实例。"""
    cell = layout.create_cell("Archimedean_Spiral", LIBRARY_NAME, params)
    if cell is None:
        raise RuntimeError("无法创建 Archimedean_Spiral PCell。")
    _check_pinrec_directions(cell, layout, params["ports_type"], geometry)
    _check_parameter_text(cell, layout, geometry)
    return pya.CellInstArray(cell.cell_index(), pya.Trans(x_offset, 0))


def _check_parameter_text(cell, layout, geometry):
    """验证三行 Spiral Text 的内容、类型专属半径字段和内孔安全边界。"""
    text_layer = layout.layer(TEXT_LAYER)
    text_shapes = [
        shape
        for shape in cell.each_shape(text_layer)
        if shape.is_text()
    ]
    if len(text_shapes) != 3:
        raise RuntimeError("Archimedean_Spiral 应生成 3 行参数 Text，实际为 %d 行。" % len(text_shapes))
    labels = [shape.text.string for shape in text_shapes]
    if not labels[0].startswith("Archimedean_Spiral | ports="):
        raise RuntimeError("Spiral Text 首行缺少器件与端口类型信息。")
    if not labels[1].startswith("w=") or "pitch=" not in labels[1]:
        raise RuntimeError("Spiral Text 第二行缺少宽度、间隙或 pitch 信息。")
    if not labels[2].startswith("L=") or "delta_L=" not in labels[2] or "Dout=" not in labels[2]:
        raise RuntimeError("Spiral Text 第三行缺少长度、delta_L 或 Dout 信息。")
    bend_type = geometry["bend_type"]
    if bend_type == "Circular" and "R=" not in labels[1]:
        raise RuntimeError("Circular Spiral Text 缺少 R 字段。")
    if bend_type == "Bezier" and not all(key in labels[1] for key in ("B=", "Rmax=", "Rmin=")):
        raise RuntimeError("Bezier Spiral Text 缺少 B、Rmax 或 Rmin 字段。")
    if bend_type == "Euler" and not all(key in labels[1] for key in ("Reff=", "Rmax=", "Rmin=")):
        raise RuntimeError("Euler Spiral Text 缺少 Reff、Rmax 或 Rmin 字段。")
    target_box = ArchimedeanSpiral._parameter_text_target_box(geometry, layout.dbu)
    for shape in text_shapes:
        bbox = shape.bbox()
        if (
            bbox.left < target_box.left
            or bbox.right > target_box.right
            or bbox.bottom < target_box.bottom
            or bbox.top > target_box.top
        ):
            raise RuntimeError("Spiral 参数 Text 超出中心安全区域。")

    _check_compact_display_text(geometry)


def _check_compact_display_text(geometry):
    """验证实例名称紧凑，同时不影响版图中的三行详细参数 Text。"""

    label = ArchimedeanSpiral._compact_display_text(geometry)
    expected_prefix = "Archimedean_Spiral(%s,%s,L=" % (
        geometry["ports_type"],
        geometry["bend_type"],
    )
    if not label.startswith(expected_prefix) or not label.endswith(")"):
        raise RuntimeError("Archimedean_Spiral 实例名称格式不正确：%s" % label)
    if not all(key in label for key in (",dL=", ",N=", ",w=", ",gap=")):
        raise RuntimeError("Archimedean_Spiral 实例名称缺少关键参数：%s" % label)
    if any(key in label for key in ("target=", "pitch=", "points/90=", "Dout=", " | ")):
        raise RuntimeError("Archimedean_Spiral 实例名称仍包含冗长版图 Text 字段：%s" % label)

    bend_type = geometry["bend_type"]
    if bend_type == "Circular" and ",R=" not in label:
        raise RuntimeError("Circular Archimedean_Spiral 实例名称缺少 R：%s" % label)
    if bend_type == "Bezier" and not all(key in label for key in (",R=", ",B=")):
        raise RuntimeError("Bezier Archimedean_Spiral 实例名称缺少 R 或 B：%s" % label)
    if bend_type == "Euler" and not all(key in label for key in (",Reff=", ",Rmax=", ",Rmin=")):
        raise RuntimeError("Euler Archimedean_Spiral 实例名称缺少派生半径：%s" % label)


def _check_geometry(bend_type, ports_type):
    """检查纯计算几何的端口语义和派生长度。"""
    geometry = calculate_spiral_geometry(
        1000.0,
        0.5,
        10.0,
        2.0,
        ports_type,
        bend_type,
        0.35,
        30.0,
        10.0,
        20.0,
        0.001,
    )
    if geometry["total_length"] + 0.001 < 1000.0:
        raise RuntimeError("%s/%s 的计算长度未达到目标值。" % (bend_type, ports_type))
    start = geometry["metric_points"][0]
    end = geometry["metric_points"][-1]
    expected_delta = geometry["total_length"] - abs(end.x - start.x)
    if abs(expected_delta - geometry["delta_L"]) > 1e-9:
        raise RuntimeError("%s/%s 的 delta_L 计算不一致。" % (bend_type, ports_type))
    if geometry["turns"] > 1:
        previous_length = geometry["previous_turn_length"]
        if previous_length is None or previous_length + 0.001 >= 1000.0:
            raise RuntimeError("%s/%s 未选择满足目标长度的最小圈数。" % (bend_type, ports_type))
    center = geometry["center_points"]
    if abs(center[0].x + geometry["arm_inner_radius"]) > 0.001:
        raise RuntimeError("中心连接器左端未与 Archimedean Spiral 内臂对齐。")
    if abs(center[-1].x - geometry["arm_inner_radius"]) > 0.001:
        raise RuntimeError("中心连接器右端未与 Archimedean Spiral 内臂对齐。")
    ten_nm_axis_segments = 0
    for index in range(1, len(center)):
        dx = abs(center[index].x - center[index - 1].x)
        dy = abs(center[index].y - center[index - 1].y)
        if (
            abs(math.hypot(dx, dy) - 0.010) <= 1e-9
            and (dx <= 1e-12 or dy <= 1e-12)
        ):
            ten_nm_axis_segments += 1
    if ten_nm_axis_segments < 8:
        raise RuntimeError("%s 中心四个 Bend 未保留完整 10 nm 端段。" % bend_type)
    if ports_type == "type1":
        # type1: 两端口均位于顶部，均朝左（180°）
        if not (start.y > 0.0 and end.y > 0.0):
            raise RuntimeError("type1 端口未位于同一侧（顶部）。")
        dx_start = geometry["metric_points"][0].x - geometry["metric_points"][1].x
        dx_end = geometry["metric_points"][-1].x - geometry["metric_points"][-2].x
        if not (dx_start < 0 and dx_end < 0):
            raise RuntimeError("type1 端口应朝 180°（向左）。")
    if ports_type == "type2":
        # type2: 直接使用螺旋臂天然错位端口，不允许额外 jog。
        if not (start.y > 0.0 and end.y < 0.0):
            raise RuntimeError(
                "type2: opt1 应在顶部(y>0), opt2 应在底部(y<0)。"
            )
        dx_start = geometry["metric_points"][0].x - geometry["metric_points"][1].x
        dx_end = geometry["metric_points"][-1].x - geometry["metric_points"][-2].x
        if not (dx_start < 0 and dx_end > 0):
            raise RuntimeError(
                "type2: opt1 应朝 180°(dx<0), opt2 应朝 0°(dx>0)。"
            )
        if geometry["type3_jog"] is not None:
            raise RuntimeError("type2 不得生成端口 jog。")
        if any(
            any(abs(segment[index].y - segment[0].y) > 1e-12 for index in range(1, len(segment)))
            for segment in geometry["port_segments"].values()
        ):
            raise RuntimeError("type2 端口 landing 必须保持严格水平。")
    if ports_type == "type3":
        # type3: 外侧 90° 由 Archimedean 左臂继续生成，底部 Bend 使用中心设置。
        dx_start = geometry["metric_points"][0].x - geometry["metric_points"][1].x
        dx_end = geometry["metric_points"][-1].x - geometry["metric_points"][-2].x
        if not (dx_start < 0 and dx_end > 0):
            raise RuntimeError(
                "type3: opt1 应朝 180°(dx<0), opt2 应朝 0°(dx>0)。"
            )
    if ports_type == "type2":
        # type2: 端口异侧、纵向错位。
        if abs(start.y - end.y) <= 0.001:
            raise RuntimeError("type2 端口应保持纵向错位。")
    if ports_type == "type3":
        # type3: opt1 外侧绕线后与 opt2 严格等高，垂直段边到边间距等于 gap。
        if abs(start.y - end.y) > 1e-12:
            raise RuntimeError(
                "type3: opt1 和 opt2 的 y 坐标未对齐（差值 %.6f um）。" % abs(start.y - end.y)
            )
        jog = geometry["type3_jog"]
        if jog is None:
            raise RuntimeError("type3 缺少 Paperclip 风格 opt1 绕线。")
        centerline_gap = jog["reference_min_x"] - jog["jog_x"]
        edge_gap = centerline_gap - geometry["wg_width"]
        if abs(edge_gap - geometry["gap"]) > 0.001:
            raise RuntimeError("type3 外侧垂直段边到边间距不等于 gap。")
        jog_points = jog["points"]
        has_vertical_straight = any(
            abs(jog_points[index].x - jog_points[index - 1].x) <= 1e-12
            and abs(jog_points[index].y - jog_points[index - 1].y) > 0.020
            for index in range(1, len(jog_points))
        )
        if not has_vertical_straight:
            raise RuntimeError("type3 Archimedean 外圈与底部 Bend 之间缺少竖直波导。")
        axis_ten_nm = sum(
            1
            for index in range(1, len(jog_points))
            if abs(
                math.hypot(
                    jog_points[index].x - jog_points[index - 1].x,
                    jog_points[index].y - jog_points[index - 1].y,
                )
                - 0.010
            )
            <= 1e-9
            and (
                abs(jog_points[index].x - jog_points[index - 1].x) <= 1e-12
                or abs(jog_points[index].y - jog_points[index - 1].y) <= 1e-12
            )
        )
        if axis_ten_nm < 3:
            raise RuntimeError("type3 opt1 底部未完整映射公共 90° Bend。")
        if geometry["theta_left"] - geometry["theta_base"] <= 0.5 * math.pi:
            raise RuntimeError("type3 外侧延伸段未继续生成完整 Archimedean 90°。")
        left_tangent = geometry["left_archimedean_tangent"]
        if abs(left_tangent.x) > 1e-9 or left_tangent.y >= 0.0:
            raise RuntimeError("type3 Archimedean 外圈终点切线未严格竖直向下。")
    _check_draw_segments(geometry, bend_type, ports_type)
    # 验证实际绘制的两端 10 nm 直波导。
    _check_port_straights(geometry, bend_type, ports_type)
    return geometry


def _check_draw_segments(geometry, bend_type, ports_type):
    """验证中心线分块点数和多点重叠连续性。"""
    segments = geometry["draw_segments"]
    if not segments or max(len(segment) for segment in segments) > 4000:
        raise RuntimeError("%s/%s: draw segment 超过 GDS 安全点数。" % (bend_type, ports_type))
    for index in range(1, len(segments)):
        overlap = min(24, len(segments[index - 1]), len(segments[index]))
        if segments[index - 1][-overlap:] != segments[index][:overlap]:
            raise RuntimeError("%s/%s: 相邻中心线分块没有保持多点重叠。" % (bend_type, ports_type))


def _check_port_straights(geometry, bend_type, ports_type):
    """验证 10 nm 最外侧边与宽度级水平 landing 均进入实际绘制。"""
    pts = geometry["metric_points"]
    first_dx = pts[1].x - pts[0].x
    first_dy = pts[1].y - pts[0].y
    last_dx = pts[-1].x - pts[-2].x
    last_dy = pts[-1].y - pts[-2].y
    if abs(first_dx - 0.010) > 1e-9 or abs(first_dy) > 1e-12:
        raise RuntimeError(
            "%s/%s: opt1 首段不是朝 +x 的严格 10 nm 水平波导。" % (bend_type, ports_type)
        )
    expected_last_dx = -0.010 if ports_type == "type1" else 0.010
    if abs(last_dx - expected_last_dx) > 1e-9 or abs(last_dy) > 1e-12:
        raise RuntimeError(
            "%s/%s: opt2 末段不是规定方向的严格 10 nm 水平波导。" % (bend_type, ports_type)
        )

    required_landing = geometry["port_landing_length"]
    start_run = 0.0
    for index in range(1, len(pts)):
        dx = pts[index].x - pts[index - 1].x
        dy = pts[index].y - pts[index - 1].y
        if abs(dy) > 1e-12:
            break
        start_run += abs(dx)
    end_run = 0.0
    for index in range(len(pts) - 1, 0, -1):
        dx = pts[index].x - pts[index - 1].x
        dy = pts[index].y - pts[index - 1].y
        if abs(dy) > 1e-12:
            break
        end_run += abs(dx)
    if start_run + DBU < required_landing or end_run + DBU < required_landing:
        raise RuntimeError(
            "%s/%s: 端口水平 landing 短于一个波导宽度。" % (bend_type, ports_type)
        )

    def _draw_has_edge(point1, point2):
        target = {
            (int(round(point1.x / 0.001)), int(round(point1.y / 0.001))),
            (int(round(point2.x / 0.001)), int(round(point2.y / 0.001))),
        }
        for segment in geometry["draw_segments"]:
            for index in range(1, len(segment)):
                edge = {
                    (int(round(segment[index - 1].x / 0.001)), int(round(segment[index - 1].y / 0.001))),
                    (int(round(segment[index].x / 0.001)), int(round(segment[index].y / 0.001))),
                }
                if edge == target:
                    return True
        return False

    if not _draw_has_edge(pts[0], pts[1]) or not _draw_has_edge(pts[-2], pts[-1]):
        raise RuntimeError("%s/%s: 10 nm 端段只存在于 metric，未写入 Si draw segment。" % (bend_type, ports_type))


def _check_physical_wide_port_landings():
    """用流片样例的 2 µm 宽波导验证 GDS 中物理 Si 端口严格为 0°。"""
    params = {
        "length": 7195.766,
        "wg_width": 2.0,
        "min_radius": 85.0,
        "gap": 4.0,
        "ports_type": "type3",
        "bend_type": "Circular",
        "bezier": 0.35,
        "Euler_Rmax": 30.0,
        "Euler_Rmin": 10.0,
        "vertical_stretch": 0.0,
    }
    geometry = calculate_spiral_geometry(
        params["length"],
        params["wg_width"],
        params["min_radius"],
        params["gap"],
        params["ports_type"],
        params["bend_type"],
        params["bezier"],
        params["Euler_Rmax"],
        params["Euler_Rmin"],
        params["vertical_stretch"],
        DBU,
    )
    if abs(geometry["port_landing_length"] - params["wg_width"]) > 1e-12:
        raise RuntimeError("宽波导端口 landing 未等于 wg_width。")

    layout = pya.Layout()
    layout.dbu = DBU
    cell = layout.create_cell("Archimedean_Spiral", LIBRARY_NAME, params)
    top = layout.create_cell("JNU_WIDE_PORT_REGRESSION")
    top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans()))
    output = Path(tempfile.gettempdir()) / "jnu_spiral_wide_port_regression.gds"
    try:
        layout.write(str(output))
        reread = pya.Layout()
        reread.read(str(output))
        reread_cell = reread.cell("JNU_WIDE_PORT_REGRESSION")
        if reread_cell is None:
            raise RuntimeError("宽波导端口 GDS 重读后缺少目标 cell。")
        region = pya.Region(reread_cell.begin_shapes_rec(reread.layer(SI_LAYER)))
        region.merge()
        width_dbu = int(round(params["wg_width"] / DBU))
        half_width = width_dbu // 2
        landing_dbu = int(round(geometry["port_landing_length"] / DBU))
        endpoints = (
            ("opt1", geometry["metric_points"][0], 1),
            ("opt2", geometry["metric_points"][-1], -1),
        )
        for name, endpoint, inward_sign in endpoints:
            x0 = int(round(endpoint.x / DBU))
            y0 = int(round(endpoint.y / DBU))
            for offset in (10, landing_dbu // 4, landing_dbu // 2, 3 * landing_dbu // 4):
                x = x0 + inward_sign * offset
                section = region & pya.Region(
                    pya.Box(x, y0 - width_dbu, x + 1, y0 + width_dbu)
                )
                bbox = section.bbox()
                if bbox.empty():
                    raise RuntimeError("%s 端口物理 Si 截面为空。" % name)
                if (
                    abs(bbox.bottom - (y0 - half_width)) > 1
                    or abs(bbox.top - (y0 + half_width)) > 1
                ):
                    raise RuntimeError(
                        "%s 距端口 %d nm 的物理 Si 截面不是严格 0°。" % (name, offset)
                    )

        pin_paths = []
        pin_iterator = reread_cell.begin_shapes_rec(reread.layer(PIN_LAYER))
        while not pin_iterator.at_end():
            shape = pin_iterator.shape()
            if shape.is_path():
                pin_paths.append(shape.path)
            pin_iterator.next()
        if len(pin_paths) != 2:
            raise RuntimeError("宽波导样例缺少两个 PinRec Path。")
        if any(
            list(path.each_point())[0].y != list(path.each_point())[-1].y
            for path in pin_paths
        ):
            raise RuntimeError("宽波导样例的 PinRec 方向发生回归。")
    finally:
        try:
            os.remove(str(output))
        except OSError:
            pass


def main():
    """执行 3×3 变体、vertical stretch 和 GDS 重读回归。"""
    _check_configurable_bend_regions()
    _check_physical_wide_port_landings()
    base = calculate_spiral_geometry(
        100.0, 0.5, 10.0, 2.0, "type3", "Circular", 0.35, 30.0, 10.0, 0.0, 0.001
    )
    stretched = calculate_spiral_geometry(
        100.0, 0.5, 10.0, 2.0, "type3", "Circular", 0.35, 30.0, 10.0, 20.0, 0.001
    )
    if stretched["total_length"] <= base["total_length"] + 39.999:
        raise RuntimeError("vertical_stretch 未按预期增加中心连接器长度。")

    long_geometry = calculate_spiral_geometry(
        7195.766, 0.5, 10.0, 2.0, "type3", "Circular", 0.35, 30.0, 10.0, 20.0, 0.001
    )
    if len(long_geometry["metric_points"]) <= 8191:
        raise RuntimeError("长 Spiral 样例未覆盖 GDS 单 Path 点数上限。")
    _check_draw_segments(long_geometry, "Circular", "type3-long")

    layout = pya.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("JNU_SPIRAL_REGRESSION")
    x_offset = 0
    variant_count = 0
    for bend_type in ("Circular", "Bezier", "Euler"):
        for ports_type in ("type1", "type2", "type3"):
            geometry = _check_geometry(bend_type, ports_type)
            params = {
                "length": 1000.0,
                "wg_width": 0.5,
                "min_radius": 10.0,
                "gap": 2.0,
                "ports_type": ports_type,
                "bend_type": bend_type,
                "bezier": 0.35,
                "Euler_Rmax": 30.0,
                "Euler_Rmin": 10.0,
                "vertical_stretch": 20.0,
            }
            top.insert(_create_variant(layout, params, x_offset, geometry))
            x_offset += int(round((2.0 * geometry["outer_radius"] + 100.0) / layout.dbu))
            variant_count += 1

    long_params = {
        "length": 7195.766,
        "wg_width": 0.5,
        "min_radius": 10.0,
        "gap": 2.0,
        "ports_type": "type3",
        "bend_type": "Circular",
        "bezier": 0.35,
        "Euler_Rmax": 30.0,
        "Euler_Rmin": 10.0,
        "vertical_stretch": 20.0,
    }
    top.insert(_create_variant(layout, long_params, x_offset, long_geometry))
    variant_count += 1

    output = Path(tempfile.gettempdir()) / "jnu_spiral_regression.gds"
    layout.write(str(output))
    reread = pya.Layout()
    reread.read(str(output))
    reread_top = reread.cell("JNU_SPIRAL_REGRESSION")
    if reread_top is None:
        raise RuntimeError("GDS 重读后缺少 Archimedean_Spiral 回归顶层 cell。")
    si_count = _count_recursive(reread_top, reread.layer(SI_LAYER))
    pin_count = _count_recursive(reread_top, reread.layer(PIN_LAYER))
    if si_count < variant_count:
        raise RuntimeError("Archimedean_Spiral Si 图形数量不足：%d" % si_count)
    if pin_count < variant_count * 4:
        raise RuntimeError("Archimedean_Spiral PinRec 图形数量不足：%d" % pin_count)
    merged_si = pya.Region(reread_top.begin_shapes_rec(reread.layer(SI_LAYER)))
    merged_si.merge()
    if merged_si.count() != variant_count:
        raise RuntimeError(
            "GDS 重读后存在断接：期望 %d 个连续 Spiral，实际 %d 个。"
            % (variant_count, merged_si.count())
        )
    print(
        "OK: variants=%d GDS=%s Si=%d PinRec=%d"
        % (variant_count, output, si_count, pin_count)
    )
    try:
        os.remove(str(output))
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
