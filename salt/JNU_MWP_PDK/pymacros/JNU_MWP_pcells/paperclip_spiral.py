# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""回形针螺旋波导 PCell。"""

import math
import os
import sys

import pya

try:
    from .pcell_defaults import (
        default_bool,
        default_choice,
        default_float,
        default_int,
        apply_saved_defaults_to_states,
        save_pcell_defaults,
    )
except ImportError:
    PCELL_DIR = os.path.dirname(os.path.abspath(__file__))
    if PCELL_DIR not in sys.path:
        sys.path.insert(0, PCELL_DIR)
    from pcell_defaults import (
        default_bool,
        default_choice,
        default_float,
        default_int,
        apply_saved_defaults_to_states,
        save_pcell_defaults,
    )

# 弯曲工具模块位于 tools 目录（在 JNU_MWP_PDK 根目录下）
PYMACROS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PYMACROS_DIR not in sys.path:
    sys.path.insert(0, PYMACROS_DIR)

from JNU_MWP_tools.core.bend_sampling import AUTO_SAMPLE_COUNT, effective_points_per_90, points_per_90
from JNU_MWP_tools.core.bend_curvature import bezier_Rmax_Rmin, euler_Reff
from JNU_MWP_tools.core.devrec import insert_device_devrec
from JNU_MWP_tools.core.path_geometry import insert_centerline_polygons

# 从 bend_90deg 导入公共弯曲点生成函数（局部坐标系）
from .bend_90deg import (
    PORT_STRAIGHT_UM,
    corner_points,
)


PCELL_NAME = "Paperclip_Spiral"
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
BEND_TYPE_CHOICES = ("Circular", "Bezier", "Euler")
PORTS_TYPE_CHOICES = (
    ("type1", "type1 - ports on same sides"),
    ("type2", "type2 - ports on opposite sides"),
    ("type3", "type3 - opposite sides, aligned y"),
)
DEFAULT_BEZIER = 0.35
DEFAULT_EULER_RMAX = 30.0
DEFAULT_EULER_RMIN = 10.0
DEFAULT_POINTS_PER_90 = AUTO_SAMPLE_COUNT
PIN_LENGTH_UM = 0.02


def effective_bend_radius(bend_type, bend_radius, euler_rmax, euler_rmin):
    """返回当前弯曲类型实际使用的半径；Euler 完全忽略兼容参数 bend_radius。"""
    if _normalize_bend_type(bend_type) == "Euler":
        if not (float(euler_rmax) > float(euler_rmin) > 0.0):
            raise ValueError("Euler Rmin 必须大于 0 且小于 Euler Rmax。")
        return float(euler_Reff(float(euler_rmax), float(euler_rmin)))
    return float(bend_radius)


def calculate_paperclip_bend_values(
    bend_type,
    bend_radius,
    bezier,
    euler_rmax,
    euler_rmin,
    waveguide_width,
    dbu=0.001,
):
    """纯计算 Paperclip 曲率、有效半径和自适应点数。"""
    bend_type = _normalize_bend_type(bend_type)
    radius = effective_bend_radius(bend_type, bend_radius, euler_rmax, euler_rmin)
    if radius <= 0.010:
        raise ValueError("有效弯曲半径必须大于 0.010 um。")
    result = {
        "bend_type": bend_type,
        "effective_radius": radius,
        "points_per_90": max(4, points_per_90(max(float(waveguide_width), radius), dbu)),
        "Bezier_Rmax": None,
        "Bezier_Rmin": None,
        "Euler_Reff": None,
    }
    if bend_type == "Bezier":
        result["Bezier_Rmax"], result["Bezier_Rmin"] = bezier_Rmax_Rmin(
            float(bend_radius), _coerce_bezier(bezier)
        )
    elif bend_type == "Euler":
        result["Euler_Reff"] = radius
    return result
# type3 的 opt1 端口中心到第一个 90° Bend 起点固定为 10 nm。
TYPE3_OPT1_STRAIGHT_UM = 0.010


def _port_extension_point(port_center, direction, extension_um):
    """在端口外侧生成一个延伸点，确保 Si 完全覆盖 PinRec 路径。

    PinRec 路径总长 20 nm，中心在端口坐标；外侧 10 nm 必须被 Si 覆盖。
    """
    if direction == 0:
        return pya.DPoint(port_center.x + extension_um, port_center.y)
    elif direction == 180:
        return pya.DPoint(port_center.x - extension_um, port_center.y)
    elif direction == 90:
        return pya.DPoint(port_center.x, port_center.y + extension_um)
    else:  # 270
        return pya.DPoint(port_center.x, port_center.y - extension_um)


# Polygon 边界通常约为中心线点数的两倍；限制为 2000 可使 GDS XY 记录保持在 0x8000 字节以内。
MAX_GDS_POLYGON_CENTERLINE_POINTS = 2000
PATH_SEGMENT_OVERLAP_POINTS = 24
EDITABLE_PARAMETER_NAMES = (
    "wg_layer",
    "pin_layer",
    "length",
    "wg_width",
    "bend_radius",
    "gap",
    "loops",
    "ports_type",
    "bend_type",
    "bezier",
    "vertical_stretch",
)
BUILTIN_DEFAULTS = {
    "wg_layer": DEFAULT_WG_LAYER,
    "pin_layer": DEFAULT_PIN_LAYER,
    "length": 100.0,
    "wg_width": 0.5,
    "bend_radius": 10.0,
    "gap": 2.0,
    "loops": 2,
    "ports_type": "type1",
    "bend_type": "Circular",
    "bezier": DEFAULT_BEZIER,
    "vertical_stretch": 0.0,
}


def _choice_values(choices):
    """返回 TypeList 的内部可选值。"""

    return tuple(value for value, _label in choices)


def _normalize_bend_type(value):
    """把弯曲类型归一到当前支持的标准名称。"""

    text = str(value).strip().lower()
    if text == "bezier":
        return "Bezier"
    if text == "euler":
        return "Euler"
    return "Circular"


def _normalize_ports_type(value):
    """把端口类型归一到 type1/type2/type3。"""

    value = str(value)
    return value if value in _choice_values(PORTS_TYPE_CHOICES) else "type1"


def _coerce_bezier(value):
    """限制 Bezier 控制参数，避免控制点退化。"""

    return max(0.05, min(0.95, float(value)))


def _layer_info_from_choice(value, fallback):
    """把固定列表中的 layer/datatype 字符串转换为 LayerInfo。"""

    try:
        text = str(value)
        if "/" in text:
            layer, datatype = text.split("/", 1)
            return pya.LayerInfo(int(layer), int(datatype))
    except Exception:
        pass
    return fallback


class PaperclipSpiral(pya.PCellDeclarationHelper):
    """JNU 回形针螺旋波导 PCell。"""

    def __init__(self):
        super(PaperclipSpiral, self).__init__()

        wg_layer_default = default_choice(
            PCELL_NAME,
            "wg_layer",
            DEFAULT_WG_LAYER,
            _choice_values(WG_LAYER_CHOICES),
        )
        pin_layer_default = default_choice(
            PCELL_NAME,
            "pin_layer",
            DEFAULT_PIN_LAYER,
            _choice_values(PIN_LAYER_CHOICES),
        )
        bend_type_default = _normalize_bend_type(
            default_choice(PCELL_NAME, "bend_type", "Circular", BEND_TYPE_CHOICES)
        )
        ports_type_default = _normalize_ports_type(
            default_choice(PCELL_NAME, "ports_type", "type1", _choice_values(PORTS_TYPE_CHOICES))
        )
        wg_width_default = default_float(PCELL_NAME, "wg_width", 0.5)
        bend_radius_default = default_float(PCELL_NAME, "bend_radius", 10.0)
        points_default = points_per_90(max(wg_width_default, bend_radius_default), 0.001)

        # 固定列表比 TypeLayer 原生控件更宽，便于在 PCell GUI 中看清图层名称。
        wg_layer_param = self.param(
            "wg_layer",
            self.TypeList,
            "Waveguide layer",
            default=wg_layer_default,
        )
        for value, label in WG_LAYER_CHOICES:
            wg_layer_param.add_choice(label, value)

        pin_layer_param = self.param(
            "pin_layer",
            self.TypeList,
            "Pin recognition layer",
            default=pin_layer_default,
        )
        for value, label in PIN_LAYER_CHOICES:
            pin_layer_param.add_choice(label, value)

        self.param(
            "length",
            self.TypeDouble,
            "Inner length (min 2× bend radius)",
            unit="um",
            default=default_float(PCELL_NAME, "length", 100.0),
        )
        self.param(
            "wg_width",
            self.TypeDouble,
            "Waveguide width",
            unit="um",
            default=wg_width_default,
        )
        self.bend_radius_param = self.param(
            "bend_radius",
            self.TypeDouble,
            "Bend radius",
            unit="um",
            default=bend_radius_default,
        )
        self.param(
            "gap",
            self.TypeDouble,
            "Waveguide gap",
            unit="um",
            default=default_float(PCELL_NAME, "gap", 2.0),
        )
        self.param(
            "loops",
            self.TypeInt,
            "Number of loops",
            default=default_int(PCELL_NAME, "loops", 2),
        )

        ports_param = self.param(
            "ports_type",
            self.TypeList,
            "Ports type",
            default=ports_type_default,
        )
        for value, label in PORTS_TYPE_CHOICES:
            ports_param.add_choice(label, value)

        # 旧版参数保留但隐藏，用于读取旧 layout；新 GUI 统一使用 ports_type。
        self.ports_opposite_param = self.param(
            "ports_opposite",
            self.TypeBoolean,
            "Ports on opposite sides",
            default=default_bool(PCELL_NAME, "ports_opposite", False),
        )
        self.port_vertical_param = self.param(
            "port_vertical",
            self.TypeBoolean,
            "Output port vertical",
            default=default_bool(PCELL_NAME, "port_vertical", False),
        )
        try:
            self.ports_opposite_param.hidden = True
            self.port_vertical_param.hidden = True
        except Exception:
            pass

        bend_param = self.param(
            "bend_type",
            self.TypeList,
            "Bend type",
            default=bend_type_default,
        )
        for choice in BEND_TYPE_CHOICES:
            bend_param.add_choice(choice, choice)

        self.bezier_param = self.param(
            "bezier",
            self.TypeDouble,
            "Bezier parameter",
            default=default_float(PCELL_NAME, "bezier", DEFAULT_BEZIER),
        )
        try:
            self.bezier_param.hidden = bend_type_default != "Bezier"
        except Exception:
            pass

        # Euler 弯曲参数
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
            default=default_float(PCELL_NAME, "vertical_stretch", 0.0),
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
        self.param(
            "points_per_90",
            self.TypeInt,
            "Bend points per 90 deg [uneditable]",
            default=points_default,
            readonly=True,
        )
        self.param(
            "total_length",
            self.TypeDouble,
            "Estimated centerline length [uneditable]",
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
        self.delta_length_param = self.param(
            "delta_length",
            self.TypeDouble,
            "delta_length [uneditable]",
            unit="um",
            default=0.0,
            readonly=True,
        )
        try:
            self.delta_length_param.hidden = True
        except Exception:
            pass

    def display_text_impl(self):
        """返回包含全部用户参数的 cell 名称（排除弯曲点数、波导层）。"""
        if self.bend_type == "Euler":
            base = "Paperclip_Spiral(%s,%s,L=%.3f,dL=%.3f,Reff=%.3f,N=%d,w=%.3f,gap=%.3f" % (
                self.ports_type, self.bend_type, self.total_length, self.delta_L,
                self.Euler_Reff, self.loops, self.wg_width, self.gap,
            )
        else:
            base = "Paperclip_Spiral(%s,%s,L=%.3f,dL=%.3f,R=%.3f,N=%d,w=%.3f,gap=%.3f" % (
                self.ports_type, self.bend_type, self.total_length, self.delta_L,
                self.bend_radius, self.loops, self.wg_width, self.gap,
            )
        if self.bend_type == "Bezier":
            base += ",B=%.3f" % self.bezier
        elif self.bend_type == "Euler":
            base += ",Rmax=%.3f,Rmin=%.3f" % (self.Euler_Rmax, self.Euler_Rmin)
        if float(self.vertical_stretch) > 0:
            base += ",vs=%.1f" % self.vertical_stretch
        return base + ")"

    def coerce_parameters_impl(self):
        """约束参数范围，刷新长度与 delta_L，并保存下次新建默认值。"""

        dbu = self.layout.dbu if self.layout is not None else 0.001
        min_width = max(dbu, 0.001)

        if str(self.wg_layer) not in _choice_values(WG_LAYER_CHOICES):
            self.wg_layer = DEFAULT_WG_LAYER
        if str(self.pin_layer) not in _choice_values(PIN_LAYER_CHOICES):
            self.pin_layer = DEFAULT_PIN_LAYER

        self.wg_width = max(
            self._float_or_default(self.wg_width, default_float(PCELL_NAME, "wg_width", 0.5)),
            min_width,
        )
        self.bend_radius = max(
            self._float_or_default(
                self.bend_radius,
                default_float(PCELL_NAME, "bend_radius", 10.0),
            ),
            self.wg_width,
        )
        self.gap = max(
            self._float_or_default(self.gap, default_float(PCELL_NAME, "gap", 2.0)),
            0.0,
        )
        self.loops = max(self._int_or_default(self.loops, default_int(PCELL_NAME, "loops", 2)), 1)
        self.vertical_stretch = max(
            self._float_or_default(
                self.vertical_stretch,
                default_float(PCELL_NAME, "vertical_stretch", 0.0),
            ),
            0.0,
        )
        self.bend_type = _normalize_bend_type(self.bend_type)
        self.ports_type = self._coerce_ports_type_from_current_values()
        self.bezier = _coerce_bezier(
            self._float_or_default(self.bezier, default_float(PCELL_NAME, "bezier", DEFAULT_BEZIER))
        )

        # 约束 Euler 参数
        self.Euler_Rmax = max(0.001, float(self.Euler_Rmax))
        self.Euler_Rmin = max(0.001, float(self.Euler_Rmin))
        if self.Euler_Rmin >= self.Euler_Rmax:
            self.Euler_Rmin = self.Euler_Rmax * 0.5

        derived = calculate_paperclip_bend_values(
            self.bend_type,
            self.bend_radius,
            self.bezier,
            self.Euler_Rmax,
            self.Euler_Rmin,
            self.wg_width,
            dbu,
        )
        self.length = max(
            self._float_or_default(self.length, default_float(PCELL_NAME, "length", 100.0)),
            2.0 * derived["effective_radius"],
        )
        self.points_per_90 = derived["points_per_90"]
        if derived["Bezier_Rmax"] is not None:
            self.Bezier_Rmax = round(derived["Bezier_Rmax"], 3)
            self.Bezier_Rmin = round(derived["Bezier_Rmin"], 3)
        if derived["Euler_Reff"] is not None:
            self.Euler_Reff = round(derived["Euler_Reff"], 3)

        points = self._rounded_centerline()
        self.total_length = round(self._path_length(points), 3)
        self.delta_L = round(self._delta_length(points, self.total_length), 3)
        self.delta_length = self.delta_L
        self._save_defaults()

    def produce_impl(self):
        """生成实际版图：中心线 path、PinRec 端口和参数文字。"""

        dbu = self.layout.dbu
        points = self._rounded_centerline()
        wg_layer = self._layout_layer(self.wg_layer, pya.LayerInfo(1, 0))
        pin_layer = self._layout_layer(self.pin_layer, pya.LayerInfo(1, 10))
        text_layer = self.layout.layer(TEXT_LAYER)

        # 为 Si 完全覆盖 PinRec（20 nm 长，中心在端口），在端口外侧增加 10 nm 水平延伸。
        extended = list(points)
        if len(points) >= 2:
            start = points[0]
            following = points[1]
            start_dir = self._cardinal_direction(
                start.x - following.x, start.y - following.y
            )
            extended.insert(0, _port_extension_point(start, start_dir, PORT_STRAIGHT_UM))

            end = points[-1]
            previous = points[-2]
            end_dir = self._cardinal_direction(
                end.x - previous.x, end.y - previous.y
            )
            extended.append(_port_extension_point(end, end_dir, PORT_STRAIGHT_UM))

        self._insert_centerline_polygons(wg_layer, extended, self.wg_width, dbu)
        self._insert_pins(points, pin_layer)
        insert_device_devrec(self.cell, wg_layer, pin_layer)
        self._insert_parameter_text(points, text_layer)

    def callback(self, layout, name, states):
        """保持 KLayout 标准回调流程，实际显示逻辑放在 callback_impl。"""

        try:
            self._jnu_callback_dbu = layout.dbu
        except Exception:
            self._jnu_callback_dbu = 0.001
        return super(PaperclipSpiral, self).callback(layout, name, states)

    def callback_impl(self, name):
        """当用户编辑参数时，动态显示/隐藏参数并实时更新依赖值。"""

        apply_saved_defaults_to_states(
            self,
            PCELL_NAME,
            EDITABLE_PARAMETER_NAMES,
            BUILTIN_DEFAULTS,
        )

        dbu = getattr(self, "_jnu_callback_dbu", 0.001)

        try:
            bend_type = _normalize_bend_type(self._state_to_string(self.bend_type))
            is_bezier = bend_type == "Bezier"
            is_euler = bend_type == "Euler"

            self.bend_radius.visible = not is_euler
            self.bezier.visible = is_bezier
            self.Bezier_Rmax.visible = is_bezier
            self.Bezier_Rmin.visible = is_bezier

            self.Euler_Rmax.visible = is_euler
            self.Euler_Rmin.visible = is_euler
            self.Euler_Reff.visible = is_euler

            values = {
                "bend_type": bend_type,
                "bend_radius": float(self._state_to_string(self.bend_radius)),
                "bezier": float(self._state_to_string(self.bezier)),
                "Euler_Rmax": float(self._state_to_string(self.Euler_Rmax)),
                "Euler_Rmin": float(self._state_to_string(self.Euler_Rmin)),
                "wg_width": float(self._state_to_string(self.wg_width)),
                "gap": float(self._state_to_string(self.gap)),
                "length": float(self._state_to_string(self.length)),
                "loops": max(1, int(float(self._state_to_string(self.loops)))),
                "ports_type": _normalize_ports_type(self._state_to_string(self.ports_type)),
                "vertical_stretch": float(self._state_to_string(self.vertical_stretch)),
            }
            derived = calculate_paperclip_bend_values(
                bend_type,
                values["bend_radius"],
                values["bezier"],
                values["Euler_Rmax"],
                values["Euler_Rmin"],
                values["wg_width"],
                dbu,
            )
            values["effective_radius"] = derived["effective_radius"]
            values["points_per_90"] = derived["points_per_90"]
            values["length"] = max(values["length"], 2.0 * values["effective_radius"])
            if derived["Bezier_Rmax"] is not None:
                self._set_state_value(self.Bezier_Rmax, round(derived["Bezier_Rmax"], 3))
                self._set_state_value(self.Bezier_Rmin, round(derived["Bezier_Rmin"], 3))
            if derived["Euler_Reff"] is not None:
                self._set_state_value(self.Euler_Reff, round(derived["Euler_Reff"], 3))
            self._set_state_value(self.points_per_90, derived["points_per_90"])

            points = self._rounded_centerline(values)
            total_length = round(self._path_length(points), 3)
            delta_l = round(self._delta_length(points, total_length), 3)
            self._set_state_value(self.total_length, total_length)
            self._set_state_value(self.delta_L, delta_l)
            self._set_state_value(self.delta_length, delta_l)

        except Exception:
            for state in (
                self.Bezier_Rmax,
                self.Bezier_Rmin,
                self.Euler_Reff,
                self.points_per_90,
                self.total_length,
                self.delta_L,
                self.delta_length,
            ):
                self._set_state_value(state, "")
            try:
                bend_type = _normalize_bend_type(self._state_to_string(self.bend_type))
                self.bend_radius_param.hidden = bend_type == "Euler"
                self.bezier_param.hidden = bend_type != "Bezier"
            except Exception:
                pass

    def _state_to_float(self, state, fallback):
        """从 GUI 参数状态读取浮点数，失败时使用 fallback。"""

        try:
            return float(self._state_to_string(state))
        except Exception:
            return float(fallback)

    def _set_state_value(self, state, value):
        """写入 GUI 参数状态，不同 KLayout 版本失败时静默跳过。"""

        try:
            state.value = value
            return True
        except Exception:
            return False

    def _coerce_ports_type_from_current_values(self):
        """兼容旧版 boolean 端口参数并返回当前端口类型。"""

        raw_value = str(getattr(self, "ports_type", ""))
        if raw_value in _choice_values(PORTS_TYPE_CHOICES):
            return raw_value

        # 只有旧版 layout 没有有效 ports_type 时，才读取隐藏 boolean 参数做迁移。
        if bool(getattr(self, "ports_opposite", False)) or bool(getattr(self, "port_vertical", False)):
            return "type2"
        return "type1"

    def _save_defaults(self):
        """保存用户可编辑参数，供下次从 Library 新建同类 PCell 使用。"""

        save_pcell_defaults(
            self,
            PCELL_NAME,
            EDITABLE_PARAMETER_NAMES,
        )

    def _layout_layer(self, value, fallback):
        """把固定列表参数解析为当前 layout 的图层索引。"""

        return self.layout.layer(_layer_info_from_choice(value, fallback))

    def _centerline_waypoints(self, values=None):
        """构造未圆角的中心线折线路径点。"""
        values = values or {}
        bend_type = values.get("bend_type", self.bend_type)
        bend_radius = float(values.get("bend_radius", self.bend_radius))
        euler_rmax = float(values.get("Euler_Rmax", self.Euler_Rmax))
        euler_rmin = float(values.get("Euler_Rmin", self.Euler_Rmin))
        radius = float(values.get(
            "effective_radius",
            effective_bend_radius(bend_type, bend_radius, euler_rmax, euler_rmin),
        ))
        wg_width = float(values.get("wg_width", self.wg_width))
        gap = float(values.get("gap", self.gap))
        pitch = wg_width + gap
        length0 = max(float(values.get("length", self.length)), 2.0 * radius)
        loops = int(values.get("loops", self.loops))
        ports_type = values.get("ports_type", self.ports_type)
        offset = radius
        extra = pitch

        # 内侧第一段 U/S 弯固定以 x=0 为中心；length 只对左右直线对称加长。
        points = [
            pya.DPoint(-length0, offset),
            pya.DPoint(0.0, offset),
            pya.DPoint(0.0, -offset),
            pya.DPoint(length0, -offset),
        ]

        last_i = 1
        for i in range(1, loops * 2, 2):
            last_i = i

            points.insert(
                0,
                pya.DPoint(
                    -length0 - pitch * (i - 1),
                    offset - 2.0 * radius - pitch * (i - 1) - extra,
                ),
            )
            points.insert(
                0,
                pya.DPoint(
                    length0 + pitch * i,
                    offset - 2.0 * radius - pitch * (i - 1) - extra,
                ),
            )
            points.insert(
                0,
                pya.DPoint(
                    length0 + pitch * i,
                    -offset + 2.0 * radius + pitch * i + extra,
                ),
            )
            points.insert(
                0,
                pya.DPoint(
                    -length0 - pitch * (i + 1),
                    -offset + 2.0 * radius + pitch * i + extra,
                ),
            )
            points.append(
                pya.DPoint(
                    length0 + pitch * (i - 1),
                    2.0 * radius - offset + pitch * (i - 1) + extra,
                )
            )
            points.append(
                pya.DPoint(
                    -length0 - pitch * i,
                    2.0 * radius - offset + pitch * (i - 1) + extra,
                )
            )
            points.append(
                pya.DPoint(
                    -length0 - pitch * i,
                    -2.0 * radius + offset - pitch * i - extra,
                )
            )
            points.append(
                pya.DPoint(
                    length0 + pitch * (i + 1),
                    -2.0 * radius + offset - pitch * i - extra,
                )
            )

        if ports_type == "type1":
            points.append(
                pya.DPoint(
                    length0 + pitch * (last_i + 1),
                    2.0 * radius - offset + pitch * (last_i + 1) + extra,
                )
            )
            points.append(
                pya.DPoint(
                    -length0 - pitch * (last_i + 1),
                    2.0 * radius - offset + pitch * (last_i + 1) + extra,
                )
            )

        points.pop(0)
        points.insert(
            0,
            pya.DPoint(
                -length0 - pitch * (last_i + 1),
                -offset + 2.0 * radius + pitch * last_i + extra,
            ),
        )

        points = self._remove_duplicate_points(points)
        if ports_type == "type3":
            points = self._apply_type3_input_jog(points, pitch, radius)

        return self._apply_vertical_stretch(points, values)

    def _apply_type3_input_jog(self, points, horizontal_gap, radius=None):
        """给 type3 的 opt1 前端增加等高绕线，并保持边到边间距等于 gap。"""

        if len(points) < 2:
            return points

        old_start = points[0]
        end = points[-1]
        if abs(old_start.y - end.y) <= 1e-9:
            return points

        lead_raw = TYPE3_OPT1_STRAIGHT_UM + float(
            self.bend_radius if radius is None else radius
        )
        # old_start 已经在主体左侧外移了一个 pitch。type3 的中间直波导直接
        # 使用这个 x 坐标，中心线间距为 wg_width + gap，边到边间距即为 gap。
        jog_x = old_start.x
        new_start = pya.DPoint(jog_x - lead_raw, end.y)
        first_turn = pya.DPoint(jog_x, end.y)
        second_turn = pya.DPoint(jog_x, old_start.y)
        # 跳过 old_start，避免 second_turn 后的短水平段挤压第二个 90 度弯曲半径。
        return self._remove_duplicate_points([new_start, first_turn, second_turn] + list(points[1:]))

    def _apply_vertical_stretch(self, points, values=None):
        """纵向拉伸：保持组内相邻波导中心距 = wg_width + gap，不缩放 pitch。

        仅通过移动上半部分/下半部分波导组并延长连接直波导来增加整体高度。
        vertical_stretch = 0 时，所有相邻平行波导边到边间距 = gap。
        vertical_stretch > 0 时，局部相邻平行波导间距仍为 gap，整体高度增加。
        """
        values = values or {}
        stretch = max(float(values.get("vertical_stretch", self.vertical_stretch)), 0.0)
        if stretch <= 0.0 or len(points) < 2:
            return points

        pitch = float(values.get("wg_width", self.wg_width)) + float(values.get("gap", self.gap))
        min_y = min(point.y for point in points)
        max_y = max(point.y for point in points)
        height = max_y - min_y
        if height <= 1e-12:
            return points

        center_y = 0.5 * (min_y + max_y)
        margin = max(1e-6, pitch * 0.1)

        # 找到中心窗口区域(围绕 y=center_y 的一段)用于分隔上半区和下半区
        upper_points = []
        lower_points = []
        middle_points = []

        for point in points:
            dist_from_center = point.y - center_y
            if dist_from_center > margin:
                upper_points.append(point)
            elif dist_from_center < -margin:
                lower_points.append(point)
            else:
                middle_points.append(point)

        if not upper_points and not lower_points:
            return points

        half_stretch = stretch * 0.5

        result = []
        for point in points:
            dist = point.y - center_y
            if dist > margin:
                result.append(pya.DPoint(point.x, point.y + half_stretch))
            elif dist < -margin:
                result.append(pya.DPoint(point.x, point.y - half_stretch))
            else:
                # 直波导连接段：x 保持不变，y 坐标按比例线性插值
                if upper_points and lower_points:
                    top_y = min(p.y for p in upper_points) + half_stretch
                    bottom_y = max(p.y for p in lower_points) - half_stretch
                    frac = (point.y - bottom_y) / max(top_y - bottom_y, 1e-12)
                    result.append(pya.DPoint(point.x, bottom_y + frac * (top_y - bottom_y)))
                else:
                    result.append(point)

        return result

    def _rounded_centerline(self, values=None):
        """把折线路径转换成带弯曲采样点的中心线路径。"""
        values = values or {}
        waypoints = self._centerline_waypoints(values)
        dbu = getattr(getattr(self, "layout", None), "dbu", 0.001)
        bend_type = _normalize_bend_type(values.get("bend_type", self.bend_type))
        bend_radius = float(values.get("bend_radius", self.bend_radius))
        euler_rmax = float(values.get("Euler_Rmax", self.Euler_Rmax))
        euler_rmin = float(values.get("Euler_Rmin", self.Euler_Rmin))
        radius = float(values.get(
            "effective_radius",
            effective_bend_radius(bend_type, bend_radius, euler_rmax, euler_rmin),
        ))
        requested_points = int(values.get("points_per_90", self.points_per_90))
        actual_points_per_90 = effective_points_per_90(
            requested_points,
            radius,
            dbu,
        )
        return self._round_waypoints(
            waypoints,
            radius,
            actual_points_per_90,
            bend_type,
            float(values.get("bezier", self.bezier)),
            euler_rmax,
            euler_rmin,
        )

    def _round_waypoints(
        self,
        points,
        radius,
        points_per_90,
        bend_type="Circular",
        bezier=DEFAULT_BEZIER,
        euler_rmax=DEFAULT_EULER_RMAX,
        euler_rmin=DEFAULT_EULER_RMIN,
    ):
        """用 bend_90deg 公共点列对中心线折点做圆角处理。

        弯曲端点严格与相邻直波导轴对齐：
        - 首点与前一段直波导共享同轴坐标（水平段同 y，垂直段同 x）
        - 末点与后一段直波导共享同轴坐标
        """

        if len(points) < 3 or radius <= 0:
            return points

        dbu = getattr(getattr(self, "layout", None), "dbu", 0.001)

        def _round_dbu(val):
            return int(round(val / dbu))

        rounded = [points[0]]
        for index in range(1, len(points) - 1):
            prev_pt = points[index - 1]
            corner = points[index]
            next_pt = points[index + 1]

            ux, uy, len_in = self._unit_vector(prev_pt, corner)
            vx, vy, len_out = self._unit_vector(corner, next_pt)
            if len_in <= 0 or len_out <= 0:
                self._append_point(rounded, corner)
                continue

            dot = max(-1.0, min(1.0, ux * vx + uy * vy))
            cross = ux * vy - uy * vx
            turn_angle = math.acos(dot)
            if abs(cross) < 1e-9 or turn_angle < 1e-9:
                self._append_point(rounded, corner)
                continue

            tangent = radius * math.tan(0.5 * turn_angle)
            tangent = min(
                tangent,
                max(0.0, len_in - TYPE3_OPT1_STRAIGHT_UM),
                max(0.0, len_out - TYPE3_OPT1_STRAIGHT_UM),
            )

            start = pya.DPoint(corner.x - ux * tangent, corner.y - uy * tangent)
            self._append_point(rounded, start)

            turn_sign = 1.0 if cross > 0 else -1.0
            nx, ny = -uy, ux
            steps = max(2, int(math.ceil(abs(turn_angle) / (0.5 * math.pi) * points_per_90)))
            local_pts = corner_points(
                tangent,
                bend_type,
                steps,
                bezier,
                euler_rmax,
                euler_rmin,
            )
            for lx, ly in local_pts[1:]:
                self._append_point(
                    rounded,
                    pya.DPoint(
                        start.x + ux * lx + nx * turn_sign * ly,
                        start.y + uy * lx + ny * turn_sign * ly,
                    ),
                )

        self._append_point(rounded, points[-1])
        return rounded

    def _bezier_round_waypoints(self, points, radius, points_per_90, bezier):
        """用 Waveguide 工具同风格的 90 度 Bezier 转角平滑中心线。

        弯曲端点严格与相邻直波导轴对齐：
        - 首点与前一段直波导共享同轴坐标（水平段同 y，垂直段同 x）
        - 末点与后一段直波导共享同轴坐标
        """

        return self._round_waypoints(
            points,
            radius,
            points_per_90,
            "Bezier",
            bezier,
            self.Euler_Rmax,
            self.Euler_Rmin,
        )

        if len(points) < 3 or radius <= 0:
            return points

        dbu = getattr(getattr(self, "layout", None), "dbu", 0.001)

        def _round_dbu(val):
            return int(round(val / dbu))

        rounded = [points[0]]
        for index in range(1, len(points) - 1):
            prev_pt = points[index - 1]
            corner = points[index]
            next_pt = points[index + 1]

            ux, uy, len_in = self._unit_vector(prev_pt, corner)
            vx, vy, len_out = self._unit_vector(corner, next_pt)
            if len_in <= 0 or len_out <= 0:
                self._append_point(rounded, corner)
                continue

            dot = max(-1.0, min(1.0, ux * vx + uy * vy))
            cross = ux * vy - uy * vx
            turn_angle = math.acos(dot)
            if abs(cross) < 1e-9 or turn_angle < 1e-9:
                self._append_point(rounded, corner)
                continue

            tangent = radius * math.tan(0.5 * turn_angle)
            tangent = min(
                tangent,
                max(0.0, len_in - TYPE3_OPT1_STRAIGHT_UM),
                max(0.0, len_out - TYPE3_OPT1_STRAIGHT_UM),
            )
            start = pya.DPoint(corner.x - ux * tangent, corner.y - uy * tangent)
            end = pya.DPoint(corner.x + vx * tangent, corner.y + vy * tangent)
            self._append_point(rounded, start)

            turn_sign = 1.0 if cross > 0 else -1.0
            nx, ny = -uy, ux
            steps = max(2, int(math.ceil(abs(turn_angle) / (0.5 * math.pi) * points_per_90)))

            # 记录前一段直波导的轴向信息，用于端点对齐
            prev_is_horizontal = abs(_round_dbu(prev_pt.y) - _round_dbu(start.y)) < 1
            entry_fixed_y = start.y if prev_is_horizontal else None
            entry_fixed_x = start.x if not prev_is_horizontal else None

            # 记录后一段直波导的轴向信息
            next_is_horizontal = abs(_round_dbu(next_pt.y) - _round_dbu(end.y)) < 1
            exit_fixed_y = end.y if next_is_horizontal else None
            exit_fixed_x = end.x if not next_is_horizontal else None

            local_pts = corner_points(
                tangent,
                "Bezier",
                steps,
                bezier,
                self.Euler_Rmax,
                self.Euler_Rmin,
            )
            # local_pts: [(0,0), ..., (tangent, tangent)]，跳过起点（已作为 start 添加）

            for i, (lx, ly) in enumerate(local_pts[1:], start=1):
                pt_x = start.x + ux * lx + nx * turn_sign * ly
                pt_y = start.y + uy * lx + ny * turn_sign * ly

                # 首点：与前一段直波导轴对齐
                if i == 1:
                    if entry_fixed_y is not None:
                        pt_y = entry_fixed_y
                    elif entry_fixed_x is not None:
                        pt_x = entry_fixed_x

                # 末点：与后一段直波导轴对齐
                if i == len(local_pts) - 1:
                    if exit_fixed_y is not None:
                        pt_y = exit_fixed_y
                    elif exit_fixed_x is not None:
                        pt_x = exit_fixed_x

                self._append_point(
                    rounded,
                    pya.DPoint(pt_x, pt_y),
                )

        self._append_point(rounded, points[-1])
        return rounded

    def _euler_round_waypoints(self, points, radius, points_per_90, R_max, R_min):
        """用 Euler 弯曲平滑中心线。

        使用改进型 Euler 曲线：曲率沿弧长线性分布。
        端点对齐逻辑与 Bezier 版本相同。
        """

        return self._round_waypoints(
            points,
            radius,
            points_per_90,
            "Euler",
            self.bezier,
            R_max,
            R_min,
        )

        if len(points) < 3 or radius <= 0:
            return points

        dbu = getattr(getattr(self, "layout", None), "dbu", 0.001)

        def _round_dbu(val):
            return int(round(val / dbu))

        rounded = [points[0]]
        for index in range(1, len(points) - 1):
            prev_pt = points[index - 1]
            corner = points[index]
            next_pt = points[index + 1]

            ux, uy, len_in = self._unit_vector(prev_pt, corner)
            vx, vy, len_out = self._unit_vector(corner, next_pt)
            if len_in <= 0 or len_out <= 0:
                self._append_point(rounded, corner)
                continue

            dot = max(-1.0, min(1.0, ux * vx + uy * vy))
            cross = ux * vy - uy * vx
            turn_angle = math.acos(dot)
            if abs(cross) < 1e-9 or turn_angle < 1e-9:
                self._append_point(rounded, corner)
                continue

            tangent = radius * math.tan(0.5 * turn_angle)
            tangent = min(
                tangent,
                max(0.0, len_in - TYPE3_OPT1_STRAIGHT_UM),
                max(0.0, len_out - TYPE3_OPT1_STRAIGHT_UM),
            )
            start = pya.DPoint(corner.x - ux * tangent, corner.y - uy * tangent)
            end = pya.DPoint(corner.x + vx * tangent, corner.y + vy * tangent)
            self._append_point(rounded, start)

            turn_sign = 1.0 if cross > 0 else -1.0
            nx, ny = -uy, ux
            steps = max(2, int(math.ceil(abs(turn_angle) / (0.5 * math.pi) * points_per_90)))

            # 生成 Euler 弯曲点
            # 按转角比例缩放 R_max 和 R_min
            angle_ratio = abs(turn_angle) / (math.pi / 2.0)
            scaled_R_max = R_max / angle_ratio if angle_ratio > 0.01 else R_max
            scaled_R_min = R_min / angle_ratio if angle_ratio > 0.01 else R_min

            euler_pts = corner_points(
                tangent,
                "Euler",
                steps,
                self.bezier,
                scaled_R_max,
                scaled_R_min,
            )

            # 记录前一段直波导的轴向信息，用于端点对齐
            prev_is_horizontal = abs(_round_dbu(prev_pt.y) - _round_dbu(start.y)) < 1
            entry_fixed_y = start.y if prev_is_horizontal else None
            entry_fixed_x = start.x if not prev_is_horizontal else None

            # 记录后一段直波导的轴向信息
            next_is_horizontal = abs(_round_dbu(next_pt.y) - _round_dbu(end.y)) < 1
            exit_fixed_y = end.y if next_is_horizontal else None
            exit_fixed_x = end.x if not next_is_horizontal else None

            # 缩放 Euler 点到切线长度
            if len(euler_pts) >= 2:
                x_end = euler_pts[-1][0]
                scale = tangent / x_end if x_end > 1e-9 else 1.0

                for i, (lx, ly) in enumerate(euler_pts[1:], start=1):
                    pt_x = start.x + ux * lx * scale + nx * turn_sign * ly * scale
                    pt_y = start.y + uy * lx * scale + ny * turn_sign * ly * scale

                    # 首点：与前一段直波导轴对齐
                    if i == 1:
                        if entry_fixed_y is not None:
                            pt_y = entry_fixed_y
                        elif entry_fixed_x is not None:
                            pt_x = entry_fixed_x

                    # 末点：与后一段直波导轴对齐
                    if i == len(euler_pts) - 1:
                        if exit_fixed_y is not None:
                            pt_y = exit_fixed_y
                        elif exit_fixed_x is not None:
                            pt_x = exit_fixed_x

                    self._append_point(
                        rounded,
                        pya.DPoint(pt_x, pt_y),
                    )

        self._append_point(rounded, points[-1])
        return rounded

    def _insert_pins(self, points, pin_layer):
        """根据中心线起点和终点生成 opt1/opt2 端口。"""

        if len(points) < 2:
            return

        start = points[0]
        next_pt = points[1]
        prev_pt = points[-2]
        end = points[-1]

        start_dir = self._cardinal_direction(start.x - next_pt.x, start.y - next_pt.y)
        end_dir = self._cardinal_direction(end.x - prev_pt.x, end.y - prev_pt.y)

        self._make_pin("opt1", start, self.wg_width, pin_layer, start_dir)
        self._make_pin("opt2", end, self.wg_width, pin_layer, end_dir)

    def _insert_parameter_text(self, points, text_layer):
        """在 Text 层标注总长度和 delta_L。"""

        if not points:
            return

        min_x = min(point.x for point in points)
        max_x = max(point.x for point in points)
        min_y = min(point.y for point in points)
        max_y = max(point.y for point in points)
        x = int(round((min_x + max_x) * 0.5 / self.layout.dbu))
        y = int(round((min_y + max_y) * 0.5 / self.layout.dbu))
        label = "Paperclip type=%s bend=%s L=%.3fum delta_L=%.3fum" % (
            self.ports_type,
            self.bend_type,
            self.total_length,
            self.delta_L,
        )
        if self.bend_type == "Euler":
            label += " Reff=%.3fum Rmax=%.3fum Rmin=%.3fum" % (
                self.Euler_Reff,
                self.Euler_Rmax,
                self.Euler_Rmin,
            )
        text = pya.Text(label, pya.Trans(pya.Trans.R0, x, y))
        shape = self.cell.shapes(text_layer).insert(text)
        shape.text_halign = 1
        shape.text_valign = 1
        target_box = pya.Box(
            int(round(min_x / self.layout.dbu)),
            int(round(min_y / self.layout.dbu)),
            int(round(max_x / self.layout.dbu)),
            int(round(max_y / self.layout.dbu)),
        )
        shape.text_dsize = self._fit_parameter_text_dsize(
            shape,
            target_box,
            max_x - min_x,
            max_y - min_y,
            label,
        )

    @staticmethod
    def _parameter_text_dsize(width_um, height_um, label):
        """根据 spiral 尺寸估算参数文字大小。"""

        width_um = max(float(width_um), 0.001)
        height_um = max(float(height_um), 0.001)
        char_count = max(1, len(label))
        by_height = height_um * 0.045
        by_width = width_um / (char_count * 0.75)
        return max(0.05, min(by_height, by_width, height_um * 0.12))

    def _fit_parameter_text_dsize(self, shape, target_box, width_um, height_um, label):
        """迭代缩小参数文字，确保 Text bbox 不超出 spiral 中心线范围。"""

        dsize = self._parameter_text_dsize(width_um, height_um, label)
        for _index in range(32):
            shape.text_dsize = dsize
            try:
                bbox = shape.bbox()
            except Exception:
                break
            if bbox.empty():
                break
            if (
                bbox.left >= target_box.left
                and bbox.right <= target_box.right
                and bbox.bottom >= target_box.bottom
                and bbox.top <= target_box.top
            ):
                return dsize
            dsize *= 0.82
            if dsize <= 0.05:
                return 0.05
        return dsize

    def _make_pin(self, name, center, width_um, layer, direction):
        """在 PinRec 图层插入端口文字和 20 nm 短路径。"""

        dbu = self.layout.dbu
        x = int(round(center.x / dbu))
        y = int(round(center.y / dbu))
        width = max(1, int(round(float(width_um) / dbu)))
        half_length = max(1, int(round(0.5 * PIN_LENGTH_UM / dbu)))

        text = pya.Text(name, pya.Trans(pya.Trans.R0, x, y))
        shape = self.cell.shapes(layer).insert(text)
        shape.text_dsize = max(float(width_um) * 0.5, dbu)
        shape.text_valign = 1

        direction = direction % 360
        if direction == 0:
            p1 = pya.Point(x - half_length, y)
            p2 = pya.Point(x + half_length, y)
            shape.text_halign = 2
        elif direction == 90:
            p1 = pya.Point(x, y - half_length)
            p2 = pya.Point(x, y + half_length)
            shape.text_halign = 2
            shape.text_rot = 1
        elif direction == 180:
            p1 = pya.Point(x + half_length, y)
            p2 = pya.Point(x - half_length, y)
            shape.text_halign = 3
        else:
            p1 = pya.Point(x, y + half_length)
            p2 = pya.Point(x, y - half_length)
            shape.text_halign = 3
            shape.text_rot = 1

        self.cell.shapes(layer).insert(pya.Path([p1, p2], width))

    def _path_to_itype(self, points, width_um, dbu):
        """把 um 单位的 DPoint 路径转换成 KLayout 数据库单位 Path。"""

        ipoints = []
        for point in points:
            ipoint = pya.Point(
                int(round(point.x / dbu)),
                int(round(point.y / dbu)),
            )
            if not ipoints or ipoints[-1].x != ipoint.x or ipoints[-1].y != ipoint.y:
                ipoints.append(ipoint)

        if len(ipoints) < 2:
            ipoints.append(pya.Point(ipoints[0].x + 1, ipoints[0].y))

        width = max(1, int(round(float(width_um) / dbu)))
        return pya.Path(ipoints, width)

    def _safe_straight_range(self, points, start_idx, end_idx, dbu):
        """在 [start_idx, end_idx) 范围内寻找严格水平/垂直的安全直波导段。

        返回 (straight_start, straight_end, is_horizontal) 若找到，
        否则返回 None。

        安全条件：
        - 水平段：相邻点 y 坐标在 DBU 舍入后完全相同
        - 垂直段：相邻点 x 坐标在 DBU 舍入后完全相同
        - 不使用角度容差，避免把弯曲切线段误判为直线
        - 总长度 >= 2 * safe_margin_um
        - 返回的段最靠近 end_idx 方向（便于接近 GDS 上限）
        """
        wg_width = max(float(self.wg_width), 1e-6)
        bend_radius = max(
            effective_bend_radius(
                self.bend_type,
                self.bend_radius,
                self.Euler_Rmax,
                self.Euler_Rmin,
            ),
            0.0,
        )
        safe_margin = max(10.0, 0.25 * bend_radius, 5.0 * wg_width)

        def _round_dbu(val):
            """将 um 值舍入到 DBU 网格。"""
            return int(round(val / dbu))

        def _classify_segment(p1, p2):
            """基于坐标严格判断线段方向：'h' = 水平, 'v' = 垂直, None = 非轴向。"""
            x1, y1 = _round_dbu(p1.x), _round_dbu(p1.y)
            x2, y2 = _round_dbu(p2.x), _round_dbu(p2.y)
            if y1 == y2:
                return 'h'
            if x1 == x2:
                return 'v'
            return None

        best_run_start = None
        best_run_end = None
        best_is_h = None

        run_start = start_idx
        while run_start < end_idx - 1:
            seg_type = _classify_segment(points[run_start], points[run_start + 1])
            if seg_type is None:
                run_start += 1
                continue

            # 向后扩展同向线段
            run_end = run_start + 1
            while run_end < end_idx and run_end + 1 < len(points):
                next_type = _classify_segment(points[run_end], points[run_end + 1])
                if next_type != seg_type:
                    break
                run_end += 1

            if run_end > run_start:
                run_length = math.hypot(
                    points[run_end].x - points[run_start].x,
                    points[run_end].y - points[run_start].y,
                )
                if run_length >= 2.0 * safe_margin:
                    best_run_start = run_start
                    best_run_end = run_end
                    best_is_h = (seg_type == 'h')

            run_start = run_end if run_end > run_start else run_start + 1

        if best_run_start is None:
            return None

        return (best_run_start, best_run_end, best_is_h)

    def _split_centerline_on_straights(self, points, max_points):
        """在严格水平/垂直直波导段中部插入 split point，保证邻段连续。

        不再使用角度近似（容易把 89°/91° 弯曲切线误判为直波导）。
        不再允许 fallback 在弯曲段处分段。

        安全要求：
        - split point 所在直线段长度 >= 2 * safe_margin_um
        - split point 取直线段中点，离两端弯曲或折点至少 safe_margin_um
        - 水平段 split point 的 y 取该段固定 y，x 取中点
        - 垂直段 split point 的 x 取该段固定 x，y 取中点
        - 若搜索窗口内无安全直线段，抛出异常
        """
        segments = []
        total = len(points)
        dbu = getattr(getattr(self, "layout", None), "dbu", 0.001)
        start = 0
        prefix = []

        def _round_dbu(val):
            return int(round(val / dbu))

        def _get_fixed_coord(pts, idx_start, idx_end, is_horizontal):
            """获取直段的固定坐标：水平段返回固定 y，垂直段返回固定 x。"""
            if is_horizontal:
                # 水平段：所有点 y 坐标在 DBU 舍入后相同，取第一个点的 y
                return pts[idx_start].y
            else:
                # 垂直段：所有点 x 坐标在 DBU 舍入后相同，取第一个点的 x
                return pts[idx_start].x

        while start < total - 1:
            end = min(total, start + max_points)
            if end >= total:
                seg = prefix + points[start:total]
                if len(seg) >= 2:
                    segments.append(seg)
                break

            found = self._safe_straight_range(points, start, end, dbu)
            split_idx = None

            if found is not None:
                straight_start, straight_end, is_h = found
                # split point 取直线段中点
                split_idx = (straight_start + straight_end) // 2
                # 确保 split_idx 在有效范围内且 split_idx < end
                split_idx = max(straight_start + 1, min(split_idx, end - 1, straight_end - 1))
            else:
                raise RuntimeError(
                    "Paperclip_Spiral：在点数 [%d..%d) 范围内找不到安全直波导段，"
                    "无法进行 GDS 分段。请增加 bend_radius 或减少 points_per_90 后重试。"
                    % (start, end)
                )

            # 计算 split point：使用固定坐标避免 DBU 舍入误差
            # 取 split_idx 和 split_idx+1 的中点，但固定轴坐标取自直段
            mid_x = 0.5 * (points[split_idx].x + points[split_idx + 1].x)
            mid_y = 0.5 * (points[split_idx].y + points[split_idx + 1].y)
            fixed_coord = _get_fixed_coord(points, straight_start, straight_end, is_h)
            if is_h:
                split_point = pya.DPoint(mid_x, fixed_coord)
            else:
                split_point = pya.DPoint(fixed_coord, mid_y)

            seg = prefix + points[start:split_idx + 1]
            seg.append(split_point)
            if len(seg) >= 2:
                segments.append(seg)

            prefix = [split_point]
            start = split_idx + 1

        return segments

    def _insert_centerline_polygons(self, layer, points, width_um, dbu):
        """分段插入中心线扫掠 Polygon，只在直波导段内部分段。

        total_length 和 delta_L 已基于完整 metric_points 计算，GDS 分段不影响。
        """
        width_dbu = max(1, int(round(float(width_um) / dbu)))
        if len(points) <= MAX_GDS_POLYGON_CENTERLINE_POINTS:
            path = self._path_to_itype(points, width_um, dbu)
            insert_centerline_polygons(
                self.cell,
                layer,
                list(path.each_point()),
                width_dbu,
            )
            return

        segments = self._split_centerline_on_straights(
            points,
            MAX_GDS_POLYGON_CENTERLINE_POINTS,
        )
        for segment in segments:
            if len(segment) >= 2:
                path = self._path_to_itype(segment, width_um, dbu)
                insert_centerline_polygons(
                    self.cell,
                    layer,
                    list(path.each_point()),
                    width_dbu,
                )

    @staticmethod
    def _unit_vector(p1, p2):
        """返回 p1 到 p2 的单位向量和线段长度。"""

        dx = p2.x - p1.x
        dy = p2.y - p1.y
        length = math.hypot(dx, dy)
        if length == 0:
            return 0.0, 0.0, 0.0
        return dx / length, dy / length, length

    @staticmethod
    def _append_point(points, point):
        """追加点，同时跳过与上一个点重合的点。"""

        if not points:
            points.append(point)
            return
        if math.hypot(points[-1].x - point.x, points[-1].y - point.y) > 1e-9:
            points.append(point)

    @staticmethod
    def _remove_duplicate_points(points):
        """清理点列中的连续重复点。"""

        clean = []
        for point in points:
            PaperclipSpiral._append_point(clean, point)
        return clean

    @staticmethod
    def _path_length(points):
        """按相邻点距离累加中心线长度。"""

        length = 0.0
        for index in range(1, len(points)):
            length += math.hypot(
                points[index].x - points[index - 1].x,
                points[index].y - points[index - 1].y,
            )
        return length

    @staticmethod
    def _delta_length(points, total_length):
        """计算 delta_L = 总长度 - opt1/opt2 横坐标差绝对值。"""

        if len(points) < 2:
            return 0.0
        return float(total_length) - abs(points[-1].x - points[0].x)

    @staticmethod
    def _cardinal_direction(dx, dy):
        """把方向向量归一到 KLayout pin 常用的 0/90/180/270 度。"""

        if abs(dx) >= abs(dy):
            return 0 if dx >= 0 else 180
        return 90 if dy >= 0 else 270

    @staticmethod
    def _state_to_string(state):
        """兼容读取 PCellParameterState.value 的属性和方法形式。"""

        try:
            value = state.value
            value = value() if callable(value) else value
            return str(value)
        except Exception:
            return str(state)

    @staticmethod
    def _float_or_default(value, fallback):
        """把参数值转换成 float；若为空或无效则使用默认值。"""

        try:
            return float(value)
        except Exception:
            return float(fallback)

    @staticmethod
    def _int_or_default(value, fallback):
        """把参数值转换成 int；若为空或无效则使用默认值。"""

        try:
            return int(value)
        except Exception:
            return int(fallback)


__all__ = ["PaperclipSpiral"]
