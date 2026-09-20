# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""90° 弯曲波导 PCell。

支持 Circular、Bezier、Euler 三种弯曲类型。
Bezier 和 Euler 弯曲显示曲率半径参数。

参考文献：
- Bezier: Bahadori M, et al. JLT 2019
- Euler: Jiang X, et al. Optics Express 2018
"""

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

from JNU_MWP_tools.core.bend_sampling import AUTO_SAMPLE_COUNT, effective_points_per_90, points_per_90
from JNU_MWP_tools.core.bend_curvature import bezier_Rmax_Rmin, euler_Reff, euler_curve_points
from JNU_MWP_tools.core.path_geometry import insert_centerline_polygons


SI_LAYER = pya.LayerInfo(1, 0)
WG_LAYER = pya.LayerInfo(1, 99)
PIN_LAYER = pya.LayerInfo(1, 10)
DEVREC_LAYER = pya.LayerInfo(68, 0)
TEXT_LAYER = pya.LayerInfo(10, 0)

PCELL_NAME = "Bend_90deg"
BEND_TYPE_CHOICES = ("Circular", "Bezier", "Euler")
DEFAULT_WIDTH = 0.5
DEFAULT_RADIUS = 10.0
DEFAULT_BEZIER_K = 0.35
DEFAULT_EULER_RMAX = 30.0
DEFAULT_EULER_RMIN = 10.0
DEFAULT_POINTS_PER_90 = AUTO_SAMPLE_COUNT
PORT_STRAIGHT_UM = 0.010


def _normalize_bend_type(value):
    """把弯曲类型归一到当前支持的标准名称。"""
    text = str(value).strip().lower()
    if text == "bezier":
        return "Bezier"
    if text == "euler":
        return "Euler"
    return "Circular"


def _coerce_bezier(value):
    """限制 Bezier 控制参数，避免控制点退化。"""
    return max(0.05, min(0.95, float(value)))


def _ensure_tools_path():
    """保证 pymacros 父目录可用于导入分类后的工具子包。"""
    pymacros_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if pymacros_dir not in sys.path:
        sys.path.insert(0, pymacros_dir)


def _to_itype(value, dbu):
    """把微米单位转换为 KLayout 数据库整数单位。"""
    return int(round(float(value) / dbu))


def _with_port_straights(points, radius, straight_length=PORT_STRAIGHT_UM):
    """在弯曲盒内固定加入首尾轴向直段，并清理逆序或重合采样点。"""
    radius = float(radius)
    straight_length = float(straight_length)
    if radius <= straight_length:
        raise ValueError("弯曲半径必须大于端口直段长度 %.3f um。" % straight_length)

    eps = 1e-12
    cleaned = [(0.0, 0.0), (straight_length, 0.0)]
    last_x, last_y = cleaned[-1]
    for raw_x, raw_y in list(points)[1:-1]:
        x = float(raw_x)
        y = float(raw_y)
        if x <= straight_length + eps or y >= radius - straight_length - eps:
            continue
        if x < last_x - eps or y < last_y - eps:
            continue
        if x > radius + eps or y < -eps:
            continue
        if abs(x - last_x) <= eps and abs(y - last_y) <= eps:
            continue
        cleaned.append((x, y))
        last_x, last_y = x, y

    exit_start = (radius, radius - straight_length)
    if (
        abs(cleaned[-1][0] - exit_start[0]) > eps
        or abs(cleaned[-1][1] - exit_start[1]) > eps
    ):
        cleaned.append(exit_start)
    cleaned.append((radius, radius))
    return cleaned


def corner_points_circular(radius, samples):
    """生成标准 90 度圆弧弯曲的局部中心线点（公共 API）。

    返回从 (0,0) 到 (radius, radius) 的局部坐标采样点列。
    """
    samples = max(2, int(samples))
    pts = []
    for idx in range(samples + 1):
        angle = -math.pi / 2 + (math.pi / 2) * idx / samples
        x = radius * math.cos(angle)
        y = radius + radius * math.sin(angle)
        pts.append((x, y))
    pts[0] = (0.0, 0.0)
    pts[-1] = (radius, radius)
    return _with_port_straights(pts, radius)


def corner_points_bezier(radius, samples, k=DEFAULT_BEZIER_K):
    """生成标准 90 度 Bezier 弯曲的局部中心线点（公共 API）。

    控制点（Bahadori 论文标准对称配置）：
    - P0 = (0, 0)
    - P1 = (R0*(1-k), 0)
    - P2 = (R0, R0*k)
    - P3 = (R0, R0)

    返回从 (0,0) 到 (radius, radius) 的局部坐标采样点列。
    """
    samples = max(2, int(samples))
    L = radius
    xp = [0.0, (1 - k) * L, L, L]
    yp = [0.0, 0.0, k * L, L]

    xA = xp[3] - 3 * xp[2] + 3 * xp[1] - xp[0]
    xB = 3 * xp[2] - 6 * xp[1] + 3 * xp[0]
    xC = 3 * xp[1] - 3 * xp[0]
    xD = xp[0]

    yA = yp[3] - 3 * yp[2] + 3 * yp[1] - yp[0]
    yB = 3 * yp[2] - 6 * yp[1] + 3 * yp[0]
    yC = 3 * yp[1] - 3 * yp[0]
    yD = yp[0]

    pts = []
    for idx in range(samples + 1):
        t = idx / samples
        x = t**3 * xA + t**2 * xB + t * xC + xD
        y = t**3 * yA + t**2 * yB + t * yC + yD
        pts.append((x, y))

    pts[0] = (0.0, 0.0)
    pts[-1] = (radius, radius)
    return _with_port_straights(pts, radius)


def corner_points_euler(radius, samples, R_max=DEFAULT_EULER_RMAX, R_min=DEFAULT_EULER_RMIN):
    """生成标准 90 度 Euler 弯曲的局部中心线点（公共 API）。

    使用改进型 Euler 曲线：曲率沿弧长线性分布。
    将 Euler 曲线缩放到 radius × radius 的弯曲盒中。

    返回从 (0,0) 到 (radius, radius) 的局部坐标采样点列。
    """
    samples = max(2, int(samples))
    pts_list = euler_curve_points(R_max, R_min, math.pi / 2, max(10, samples // 2))

    if len(pts_list) < 2:
        return _with_port_straights([(0.0, 0.0), (radius, radius)], radius)

    x_end = pts_list[-1][0]
    scale = radius / x_end if x_end > 1e-9 else 1.0
    scaled = [(px * scale, py * scale) for px, py in pts_list]
    scaled[0] = (0.0, 0.0)
    scaled[-1] = (radius, radius)
    return _with_port_straights(scaled, radius)


def corner_points(radius, bend_type, npoints=64, bezier_k=DEFAULT_BEZIER_K, euler_Rmax=DEFAULT_EULER_RMAX, euler_Rmin=DEFAULT_EULER_RMIN):
    """根据弯曲类型生成标准局部拐角中心线（公共 API）。

    返回从 (0,0) 到 (radius, radius) 的局部坐标采样点列。
    waveguide.py 和 paperclip 等模块应通过此函数获取弯曲点列。
    """
    bend_key = str(bend_type).lower()
    if bend_key == "bezier":
        return corner_points_bezier(radius, npoints, bezier_k)
    if bend_key == "euler":
        return corner_points_euler(radius, npoints, euler_Rmax, euler_Rmin)
    return corner_points_circular(radius, npoints)


def calculate_bend_derived(radius, bend_type, bezier_k, euler_Rmax, euler_Rmin, dbu=0.001):
    """纯计算 Bend 派生值，供 coerce 与 GUI callback 共用。"""
    bend_type = _normalize_bend_type(bend_type)
    radius = max(float(dbu), float(radius))
    bezier_k = _coerce_bezier(bezier_k)
    euler_Rmax = max(float(dbu), float(euler_Rmax))
    euler_Rmin = max(float(dbu), float(euler_Rmin))
    if euler_Rmin >= euler_Rmax:
        raise ValueError("Euler Rmin 必须小于 Euler Rmax。")

    effective_radius = (
        euler_Reff(euler_Rmax, euler_Rmin)
        if bend_type == "Euler"
        else radius
    )
    if effective_radius <= PORT_STRAIGHT_UM:
        raise ValueError("有效弯曲半径必须大于 %.3f um。" % PORT_STRAIGHT_UM)
    point_count = max(4, points_per_90(effective_radius, dbu))
    bezier_rmax = bezier_rmin = None
    euler_reff = None
    if bend_type == "Bezier":
        bezier_rmax, bezier_rmin = bezier_Rmax_Rmin(radius, bezier_k)
    elif bend_type == "Euler":
        euler_reff = effective_radius

    pts = corner_points(
        effective_radius,
        bend_type,
        point_count,
        bezier_k,
        euler_Rmax,
        euler_Rmin,
    )
    bend_length = sum(
        math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
        for i in range(1, len(pts))
    )
    return {
        "bend_type": bend_type,
        "radius": radius,
        "bezier_k": bezier_k,
        "Euler_Rmax": euler_Rmax,
        "Euler_Rmin": euler_Rmin,
        "effective_radius": effective_radius,
        "points_per_90": point_count,
        "Bezier_Rmax": bezier_rmax,
        "Bezier_Rmin": bezier_rmin,
        "Euler_Reff": euler_reff,
        "bend_length": bend_length,
    }


class Bend90deg(pya.PCellDeclarationHelper):
    """90° 弯曲波导 PCell。"""

    def __init__(self):
        super(Bend90deg, self).__init__()
        self.cellName = "Bend_90deg"

        bend_type_default = _normalize_bend_type(
            default_choice(PCELL_NAME, "bend_type", "Circular", BEND_TYPE_CHOICES)
        )

        self.param(
            "width",
            self.TypeDouble,
            "Waveguide width",
            unit="um",
            default=default_float(PCELL_NAME, "width", DEFAULT_WIDTH),
        )
        self.param(
            "radius",
            self.TypeDouble,
            "Bend radius",
            unit="um",
            default=default_float(PCELL_NAME, "radius", DEFAULT_RADIUS),
        )

        bend_param = self.param(
            "bend_type",
            self.TypeList,
            "Bend type",
            default=bend_type_default,
        )
        for choice in BEND_TYPE_CHOICES:
            bend_param.add_choice(choice, choice)

        # Bezier 参数
        self.bezier_k_param = self.param(
            "bezier_k",
            self.TypeDouble,
            "Bezier shape factor",
            default=default_float(PCELL_NAME, "bezier_k", DEFAULT_BEZIER_K),
        )

        # Euler 参数
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

        # 只读派生参数统一放在全部可编辑参数之后。
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

        # 根据默认弯曲类型，设置初始隐藏状态
        try:
            self.bezier_k_param.hidden = bend_type_default != "Bezier"
            self.Bezier_Rmax_param.hidden = bend_type_default != "Bezier"
            self.Bezier_Rmin_param.hidden = bend_type_default != "Bezier"
            self.Euler_Rmax_param.hidden = bend_type_default != "Euler"
            self.Euler_Rmin_param.hidden = bend_type_default != "Euler"
            self.Euler_Reff_param.hidden = bend_type_default != "Euler"
        except Exception:
            pass

        self.param(
            "points_per_90",
            self.TypeInt,
            "Points per 90° [uneditable]",
            default=AUTO_SAMPLE_COUNT,
            readonly=True,
        )

        self.param(
            "bend_length",
            self.TypeDouble,
            "Bend arc length [uneditable]",
            unit="um",
            default=0.0,
            readonly=True,
        )

    def display_text_impl(self):
        """在实例属性中显示全部用户参数（排除弯曲点数、波导层）。"""
        if self.bend_type == "Bezier":
            return "Bend_90deg_%s_w%.3f_R%.3f_B%.3f_L%.3f" % (
                self.bend_type, self.width, self.radius,
                self.bezier_k, self.bend_length,
            )
        elif self.bend_type == "Euler":
            return "Bend_90deg_%s_w%.3f_Rmax%.3f_Rmin%.3f_Reff%.3f_L%.3f" % (
                self.bend_type, self.width,
                self.Euler_Rmax, self.Euler_Rmin, self.Euler_Reff, self.bend_length,
            )
        return "Bend_90deg_%s_w%.3f_R%.3f_L%.3f" % (
            self.bend_type, self.width, self.radius, self.bend_length,
        )

    def coerce_parameters_impl(self):
        """约束参数范围，计算曲率参数。"""
        dbu = self.layout.dbu if self.layout else 0.001
        self.width = max(dbu, float(self.width))
        try:
            derived = calculate_bend_derived(
                self.radius,
                self.bend_type,
                self.bezier_k,
                self.Euler_Rmax,
                self.Euler_Rmin,
                dbu,
            )
        except ValueError:
            self.Euler_Rmax = max(dbu, float(self.Euler_Rmax))
            self.Euler_Rmin = min(max(dbu, float(self.Euler_Rmin)), self.Euler_Rmax * 0.5)
            derived = calculate_bend_derived(
                self.radius,
                self.bend_type,
                self.bezier_k,
                self.Euler_Rmax,
                self.Euler_Rmin,
                dbu,
            )

        self.radius = derived["radius"]
        self.bend_type = derived["bend_type"]
        self.bezier_k = derived["bezier_k"]
        self.Euler_Rmax = derived["Euler_Rmax"]
        self.Euler_Rmin = derived["Euler_Rmin"]
        self.points_per_90 = derived["points_per_90"]
        if derived["Bezier_Rmax"] is not None:
            self.Bezier_Rmax = round(derived["Bezier_Rmax"], 3)
            self.Bezier_Rmin = round(derived["Bezier_Rmin"], 3)
        if derived["Euler_Reff"] is not None:
            self.Euler_Reff = round(derived["Euler_Reff"], 3)
        self.bend_length = round(derived["bend_length"], 3)

        save_pcell_defaults(
            self,
            PCELL_NAME,
            ["width", "radius", "bend_type", "bezier_k", "Euler_Rmax", "Euler_Rmin"],
        )

    def callback(self, layout, name, states):
        """保持 KLayout 标准回调流程。"""
        try:
            self._jnu_callback_dbu = layout.dbu
        except Exception:
            self._jnu_callback_dbu = 0.001
        return super(Bend90deg, self).callback(layout, name, states)

    def _state_value(self, state):
        """兼容读取 PCellParameterState.value 的属性/方法形式。"""
        try:
            value = state.value
            return value() if callable(value) else value
        except Exception:
            return None

    def _state_to_string(self, state):
        """从 GUI 参数状态读取字符串值。"""
        val = self._state_value(state)
        return str(val) if val is not None else ""

    def _set_state_value(self, state, value):
        """写入 GUI 参数状态，不同 KLayout 版本失败时静默跳过。"""
        try:
            state.value = value
            return True
        except Exception:
            return False

    def callback_impl(self, name):
        """用户编辑参数时，动态显示/隐藏参数并实时更新依赖值。"""
        callback_name = str(name or "")
        dbu = getattr(self, "_jnu_callback_dbu", 0.001)

        try:
            # 在 callback_impl 中，self.bend_type 等是 PCellParameterState，不是值
            bend_type = self._state_to_string(self.bend_type).lower()
            is_bezier = bend_type == "bezier"
            is_euler = bend_type == "euler"

            # Bend radius：Euler 类型时隐藏
            self.radius.visible = not is_euler

            self.bezier_k.visible = is_bezier
            self.Bezier_Rmax.visible = is_bezier
            self.Bezier_Rmin.visible = is_bezier

            self.Euler_Rmax.visible = is_euler
            self.Euler_Rmin.visible = is_euler
            self.Euler_Reff.visible = is_euler

            if callback_name in ("radius", "bezier_k", "Euler_Rmax", "Euler_Rmin", "bend_type"):
                derived = calculate_bend_derived(
                    float(self._state_to_string(self.radius)),
                    bend_type,
                    float(self._state_to_string(self.bezier_k)),
                    float(self._state_to_string(self.Euler_Rmax)),
                    float(self._state_to_string(self.Euler_Rmin)),
                    dbu,
                )
                if derived["Bezier_Rmax"] is not None:
                    self._set_state_value(self.Bezier_Rmax, round(derived["Bezier_Rmax"], 3))
                    self._set_state_value(self.Bezier_Rmin, round(derived["Bezier_Rmin"], 3))
                if derived["Euler_Reff"] is not None:
                    self._set_state_value(self.Euler_Reff, round(derived["Euler_Reff"], 3))
                self._set_state_value(self.points_per_90, derived["points_per_90"])
                self._set_state_value(self.bend_length, round(derived["bend_length"], 3))

        except Exception:
            for state in (
                self.Bezier_Rmax,
                self.Bezier_Rmin,
                self.Euler_Reff,
                self.points_per_90,
                self.bend_length,
            ):
                self._set_state_value(state, "")
            # 回退：通过声明对象的 hidden 属性控制可见性
            try:
                bend_type = _normalize_bend_type(self.bend_type)
                self.bezier_k_param.hidden = bend_type != "Bezier"
                self.Bezier_Rmax_param.hidden = bend_type != "Bezier"
                self.Bezier_Rmin_param.hidden = bend_type != "Bezier"
                self.Euler_Rmax_param.hidden = bend_type != "Euler"
                self.Euler_Rmin_param.hidden = bend_type != "Euler"
                self.Euler_Reff_param.hidden = bend_type != "Euler"
            except Exception:
                pass

    def produce_impl(self):
        """生成 90° 弯曲波导。"""
        dbu = self.layout.dbu
        width_dbu = max(1, _to_itype(self.width, dbu))
        devrec_width_dbu = max(width_dbu, _to_itype(self.width * 3, dbu))

        # 生成中心线点
        effective_radius = (
            euler_Reff(self.Euler_Rmax, self.Euler_Rmin)
            if self.bend_type == "Euler"
            else self.radius
        )
        pts = corner_points(
            effective_radius,
            self.bend_type,
            self.points_per_90,
            self.bezier_k,
            self.Euler_Rmax,
            self.Euler_Rmin,
        )

        # 转换为数据库坐标
        centerline = [pya.Point(_to_itype(x, dbu), _to_itype(y, dbu)) for x, y in pts]

        if len(centerline) < 2:
            return

        si_layer = self.layout.layer(SI_LAYER)
        devrec_layer = self.layout.layer(DEVREC_LAYER)
        pin_layer = self.layout.layer(PIN_LAYER)
        text_layer = self.layout.layer(TEXT_LAYER)

        # 绘制波导
        insert_centerline_polygons(self.cell, si_layer, centerline, width_dbu)
        insert_centerline_polygons(
            self.cell,
            devrec_layer,
            centerline,
            devrec_width_dbu,
        )

        # 生成端口
        _ensure_tools_path()
        from JNU_MWP_tools.core.make_pin import make_pin

        # opt1: 起点，方向 180°（向左）
        make_pin(self.cell, "opt1", centerline[0], width_dbu, pin_layer, 180)
        # opt2: 终点，方向 90°（向上）
        make_pin(self.cell, "opt2", centerline[-1], width_dbu, pin_layer, 90)

        # 文字标注
        if self.bend_type == "Euler":
            label = "Bend_90deg type=Euler w=%.3fum Reff=%.3fum Rmax=%.3fum Rmin=%.3fum L=%.3fum" % (
                self.width,
                self.Euler_Reff,
                self.Euler_Rmax,
                self.Euler_Rmin,
                self.bend_length,
            )
        else:
            label = "Bend_90deg type=%s w=%.3fum R=%.3fum L=%.3fum" % (
                self.bend_type,
                self.width,
                self.radius,
                self.bend_length,
            )
        text = pya.Text(
            label,
            pya.Trans(pya.Trans.R0, centerline[0].x, centerline[0].y),
        )
        shape = self.cell.shapes(text_layer).insert(text)
        shape.text_dsize = max(0.1, self.width * 0.5)


__all__ = [
    "Bend90deg",
    "_normalize_bend_type",
    "corner_points",
    "corner_points_circular",
    "corner_points_bezier",
    "corner_points_euler",
    "calculate_bend_derived",
    "PORT_STRAIGHT_UM",
]
