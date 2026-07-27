# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

# JNU_MWP_PDK 的 S 弯波导 PCell。
# 曲线采样、曲率计算和波导边界均在本模块内完成，保证 JNU 工具可以独立运行。

import math
import os
import sys

import pya

try:
    from .pcell_defaults import default_choice, default_float, default_int, save_pcell_defaults
except ImportError:
    PCELL_DIR = os.path.dirname(os.path.abspath(__file__))
    if PCELL_DIR not in sys.path:
        sys.path.insert(0, PCELL_DIR)
    from pcell_defaults import default_choice, default_float, default_int, save_pcell_defaults

# 弯曲工具模块位于 tools 目录（在 JNU_MWP_PDK 根目录下）
PYMACROS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PYMACROS_DIR not in sys.path:
    sys.path.insert(0, PYMACROS_DIR)

from JNU_MWP_tools.core.bend_sampling import AUTO_SAMPLE_COUNT, effective_arc_points, effective_points_per_90
from JNU_MWP_tools.core.path_geometry import insert_centerline_polygons


SI_LAYER = pya.LayerInfo(1, 0)          # Si 波导实体层。
PIN_LAYER = pya.LayerInfo(1, 10)        # PinRec 端口识别层。
DEVREC_LAYER = pya.LayerInfo(68, 0)     # DevRec 器件识别层。
TEXT_LAYER = pya.LayerInfo(10, 0)       # Text 文字层。

PCELL_NAME = "S_Bend"
DEFAULT_WIDTH = 0.5
DEFAULT_HEIGHT = 3.0
DEFAULT_LENGTH = 30.0
DEFAULT_RADIUS = (DEFAULT_LENGTH * DEFAULT_LENGTH + DEFAULT_HEIGHT * DEFAULT_HEIGHT) / (4.0 * abs(DEFAULT_HEIGHT))
DEFAULT_DEVREC_WIDTH = 1.5
DEFAULT_NPOINTS = AUTO_SAMPLE_COUNT
DEFAULT_BEZIER = 0.35
BEZIER_RADIUS_SEARCH_SAMPLES = 512


def _ensure_tools_path():
    """保证 pymacros 父目录可用于导入分类后的工具子包。"""
    pymacros_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if pymacros_dir not in sys.path:
        sys.path.insert(0, pymacros_dir)


def _to_itype(value, dbu):
    """把微米单位转换为 KLayout 数据库整数单位。"""
    return int(round(float(value) / dbu))


def _distance(p1, p2):
    """计算两个 DPoint 之间的欧氏距离，单位为微米。"""
    return math.hypot(p2.x - p1.x, p2.y - p1.y)


def _dedupe_dpoints(points):
    """删除连续重复的 DPoint，避免生成零长度 path 段。"""
    clean = []
    for point in points:
        if not clean or _distance(clean[-1], point) > 1e-9:
            clean.append(point)
    return clean


def _dpoints_to_points(points, dbu):
    """把微米坐标中心线转换为数据库整数坐标中心线。"""
    converted = [
        pya.Point(_to_itype(point.x, dbu), _to_itype(point.y, dbu))
        for point in points
    ]
    clean = []
    for point in converted:
        if not clean or clean[-1] != point:
            clean.append(point)
    return clean


def _horizontalize_endpoint_tangents(points):
    """强制 S 弯首尾相邻段水平，保证波导端口与 PinRec 方向严格一致。"""
    clean = _dedupe_dpoints(points)
    if len(clean) < 2:
        return clean

    result = list(clean)

    # 起点 pin 为 180 度，要求进入 S 弯的第一段中心线严格水平。
    result[1] = pya.DPoint(result[1].x, result[0].y)

    # 终点 pin 为 0 度，要求离开 S 弯的最后一段中心线严格水平。
    if len(result) >= 2:
        result[-2] = pya.DPoint(result[-2].x, result[-1].y)

    return _dedupe_dpoints(result)


def _path_length_um(points):
    """计算 DPoint 中心线长度，单位为微米。"""
    length = 0.0
    for index in range(1, len(points)):
        length += _distance(points[index - 1], points[index])
    return length


def _circular_radius_from_length_height(length, height):
    """由 S 弯水平长度和垂直偏移反算圆弧半径。

    两段相反方向的等半径圆弧满足：
    L = 2 * R * sin(theta)
    |H| = 2 * R * (1 - cos(theta))
    因此 R = (L^2 + H^2) / (4|H|)。当 H=0 时没有弯曲，显示半径为 0。
    """
    length = max(0.001, float(length))
    height_abs = abs(float(height))
    if height_abs <= 1e-9:
        return 0.0
    return (length * length + height_abs * height_abs) / (4.0 * height_abs)


def _circular_metrics(length, height):
    """计算由 length/height 唯一确定的圆弧 S 弯长度、半径和圆心角。"""
    length = max(0.001, float(length))
    height_abs = abs(float(height))
    radius = _circular_radius_from_length_height(length, height)

    if height_abs <= 1e-9 or radius <= 0:
        return length, radius, 0.0

    argument = (radius - height_abs / 2.0) / radius
    argument = max(-1.0, min(1.0, argument))
    theta = math.acos(argument)
    return length, radius, theta


def _circular_sbend_centerline(length, height, radius, npoints, dbu=0.001):
    """生成圆弧 S 弯中心线。

    起点和终点切向都保持水平，因此 opt1/opt2 可以直接与水平波导或器件 pin 吸附。
    """
    sign = 1.0 if height >= 0 else -1.0
    height_abs = abs(float(height))
    actual_length, actual_radius, theta = _circular_metrics(length, height)

    if height_abs <= 1e-9 or theta <= 1e-12:
        points = [pya.DPoint(0, 0), pya.DPoint(actual_length, 0)]
        return points, actual_radius, actual_length

    try:
        manual_count = int(npoints)
    except Exception:
        manual_count = AUTO_SAMPLE_COUNT
    if manual_count > 0:
        samples = max(4, manual_count // 2)
    else:
        samples = effective_arc_points(AUTO_SAMPLE_COUNT, actual_radius, theta, dbu)
    points = [pya.DPoint(0, 0)]

    # 第一段圆弧：从水平切向逐渐转到中间切向角 theta。
    for index in range(1, samples + 1):
        angle = theta * index / samples
        x = actual_radius * math.sin(angle)
        y = actual_radius - actual_radius * math.cos(angle)
        points.append(pya.DPoint(x, sign * y))

    # 第二段圆弧：反向弯曲，把切向角带回水平。
    center2_x = 2.0 * actual_radius * math.sin(theta)
    center2_y = height_abs - actual_radius
    for index in range(1, samples + 1):
        angle = math.pi / 2.0 + theta - theta * index / samples
        x = center2_x + actual_radius * math.cos(angle)
        y = center2_y + actual_radius * math.sin(angle)
        points.append(pya.DPoint(x, sign * y))

    points.append(pya.DPoint(actual_length, float(height)))
    return _dedupe_dpoints(points), actual_radius, _path_length_um(points)


def _coerce_bezier(bezier):
    """约束 Bezier 控制系数，避免控制点退化或过度回绕。"""
    return max(0.05, min(0.95, float(bezier)))


def _bezier_control_points(length, height, bezier):
    """生成两端切线均水平的 S 弯 Bezier 控制点。

    B 直接表示第二控制点的归一化水平坐标：P2.x=B*L；第一控制点
    关于中点对称，P1.x=(1-B)*L。该定义使界面输入值与实际几何严格一致，
    不再进行 1-B 互补显示或端点欧氏距离缩放。
    """
    bezier = _coerce_bezier(bezier)
    length = float(length)
    p0 = pya.DPoint(0, 0)
    p1 = pya.DPoint((1.0 - bezier) * length, 0)
    p2 = pya.DPoint(bezier * length, float(height))
    p3 = pya.DPoint(length, float(height))
    return p0, p1, p2, p3


def _bezier_point(length, height, bezier, t):
    """三次 Bezier S 弯采样点。

    两端切向均为水平；B 越小，两端控制手柄越长。
    """
    p0, p1, p2, p3 = _bezier_control_points(length, height, bezier)
    u = 1.0 - t
    return (
        p0 * (u ** 3)
        + p1 * (3.0 * u * u * t)
        + p2 * (3.0 * u * t * t)
        + p3 * (t ** 3)
    )


def _bezier_derivatives(length, height, bezier, t):
    """计算三次 Bezier 中心线在参数 t 处的一阶、二阶导数。"""
    p0, p1, p2, p3 = _bezier_control_points(length, height, bezier)
    u = 1.0 - t

    dx = (
        3.0 * u * u * (p1.x - p0.x)
        + 6.0 * u * t * (p2.x - p1.x)
        + 3.0 * t * t * (p3.x - p2.x)
    )
    dy = (
        3.0 * u * u * (p1.y - p0.y)
        + 6.0 * u * t * (p2.y - p1.y)
        + 3.0 * t * t * (p3.y - p2.y)
    )
    ddx = (
        6.0 * u * (p2.x - 2.0 * p1.x + p0.x)
        + 6.0 * t * (p3.x - 2.0 * p2.x + p1.x)
    )
    ddy = (
        6.0 * u * (p2.y - 2.0 * p1.y + p0.y)
        + 6.0 * t * (p3.y - 2.0 * p2.y + p1.y)
    )
    return dx, dy, ddx, ddy


def _bezier_curvature(length, height, bezier, t):
    """用解析曲率公式计算 Bezier 中心线曲率。"""
    dx, dy, ddx, ddy = _bezier_derivatives(length, height, bezier, t)
    cross = abs(dx * ddy - dy * ddx)
    speed2 = dx * dx + dy * dy
    if cross <= 1e-15 or speed2 <= 1e-15:
        return 0.0
    return cross / (speed2 ** 1.5)


def _refine_bezier_curvature_max(length, height, bezier, left, right):
    """在一个小区间内用三分搜索细化最大曲率位置。"""
    left = max(0.0, float(left))
    right = min(1.0, float(right))
    if right <= left:
        curvature = _bezier_curvature(length, height, bezier, left)
        return left, curvature

    for _index in range(70):
        span = right - left
        mid1 = left + span / 3.0
        mid2 = right - span / 3.0
        if _bezier_curvature(length, height, bezier, mid1) < _bezier_curvature(
            length,
            height,
            bezier,
            mid2,
        ):
            left = mid1
        else:
            right = mid2

    mid = (left + right) / 2.0
    candidates = [
        (left, _bezier_curvature(length, height, bezier, left)),
        (mid, _bezier_curvature(length, height, bezier, mid)),
        (right, _bezier_curvature(length, height, bezier, right)),
    ]
    return max(candidates, key=lambda item: item[1])


def _bezier_minimum_radius(length, height, bezier):
    """求 Bezier S 弯中心线的最小曲率半径。

    这里使用解析曲率公式，而不是离散三点外接圆估算。先粗扫曲率峰值，
    再在峰值附近细化；端点曲率也纳入候选，避免小 bezier 参数时低估曲率。
    """
    length = max(0.001, float(length))
    height = float(height)
    if abs(height) <= 1e-12:
        return 0.0

    bezier = _coerce_bezier(bezier)
    samples = BEZIER_RADIUS_SEARCH_SAMPLES
    step = 1.0 / samples
    curvatures = [
        _bezier_curvature(length, height, bezier, index * step)
        for index in range(samples + 1)
    ]

    candidate_indices = {0, samples}
    for index in range(1, samples):
        if curvatures[index] >= curvatures[index - 1] and curvatures[index] >= curvatures[index + 1]:
            candidate_indices.add(index)
    candidate_indices.add(max(range(samples + 1), key=lambda index: curvatures[index]))

    best_curvature = 0.0
    for index in candidate_indices:
        left = (index - 2) * step
        right = (index + 2) * step
        _t, curvature = _refine_bezier_curvature_max(
            length,
            height,
            bezier,
            left,
            right,
        )
        best_curvature = max(best_curvature, curvature)

    return 1.0 / best_curvature if best_curvature > 0 else 0.0


def _radius_from_three_points(p0, p1, p2):
    """用三点外接圆估算局部曲率半径。"""
    a = _distance(p1, p2)
    b = _distance(p0, p2)
    c = _distance(p0, p1)
    area2 = abs(
        (p1.x - p0.x) * (p2.y - p0.y)
        - (p1.y - p0.y) * (p2.x - p0.x)
    )
    if area2 <= 1e-12 or a <= 1e-12 or b <= 1e-12 or c <= 1e-12:
        return None
    return a * b * c / (2.0 * area2)


def _minimum_effective_radius(points):
    """通过离散采样点估算 Bezier S 弯的最小等效半径。"""
    min_radius = None
    for index in range(1, len(points) - 1):
        radius = _radius_from_three_points(
            points[index - 1],
            points[index],
            points[index + 1],
        )
        if radius is None:
            continue
        if min_radius is None or radius < min_radius:
            min_radius = radius
    return min_radius or 0.0


def _bezier_sbend_centerline(length, height, npoints, bezier=DEFAULT_BEZIER, dbu=0.001):
    """生成 Bezier S 弯中心线，并返回最小等效半径和长度。"""
    length = max(0.001, float(length))
    height = float(height)
    bezier = _coerce_bezier(bezier)
    min_radius = _bezier_minimum_radius(length, height, bezier)
    try:
        manual_count = int(npoints)
    except Exception:
        manual_count = AUTO_SAMPLE_COUNT
    auto_samples = max(8, effective_points_per_90(AUTO_SAMPLE_COUNT, min_radius, dbu) * 2)
    samples = max(8, manual_count)
    if manual_count <= 0:
        samples = auto_samples
    points = [
        _bezier_point(length, height, bezier, index / samples)
        for index in range(samples + 1)
    ]
    points = _dedupe_dpoints(points)
    return points, min_radius, _path_length_um(points)


def _sbend_geometry(length, height, radius, bend_type, npoints, bezier=DEFAULT_BEZIER, dbu=0.001):
    """根据弯曲类型生成 S 弯中心线、显示半径和实际长度。"""
    if str(bend_type).lower() == "bezier":
        return _bezier_sbend_centerline(length, height, npoints, bezier, dbu)
    return _circular_sbend_centerline(length, height, radius, npoints, dbu)


def _display_radius(length, height, bend_type, npoints, bezier=DEFAULT_BEZIER, dbu=0.001):
    """计算 GUI 中只读显示的弯曲半径。"""
    if str(bend_type).lower() == "bezier":
        return _bezier_minimum_radius(length, height, bezier)
    return _circular_radius_from_length_height(length, height)


def _adaptive_npoints(length, height, bend_type, bezier=DEFAULT_BEZIER, dbu=0.001):
    """根据当前 S 弯几何计算 GUI 中显示的自适应采样点数。"""

    if str(bend_type).lower() == "bezier":
        radius = _bezier_minimum_radius(length, height, bezier)
        return max(8, effective_points_per_90(AUTO_SAMPLE_COUNT, radius, dbu) * 2)

    _actual_length, actual_radius, theta = _circular_metrics(length, height)
    return max(8, effective_arc_points(AUTO_SAMPLE_COUNT, actual_radius, theta, dbu) * 2)


def _offset_centerline(points, offset_start, offset_end=None):
    """沿中心线法向偏移生成 S 弯波导的单侧边界点。

    offset_start/offset_end 单位为微米；当两端宽度相同时二者相等。
    端点会被拉回 Manhattan 方向，避免端口边界出现斜切。
    """
    if offset_end is None:
        offset_end = offset_start
    if len(points) < 2:
        return list(points)

    cumulative = [0.0]
    for index in range(1, len(points)):
        cumulative.append(cumulative[-1] + _distance(points[index - 1], points[index]))
    total = cumulative[-1] or 1.0

    shifted = []
    for index, point in enumerate(points):
        if index == 0:
            tangent = points[1] - points[0]
        elif index == len(points) - 1:
            tangent = points[-1] - points[-2]
        else:
            tangent = points[index + 1] - points[index - 1]

        tangent_len = math.hypot(tangent.x, tangent.y)
        if tangent_len <= 1e-12:
            shifted.append(pya.DPoint(point.x, point.y))
            continue

        fraction = cumulative[index] / total
        offset = (1.0 - fraction) * offset_start + fraction * offset_end
        shifted.append(
            pya.DPoint(
                point.x - tangent.y / tangent_len * offset,
                point.y + tangent.x / tangent_len * offset,
            )
        )

    # 将首末边界点投影回端口截面，确保两端面严格保持 Manhattan。
    if abs(shifted[0].x - points[0].x) > abs(shifted[0].y - points[0].y):
        shifted[0].y = points[0].y
    else:
        shifted[0].x = points[0].x
    if abs(shifted[-1].x - points[-1].x) > abs(shifted[-1].y - points[-1].y):
        shifted[-1].y = points[-1].y
    else:
        shifted[-1].x = points[-1].x

    return shifted


def _bezier_waveguide_polygon(points, width):
    """将 Bezier S 弯中心线按波导宽度展开为 DPolygon。"""
    half_width = float(width) / 2.0
    upper = _offset_centerline(points, half_width)
    lower = _offset_centerline(points, -half_width)
    return pya.DPolygon(upper + list(reversed(lower)))


def draw_s_bend_geometry(
    cell,
    layout,
    width,
    height,
    length,
    radius,
    bend_type,
    npoints,
    bezier=DEFAULT_BEZIER,
):
    """绘制 S 弯波导，并返回 (实际长度, 显示半径)。"""
    dpoints, display_radius, actual_length = _sbend_geometry(
        length,
        height,
        radius,
        bend_type,
        npoints,
        bezier,
        layout.dbu,
    )
    dpoints = _horizontalize_endpoint_tangents(dpoints)
    actual_length = _path_length_um(dpoints)
    centerline = _dpoints_to_points(dpoints, layout.dbu)
    if len(centerline) < 2:
        return 0.0, 0.0

    width_dbu = max(1, _to_itype(width, layout.dbu))
    devrec_width_dbu = max(width_dbu, _to_itype(DEFAULT_DEVREC_WIDTH, layout.dbu))

    si_layer = layout.layer(SI_LAYER)
    devrec_layer = layout.layer(DEVREC_LAYER)
    pin_layer = layout.layer(PIN_LAYER)
    text_layer = layout.layer(TEXT_LAYER)

    # Bezier S 弯继续使用法向偏移边界，以保持现有端面和边界形状；
    # Circular S 弯把中心线扫掠结果规范化为 Polygon。
    if str(bend_type).lower() == "bezier":
        si_polygon = _bezier_waveguide_polygon(dpoints, width)
        cell.shapes(si_layer).insert(si_polygon.to_itype(layout.dbu))
    else:
        insert_centerline_polygons(cell, si_layer, centerline, width_dbu)

    # 1/99 不再保存可见中心线；DevRec 仅写入扫掠后的 Polygon。
    insert_centerline_polygons(cell, devrec_layer, centerline, devrec_width_dbu)

    # S 弯两端切向均为水平：左端朝 180 度，右端朝 0 度。
    _ensure_tools_path()
    from JNU_MWP_tools.core.make_pin import make_pin

    make_pin(cell, "opt1", centerline[0], width_dbu, pin_layer, 180)
    make_pin(cell, "opt2", centerline[-1], width_dbu, pin_layer, 0)

    # 在 Text 层显示关键参数；Bezier 的 radius 是离散曲率估算得到的等效最小半径。
    mid = centerline[len(centerline) // 2]
    if str(bend_type).lower() == "bezier":
        label = (
            "S_Bend type=%s width=%.3fum height=%.3fum bezier=%.3f radius=%.3fum length=%.3fum"
            % (bend_type, width, height, _coerce_bezier(bezier), display_radius, actual_length)
        )
    else:
        label = (
            "S_Bend type=%s width=%.3fum height=%.3fum radius=%.3fum length=%.3fum"
            % (bend_type, width, height, display_radius, actual_length)
        )

    text = pya.Text(label, pya.Trans(pya.Trans.R0, mid.x, mid.y))
    shape = cell.shapes(text_layer).insert(text)
    shape.text_dsize = max(0.1, float(width) * 0.5)
    shape.text_halign = 1
    shape.text_valign = 1

    return actual_length, display_radius


class SBendWaveguide(pya.PCellDeclarationHelper):
    """JNU S 弯波导 PCell，支持圆弧版和 Bezier 版。"""

    def __init__(self):
        super(SBendWaveguide, self).__init__()

        width_default = default_float(PCELL_NAME, "width", DEFAULT_WIDTH)
        height_default = default_float(PCELL_NAME, "height", DEFAULT_HEIGHT)
        length_default = default_float(PCELL_NAME, "length", DEFAULT_LENGTH)
        bend_type_default = default_choice(
            PCELL_NAME,
            "bend_type",
            "Circular",
            ("Circular", "Bezier"),
        )
        bezier_default = _coerce_bezier(default_float(PCELL_NAME, "bezier", DEFAULT_BEZIER))
        npoints_default = _adaptive_npoints(
            length_default,
            height_default,
            bend_type_default,
            bezier_default,
        )
        radius_default = _display_radius(
            length_default,
            height_default,
            bend_type_default,
            npoints_default,
            bezier_default,
        )

        self.param(
            "width",
            self.TypeDouble,
            "Waveguide width",
            unit="um",
            default=width_default,
        )
        self.param(
            "height",
            self.TypeDouble,
            "Offset height",
            unit="um",
            default=height_default,
        )
        self.param(
            "length",
            self.TypeDouble,
            "Horizontal length",
            unit="um",
            default=length_default,
        )
        # 先显示弯曲类型，再根据类型动态显示 Bezier 控制参数。
        bend_param = self.param(
            "bend_type",
            self.TypeList,
            "Bend type",
            default=bend_type_default,
        )
        bend_param.add_choice("Circular", "Circular")
        bend_param.add_choice("Bezier", "Bezier")
        self.bezier_param = self.param(
            "bezier",
            self.TypeDouble,
            "Bezier control",
            default=bezier_default,
        )
        try:
            self.bezier_param.hidden = bend_type_default != "Bezier"
        except Exception:
            pass

        # 只读派生参数统一放在全部可编辑参数之后。
        self.param(
            "radius",
            self.TypeDouble,
            "Bend radius (calculated) [uneditable]",
            unit="um",
            default=radius_default,
            readonly=True,
        )

        # Bezier S 弯曲率参数（只读显示）
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

        self.param(
            "npoints",
            self.TypeInt,
            "Curve sample points [uneditable]",
            default=npoints_default,
            readonly=True,
        )

    def _update_parameter_visibility(self):
        """根据当前 bend_type 设置 Bezier 参数的初始显示状态。"""
        try:
            self.bezier_param.hidden = str(self.bend_type).lower() != "bezier"
        except Exception:
            pass

    def _parameter_index(self, parameter_name):
        """按参数名查找 PCell 参数在 states 列表中的位置。"""
        for index, declaration in enumerate(self.get_parameters()):
            try:
                name = declaration.name() if callable(declaration.name) else declaration.name
            except Exception:
                name = ""
            if name == parameter_name:
                return index
        return None

    def _state_value(self, state):
        """兼容读取 PCellParameterState.value 的属性/方法形式。"""
        try:
            value = state.value
            return value() if callable(value) else value
        except Exception:
            return None

    def _set_bezier_state_visible(self, bend_state, bezier_state):
        """在 GUI 参数状态对象上切换 Bezier 参数栏显示状态。"""
        bend_value = self._state_value(bend_state)
        if bend_value is None:
            bend_value = bend_state

        visible = str(bend_value).lower() == "bezier"
        try:
            bezier_state.visible = visible
        except Exception:
            pass

    def _set_state_value(self, state, value):
        """写入 GUI 参数状态，不同 KLayout 版本失败时静默跳过。"""

        try:
            state.value = value
            return True
        except Exception:
            return False

    def _numeric_state_value(self, state, default):
        """从 GUI 参数状态对象读取浮点值，失败时使用默认值。"""
        value = self._state_value(state)
        try:
            return float(value)
        except Exception:
            return float(default)

    def _integer_state_value(self, state, default):
        """从 GUI 参数状态对象读取整数值，失败时使用默认值。"""
        value = self._state_value(state)
        try:
            return int(value)
        except Exception:
            return int(default)

    def _update_radius_state_value(self, radius_state):
        """根据当前 GUI 参数实时刷新只读弯曲半径显示值。"""
        bend_type = self._state_value(self.bend_type)
        if bend_type is None:
            bend_type = "Circular"

        radius = _display_radius(
            self._numeric_state_value(self.length, DEFAULT_LENGTH),
            self._numeric_state_value(self.height, DEFAULT_HEIGHT),
            bend_type,
            max(0, self._integer_state_value(self.npoints, DEFAULT_NPOINTS)),
            self._numeric_state_value(self.bezier, DEFAULT_BEZIER),
        )

        try:
            radius_state.value = radius
            radius_state.readonly = True
        except Exception:
            pass

    def _update_npoints_state_value(self, npoints_state):
        """根据当前 S 弯几何刷新自适应采样点数。"""

        bend_type = self._state_value(self.bend_type)
        if bend_type is None:
            bend_type = "Circular"
        dbu = getattr(self, "_jnu_callback_dbu", 0.001)
        auto_npoints = _adaptive_npoints(
            self._numeric_state_value(self.length, DEFAULT_LENGTH),
            self._numeric_state_value(self.height, DEFAULT_HEIGHT),
            bend_type,
            self._numeric_state_value(self.bezier, DEFAULT_BEZIER),
            dbu,
        )
        self._set_state_value(npoints_state, auto_npoints)

    def callback(self, layout, name, states):
        """保持 PCellDeclarationHelper 的标准状态绑定，再转入 callback_impl。"""
        try:
            self._jnu_callback_dbu = layout.dbu
        except Exception:
            self._jnu_callback_dbu = 0.001
        return super(SBendWaveguide, self).callback(layout, name, states)

    def callback_impl(self, name):
        """用户切换 bend_type 时，刷新 Bezier 参数显示状态。"""
        try:
            # 在 PCellDeclarationHelper 的 callback_impl 里，self.bend_type/self.bezier
            # 是 GUI 的 PCellParameterState，而不是普通参数值。
            self._set_bezier_state_visible(self.bend_type, self.bezier)

            # 设置 Bezier_Rmax/Rmin 可见性
            bend_value = self._state_value(self.bend_type)
            is_bezier = str(bend_value).lower() == "bezier" if bend_value is not None else False
            try:
                self.Bezier_Rmax.visible = is_bezier
                self.Bezier_Rmin.visible = is_bezier
            except Exception:
                pass

            if name != "npoints":
                self._update_npoints_state_value(self.npoints)
            self._update_radius_state_value(self.radius)
        except Exception:
            self._update_parameter_visibility()

    def display_text_impl(self):
        """在 Library/Instance 面板中显示全部用户参数（排除弯曲点数、波导层）。"""
        _, display_radius, actual_length = _sbend_geometry(
            self.length, self.height, self.radius,
            self.bend_type, self.npoints, self.bezier,
        )
        if str(self.bend_type).lower() == "bezier":
            return "S_Bend_%s_w%.3f_h%.3f_len%.3f_B%.3f_R%.3f_L%.3f" % (
                self.bend_type, self.width, self.height, self.length,
                _coerce_bezier(self.bezier), display_radius, actual_length,
            )
        return "S_Bend_%s_w%.3f_h%.3f_len%.3f_R%.3f_L%.3f" % (
            self.bend_type, self.width, self.height, self.length,
            display_radius, actual_length,
        )

    def coerce_parameters_impl(self):
        """约束参数，避免生成零长度或无效半径的 S 弯，并更新曲率参数。"""
        self.width = max(0.001, float(self.width))
        self.height = float(self.height)
        self.length = max(0.001, float(self.length))
        if str(self.bend_type).lower() != "bezier":
            self.bend_type = "Circular"
        else:
            self.bend_type = "Bezier"
        self.bezier = _coerce_bezier(self.bezier)
        try:
            self.npoints = max(0, int(self.npoints))
        except Exception:
            self.npoints = DEFAULT_NPOINTS
        if self.npoints <= 0:
            self.npoints = _adaptive_npoints(
                self.length,
                self.height,
                self.bend_type,
                self.bezier,
                self.layout.dbu,
            )
        self.radius = _display_radius(
            self.length,
            self.height,
            self.bend_type,
            self.npoints,
            self.bezier,
        )

        # 计算并更新 Bezier 曲率参数
        if self.bend_type == "Bezier":
            # Rmin 使用已有的解析曲率计算
            self.Bezier_Rmin = _bezier_minimum_radius(self.length, self.height, self.bezier)
            # Rmax 使用端点曲率估算（端点曲率最小，对应最大半径）
            endpoint_curvature = _bezier_curvature(self.length, self.height, self.bezier, 0.0)
            if endpoint_curvature > 1e-12:
                self.Bezier_Rmax = 1.0 / endpoint_curvature
            else:
                self.Bezier_Rmax = 0.0

        self._update_parameter_visibility()
        save_pcell_defaults(
            self,
            PCELL_NAME,
            ["width", "height", "length", "bend_type", "bezier"],
        )

    def produce_impl(self):
        """根据参数绘制 S 弯波导实体、引导路径、DevRec、PinRec 和文字标注。"""
        self.actual_length, self.effective_radius = draw_s_bend_geometry(
            self.cell,
            self.layout,
            self.width,
            self.height,
            self.length,
            self.radius,
            self.bend_type,
            self.npoints,
            self.bezier,
        )


__all__ = ["SBendWaveguide", "draw_s_bend_geometry"]
