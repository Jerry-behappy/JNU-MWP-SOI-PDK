# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""回形针螺旋波导，含直波导与弯曲不同宽度的 Composite Waveguide PCell。

在直波导段和弯曲段之间插入 taper 实现宽度过渡。
gap 精确按直波导生效，即 centerline pitch = straight_width + gap。
短内部连接段出现时 taper 自动缩短以避免拓扑错误。
"""

import math
import os
import sys

import pya

from .taper import taper_polygon_between

from .paperclip_spiral import (
    BEND_TYPE_CHOICES,
    PORTS_TYPE_CHOICES,
    WG_LAYER_CHOICES,
    PIN_LAYER_CHOICES,
    TYPE3_OPT1_STRAIGHT_UM,
    _choice_values,
    _coerce_bezier,
    _normalize_bend_type,
    _normalize_ports_type,
    _layer_info_from_choice,
    _port_extension_point,
    calculate_paperclip_bend_values,
    effective_bend_radius,
)

try:
    from .pcell_defaults import (
        default_bool, default_choice, default_float, default_int,
    )
except ImportError:
    PCELL_DIR = os.path.dirname(os.path.abspath(__file__))
    if PCELL_DIR not in sys.path:
        sys.path.insert(0, PCELL_DIR)
    from pcell_defaults import (
        default_bool, default_choice, default_float, default_int,
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
from .bend_90deg import corner_points

PCELL_NAME = "Paperclip_Spiral_with_Composite_Waveguide"
DEFAULT_STRAIGHT_WIDTH = 0.5
DEFAULT_BEND_WIDTH = 1.0
DEFAULT_TAPER_LENGTH = 20.0
DEFAULT_BEZIER = 0.35
DEFAULT_EULER_RMAX = 30.0
DEFAULT_EULER_RMIN = 10.0
PIN_LENGTH_UM = 0.02
TEXT_LAYER = pya.LayerInfo(10, 0)
POLYGON_JOIN_TOLERANCE_DBU = 5


class PaperclipSpiralWithCompositeWaveguide(pya.PCellDeclarationHelper):
    """回形针螺旋波导 — 直段/弯曲不同宽度，含 taper。"""

    def __init__(self):
        super().__init__()
        bend_type_default = _normalize_bend_type(default_choice(PCELL_NAME, "bend_type", "Circular", BEND_TYPE_CHOICES))
        ports_type_default = _normalize_ports_type(default_choice(PCELL_NAME, "ports_type", "type1", _choice_values(PORTS_TYPE_CHOICES)))
        wg_param = self.param("wg_layer", self.TypeList, "Waveguide layer", default=default_choice(PCELL_NAME, "wg_layer", "1/0", _choice_values(WG_LAYER_CHOICES)))
        for v, l in WG_LAYER_CHOICES: wg_param.add_choice(l, v)
        pin_param = self.param("pin_layer", self.TypeList, "Pin layer", default=default_choice(PCELL_NAME, "pin_layer", "1/10", _choice_values(PIN_LAYER_CHOICES)))
        for v, l in PIN_LAYER_CHOICES: pin_param.add_choice(l, v)
        self.param("length", self.TypeDouble, "Inner length", unit="um", default=default_float(PCELL_NAME, "length", 100.0))
        self.param("straight_width", self.TypeDouble, "Straight width", unit="um", default=default_float(PCELL_NAME, "straight_width", DEFAULT_STRAIGHT_WIDTH))
        self.param("bend_width", self.TypeDouble, "Bend width", unit="um", default=default_float(PCELL_NAME, "bend_width", DEFAULT_BEND_WIDTH))
        self.param("taper_length", self.TypeDouble, "Taper length", unit="um", default=default_float(PCELL_NAME, "taper_length", DEFAULT_TAPER_LENGTH))
        self.bend_radius_param = self.param("bend_radius", self.TypeDouble, "Bend radius", unit="um", default=default_float(PCELL_NAME, "bend_radius", 10.0))
        self.param("gap", self.TypeDouble, "Gap", unit="um", default=default_float(PCELL_NAME, "gap", 2.0))
        self.param("loops", self.TypeInt, "Loops", default=default_int(PCELL_NAME, "loops", 2))
        ports_param = self.param("ports_type", self.TypeList, "Ports type", default=ports_type_default)
        for v, l in PORTS_TYPE_CHOICES: ports_param.add_choice(l, v)
        bend_param = self.param("bend_type", self.TypeList, "Bend type", default=bend_type_default)
        for c in BEND_TYPE_CHOICES: bend_param.add_choice(c, c)
        self.bezier_param = self.param("bezier", self.TypeDouble, "Bezier", default=default_float(PCELL_NAME, "bezier", DEFAULT_BEZIER))
        try: self.bezier_param.hidden = bend_type_default != "Bezier"
        except Exception: pass

        # Euler 弯曲参数
        self.Euler_Rmax_param = self.param("Euler_Rmax", self.TypeDouble, "Euler Rmax", unit="um", default=default_float(PCELL_NAME, "Euler_Rmax", DEFAULT_EULER_RMAX))
        self.Euler_Rmin_param = self.param("Euler_Rmin", self.TypeDouble, "Euler Rmin", unit="um", default=default_float(PCELL_NAME, "Euler_Rmin", DEFAULT_EULER_RMIN))
        self.param("vertical_stretch", self.TypeDouble, "Vertical stretch", unit="um", default=default_float(PCELL_NAME, "vertical_stretch", 0.0))

        # 只读派生参数统一放在全部可编辑参数之后。
        self.Bezier_Rmax_param = self.param("Bezier_Rmax", self.TypeDouble, "Bezier Rmax [uneditable]", unit="um", default=0.0, readonly=True)
        self.Bezier_Rmin_param = self.param("Bezier_Rmin", self.TypeDouble, "Bezier Rmin [uneditable]", unit="um", default=0.0, readonly=True)
        self.Euler_Reff_param = self.param("Euler_Reff", self.TypeDouble, "Euler Reff [uneditable]", unit="um", default=0.0, readonly=True)
        self.param("points_per_90", self.TypeInt, "Points/90° [uneditable]", default=points_per_90(max(DEFAULT_STRAIGHT_WIDTH, 10.0), 0.001), readonly=True)
        self.param("total_length", self.TypeDouble, "Total length [uneditable]", unit="um", default=0.0, readonly=True)
        self.param("delta_L", self.TypeDouble, "delta_L [uneditable]", unit="um", default=0.0, readonly=True)

    def display_text_impl(self):
        """返回包含全部用户参数的 cell 名称（排除弯曲点数、波导层）。"""
        if self.bend_type == "Euler":
            base = "CompPclip(L=%.3f,Reff=%.3f,N=%d,ws=%.3f,wb=%.3f,gap=%.3f,taper=%.3f,%s,%s" % (
                self.total_length, self.Euler_Reff, self.loops,
                self.straight_width, self.bend_width, self.gap, self.taper_length,
                self.ports_type, self.bend_type,
            )
        else:
            base = "CompPclip(L=%.3f,R=%.3f,N=%d,ws=%.3f,wb=%.3f,gap=%.3f,taper=%.3f,%s,%s" % (
                self.total_length, self.bend_radius, self.loops,
                self.straight_width, self.bend_width, self.gap, self.taper_length,
                self.ports_type, self.bend_type,
            )
        if self.bend_type == "Bezier":
            base += ",B=%.3f" % self.bezier
        elif self.bend_type == "Euler":
            base += ",Rmax=%.3f,Rmin=%.3f" % (self.Euler_Rmax, self.Euler_Rmin)
        if float(self.vertical_stretch) > 0:
            base += ",vs=%.1f" % self.vertical_stretch
        return base + ")"

    def coerce_parameters_impl(self):
        dbu = self.layout.dbu or 0.001
        self.straight_width = max(self._fval(self.straight_width, DEFAULT_STRAIGHT_WIDTH), dbu)
        self.bend_width = max(self._fval(self.bend_width, DEFAULT_BEND_WIDTH), dbu)
        self.taper_length = max(self._fval(self.taper_length, DEFAULT_TAPER_LENGTH), 0.0)
        self.bend_radius = max(self._fval(self.bend_radius, 10.0), max(self.straight_width, self.bend_width))
        self.gap = max(self._fval(self.gap, 2.0), 0.0)
        self.loops = max(self._ival(self.loops, 2), 1)
        self.vertical_stretch = max(self._fval(self.vertical_stretch, 0.0), 0.0)
        self.bend_type = _normalize_bend_type(getattr(self, "bend_type", "Circular"))
        self.ports_type = self._port_type()
        self.bezier = _coerce_bezier(self._fval(getattr(self, "bezier", DEFAULT_BEZIER), DEFAULT_BEZIER))

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
            max(self.straight_width, self.bend_width),
            dbu,
        )
        self.length = max(self._fval(self.length, 100.0), 2.0 * derived["effective_radius"])
        self.points_per_90 = derived["points_per_90"]
        if derived["Bezier_Rmax"] is not None:
            self.Bezier_Rmax = round(derived["Bezier_Rmax"], 3)
            self.Bezier_Rmin = round(derived["Bezier_Rmin"], 3)
        if derived["Euler_Reff"] is not None:
            self.Euler_Reff = round(derived["Euler_Reff"], 3)

        waypoints = self._centerline_waypoints()
        rounded, _ = self._rounded_with_primitives(waypoints)
        self.total_length = round(self._plen(rounded), 3)
        self.delta_L = round(
            float(self.total_length) - abs(rounded[-1].x - rounded[0].x)
            if len(rounded) >= 2 else 0.0,
            3,
        )

    def _state_to_string(self, state):
        """从 GUI 参数状态读取字符串值。"""
        try:
            value = state.value
            value = value() if callable(value) else value
            return str(value)
        except Exception:
            return str(state)

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

    def _update_points_composite(self):
        """根据当前弯曲类型和半径刷新自适应弯曲点数。"""
        dbu = getattr(self, "_dbu", 0.001)

        try:
            bend_type = self._state_to_string(self.bend_type).lower()
        except Exception:
            bend_type = "circular"

        if bend_type == "euler":
            try:
                rmax_val = self._state_to_float(self.Euler_Rmax, DEFAULT_EULER_RMAX)
                rmin_val = self._state_to_float(self.Euler_Rmin, DEFAULT_EULER_RMIN)
                if rmax_val > rmin_val > 0:
                    reff = euler_Reff(rmax_val, rmin_val)
                else:
                    reff = rmax_val
            except Exception:
                reff = self._state_to_float(self.bend_radius, 10.0)
        else:
            reff = self._state_to_float(self.bend_radius, 10.0)

        radius = max(
            self._state_to_float(self.straight_width, DEFAULT_STRAIGHT_WIDTH),
            reff,
        )
        self._set_state_value(self.points_per_90, points_per_90(radius, dbu))

    def callback(self, layout, name, states):
        """保持 KLayout 标准回调流程。"""
        try:
            self._dbu = layout.dbu
        except Exception:
            self._dbu = 0.001
        return super().callback(layout, name, states)

    def callback_impl(self, name):
        """用户编辑参数时，动态显示/隐藏参数并实时更新依赖值。"""
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
                "straight_width": float(self._state_to_string(self.straight_width)),
                "bend_width": float(self._state_to_string(self.bend_width)),
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
                max(values["straight_width"], values["bend_width"]),
                getattr(self, "_dbu", 0.001),
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
            waypoints = self._centerline_waypoints(values)
            rounded, _ = self._rounded_with_primitives(waypoints, values)
            total_length = round(self._plen(rounded), 3)
            delta_l = round(
                total_length - abs(rounded[-1].x - rounded[0].x)
                if len(rounded) >= 2 else 0.0,
                3,
            )
            self._set_state_value(self.total_length, total_length)
            self._set_state_value(self.delta_L, delta_l)
        except Exception:
            for state in (
                self.Bezier_Rmax,
                self.Bezier_Rmin,
                self.Euler_Reff,
                self.points_per_90,
                self.total_length,
                self.delta_L,
            ):
                self._set_state_value(state, "")
            try:
                bend_type = _normalize_bend_type(self._state_to_string(self.bend_type))
                self.bend_radius_param.hidden = bend_type == "Euler"
                self.bezier_param.hidden = bend_type != "Bezier"
            except Exception:
                pass

    def produce_impl(self):
        waypoints = self._centerline_waypoints()
        rounded, prims = self._rounded_with_primitives(waypoints)
        dbu = self.layout.dbu
        wg_layer = self.layout.layer(_layer_info_from_choice(self.wg_layer, pya.LayerInfo(1, 0)))
        pin_layer = self.layout.layer(_layer_info_from_choice(self.pin_layer, pya.LayerInfo(1, 10)))
        self._draw_composite_from_primitives(wg_layer, rounded, prims, dbu)

        # 为 Si 完全覆盖 PinRec，在端口外侧增加 10 nm 水平延伸。
        if len(rounded) >= 2:
            start = rounded[0]
            start_dir = self._cdir(
                start.x - rounded[1].x, start.y - rounded[1].y
            )
            ext_start = _port_extension_point(start, start_dir, TYPE3_OPT1_STRAIGHT_UM)
            self._insert_centerline_polygon(wg_layer, [start, ext_start],
                           self.straight_width if start_dir in (0, 180) else self.bend_width, dbu)

            end = rounded[-1]
            end_dir = self._cdir(
                end.x - rounded[-2].x, end.y - rounded[-2].y
            )
            ext_end = _port_extension_point(end, end_dir, TYPE3_OPT1_STRAIGHT_UM)
            self._insert_centerline_polygon(wg_layer, [end, ext_end],
                           self.straight_width if end_dir in (0, 180) else self.bend_width, dbu)

        self._merge_waveguide_polygons(wg_layer)
        self._insert_pins(rounded, pin_layer)
        insert_device_devrec(self.cell, wg_layer, pin_layer)
        self._insert_text(rounded, self.layout.layer(TEXT_LAYER))

    # ============ geometry (waypoints & rounded) ============

    def _centerline_waypoints(self, values=None):
        values = values or {}
        bend_type = values.get("bend_type", self.bend_type)
        bend_radius = values.get("bend_radius", self.bend_radius)
        euler_rmax = values.get("Euler_Rmax", self.Euler_Rmax)
        euler_rmin = values.get("Euler_Rmin", self.Euler_Rmin)
        R = float(values.get(
            "effective_radius",
            effective_bend_radius(bend_type, bend_radius, euler_rmax, euler_rmin),
        ))
        straight_width = float(values.get("straight_width", self.straight_width))
        gap = float(values.get("gap", self.gap))
        pitch = straight_width + gap
        L0 = max(float(values.get("length", self.length)), 2.0 * R); off = R
        loops = int(values.get("loops", self.loops))
        ports_type = values.get("ports_type", self.ports_type)
        pts = [pya.DPoint(-L0, off), pya.DPoint(0, off), pya.DPoint(0, -off), pya.DPoint(L0, -off)]
        li = 1
        for i in range(1, loops * 2, 2):
            li = i
            pts.insert(0, pya.DPoint(-L0-pitch*(i-1), off-2.0*R-pitch*(i-1)-pitch))
            pts.insert(0, pya.DPoint(L0+pitch*i, off-2.0*R-pitch*(i-1)-pitch))
            pts.insert(0, pya.DPoint(L0+pitch*i, -off+2.0*R+pitch*i+pitch))
            pts.insert(0, pya.DPoint(-L0-pitch*(i+1), -off+2.0*R+pitch*i+pitch))
            pts.append(pya.DPoint(L0+pitch*(i-1), 2.0*R-off+pitch*(i-1)+pitch))
            pts.append(pya.DPoint(-L0-pitch*i, 2.0*R-off+pitch*(i-1)+pitch))
            pts.append(pya.DPoint(-L0-pitch*i, -2.0*R+off-pitch*i-pitch))
            pts.append(pya.DPoint(L0+pitch*(i+1), -2.0*R+off-pitch*i-pitch))
        if ports_type == "type1":
            pts.append(pya.DPoint(L0+pitch*(li+1), 2.0*R-off+pitch*(li+1)+pitch))
            pts.append(pya.DPoint(-L0-pitch*(li+1), 2.0*R-off+pitch*(li+1)+pitch))
        pts.pop(0)
        pts.insert(0, pya.DPoint(-L0-pitch*(li+1), -off+2.0*R+pitch*li+pitch))
        pts = self._dedup(pts)
        if ports_type == "type3": pts = self._type3_jog(pts, pitch, values)
        return self._vertical_stretch(pts, values)

    def _type3_jog(self, pts, gap, values=None):
        if len(pts) < 2: return pts
        os_, end = pts[0], pts[-1]
        if abs(os_.y - end.y) <= 1e-9: return pts
        values = values or {}
        lead = TYPE3_OPT1_STRAIGHT_UM + float(values.get(
            "effective_radius",
            effective_bend_radius(
                values.get("bend_type", self.bend_type),
                values.get("bend_radius", self.bend_radius),
                values.get("Euler_Rmax", self.Euler_Rmax),
                values.get("Euler_Rmin", self.Euler_Rmin),
            ),
        ))
        return self._dedup([pya.DPoint(os_.x - lead, end.y), pya.DPoint(os_.x, end.y), pya.DPoint(os_.x, os_.y)] + list(pts[1:]))

    def _vertical_stretch(self, pts, values=None):
        values = values or {}
        s = max(float(values.get("vertical_stretch", self.vertical_stretch)), 0.0)
        if s <= 0 or len(pts) < 2: return pts
        mn, mx = min(p.y for p in pts), max(p.y for p in pts)
        h = mx - mn
        if h <= 1e-12: return pts
        cy, mg = 0.5*(mn+mx), max(1e-6, (float(values.get("straight_width", self.straight_width))+float(values.get("gap", self.gap)))*0.1)
        up, lo = [], []
        for p in pts:
            if p.y-cy > mg: up.append(p)
            elif p.y-cy < -mg: lo.append(p)
        if not up and not lo: return pts
        hs, out = s*0.5, []
        for p in pts:
            d = p.y-cy
            if d > mg: out.append(pya.DPoint(p.x, p.y+hs))
            elif d < -mg: out.append(pya.DPoint(p.x, p.y-hs))
            else:
                if up and lo:
                    t, b = min(o.y for o in up)+hs, max(o.y for o in lo)-hs
                    out.append(pya.DPoint(p.x, b+(p.y-b)/max(t-b,1e-12)*(t-b)))
                else: out.append(p)
        return out

    def _rounded_with_primitives(self, wpts, values=None):
        """返回 (rounded_points, ordered_primitives).

        primitives 列表包含类型 "straight" 和 "bend"。
        bend 的 data 包含 {'entry','exit','arc_pts'}。
        """
        values = values or {}
        dbu = getattr(self.layout, 'dbu', 0.001)
        bend_type = _normalize_bend_type(values.get("bend_type", getattr(self, "bend_type", "Circular")))
        euler_Rmax = float(values.get("Euler_Rmax", getattr(self, "Euler_Rmax", DEFAULT_EULER_RMAX)))
        euler_Rmin = float(values.get("Euler_Rmin", getattr(self, "Euler_Rmin", DEFAULT_EULER_RMIN)))
        R = effective_bend_radius(
            bend_type,
            values.get("bend_radius", self.bend_radius),
            euler_Rmax,
            euler_Rmin,
        )
        p90 = effective_points_per_90(int(values.get("points_per_90", self.points_per_90)), R, dbu)
        bezier = float(values.get("bezier", getattr(self, "bezier", DEFAULT_BEZIER)))

        if len(wpts) < 3 or R <= 0:
            return wpts, [{"type":"straight","pts":wpts}]

        rounded = [wpts[0]]
        prims = []
        last_corner_idx = 0

        # 起点到第一个拐角前为一条 straight
        prims.append({"type":"straight","pts":[wpts[0]]})

        for i in range(1, len(wpts) - 1):
            prev, corner, nxt = wpts[i-1], wpts[i], wpts[i+1]
            ux, uy, li = self._uv(prev, corner)
            vx, vy, lo = self._uv(corner, nxt)
            if li <= 0 or lo <= 0:
                self._ap(rounded, corner)
                continue
            dot = max(-1.0, min(1.0, ux*vx+uy*vy))
            cross = ux*vy - uy*vx
            ta = math.acos(dot)
            if abs(cross) < 1e-9 or ta < 1e-9:
                self._ap(rounded, corner)
                continue
            t = R * math.tan(0.5*ta)
            t = min(
                t,
                max(0.0, li - TYPE3_OPT1_STRAIGHT_UM),
                max(0.0, lo - TYPE3_OPT1_STRAIGHT_UM),
            )
            ar = t / math.tan(0.5*ta)
            entry = pya.DPoint(corner.x - ux*t, corner.y - uy*t)
            exit_pt = pya.DPoint(corner.x + vx*t, corner.y + vy*t)

            # 直段：从上一个 exit 到当前 entry
            if len(prims) > 0 and prims[-1]["type"] == "straight":
                prims[-1]["pts"].append(entry)
            else:
                prims.append({"type":"straight","pts":[entry]})

            self._ap(rounded, entry)
            arc_pts = []
            turn_sign = 1.0 if cross > 0 else -1.0
            nx, ny = -uy, ux
            steps = max(2, int(math.ceil(abs(ta)/(0.5*math.pi)*p90)))
            local_pts = corner_points(
                t,
                bend_type,
                steps,
                bezier,
                euler_Rmax,
                euler_Rmin,
            )
            for lx, ly in local_pts[1:]:
                pt = pya.DPoint(
                    entry.x + ux*lx + nx*turn_sign*ly,
                    entry.y + uy*lx + ny*turn_sign*ly,
                )
                arc_pts.append(pt)
                self._ap(rounded, pt)

            self._ap(rounded, exit_pt)
            prims.append({"type":"bend","entry":entry,"exit":exit_pt,"arc_pts":arc_pts})
            prims.append({"type":"straight","pts":[exit_pt]})

        # 最后一段 straight 到达终点
        prims[-1]["pts"].append(wpts[-1])
        self._ap(rounded, wpts[-1])

        return rounded, prims

    # ============ composite drawing ============

    def _draw_composite_from_primitives(self, layer, rounded, prims, dbu):
        sw = max(1, int(round(float(self.straight_width)/dbu)))
        bw = max(1, int(round(float(self.bend_width)/dbu)))
        taper = max(1, int(round(float(self.taper_length)/dbu))) if sw != bw else 0
        tol = max(1, int(round(1.0/dbu)))

        for p in prims:
            if p["type"] == "bend":
                arc = p["arc_pts"]
                for sub in self._split_on_straights(arc, 4000):
                    if len(sub) >= 2:
                        self._insert_centerline_polygon(layer, sub, bw, dbu)
            elif p["type"] == "straight":
                pts = p["pts"]
                if len(pts) < 2: continue
                total = int(round(math.hypot(pts[-1].x-pts[0].x, pts[-1].y-pts[0].y)/dbu))
                if total <= 0: continue
                self._draw_straight_seg(layer, pts, sw, bw, taper, tol, dbu)

    def _is_horizontal(self, pts):
        """判断直段是否为水平方向。"""
        if len(pts) < 2: return True
        return abs(pts[-1].y - pts[0].y) <= abs(pts[-1].x - pts[0].x)

    def _draw_straight_seg(self, layer, pts, sw, bw, tlen, tol, dbu, pin_start=False, pin_end=False):
        """在直段端点处配 taper，中段均匀。

        横向直段用 sw，纵向直段用 bw。taper 只在横/纵交接且宽度不同时放置。
        """
        if len(pts) < 2: return
        is_h = self._is_horizontal(pts)
        my_w = sw if is_h else bw  # 横向=straight_width, 纵向=bend_width
        need_taper = sw != bw

        sx, sy = pts[0].x, pts[0].y
        ex, ey = pts[-1].x, pts[-1].y
        dx, dy = ex-sx, ey-sy
        total = int(round(math.hypot(dx, dy)/dbu))
        if total <= 0: return
        ux, uy = dx/total/dbu, dy/total/dbu
        nx, ny = -dy/total/dbu, dx/total/dbu

        # 短直段没有足够空间放置 taper 时，严格按实际端点绘制，禁止被 tol 扩长。
        if total < tlen + tol:
            self._insert_centerline_polygon(layer, pts, my_w, dbu)
            return

        # 若是纵向直段（bend_width），不放 taper，直接画均匀段
        if not is_h:
            self._insert_centerline_polygon(layer, pts, bw, dbu)
            return

        # 横向直段：taper 仅在邻接纵向或弯曲时放置
        used = 0
        if need_taper and not pin_start and total >= tlen+tol:
            end = min(tlen, total)
            taper_polygon_between(self.cell, layer,
                pya.Point(int(round(sx/dbu)), int(round(sy/dbu))),
                pya.Point(int(round((sx+ux*end*dbu)/dbu)), int(round((sy+uy*end*dbu)/dbu))),
                bw, sw, nx, ny)
            used = end
        r_start = total - tlen if need_taper and not pin_end and total >= tlen+tol else total
        r_start = max(r_start, used+tol)
        if r_start > used:
            msx, msy = int(round((sx+ux*used*dbu)/dbu)), int(round((sy+uy*used*dbu)/dbu))
            mex, mey = int(round((sx+ux*r_start*dbu)/dbu)), int(round((sy+uy*r_start*dbu)/dbu))
            self._insert_centerline_polygon(
                layer,
                [pya.DPoint(msx * dbu, msy * dbu), pya.DPoint(mex * dbu, mey * dbu)],
                sw,
                dbu,
            )
            used = r_start
        if need_taper and not pin_end and used < total - tol:
            taper_polygon_between(self.cell, layer,
                pya.Point(int(round((sx+ux*used*dbu)/dbu)), int(round((sy+uy*used*dbu)/dbu))),
                pya.Point(int(round(ex/dbu)), int(round(ey/dbu))),
                sw, bw, nx, ny)

    def _insert_centerline_polygon(self, layer, pts, width, dbu):
        if len(pts) < 2: return
        insert_centerline_polygons(
            self.cell,
            layer,
            [pya.Point(int(round(p.x/dbu)), int(round(p.y/dbu))) for p in pts],
            max(1, int(width)),
        )

    def _merge_waveguide_polygons(self, layer):
        """合并直段、taper 与弯曲 Polygon，并闭合 DBU 舍入产生的微小缝隙。"""

        region = pya.Region(self.cell.begin_shapes_rec(layer))
        region.merge()
        region.size(POLYGON_JOIN_TOLERANCE_DBU)
        region.size(-POLYGON_JOIN_TOLERANCE_DBU)
        region.merge()
        self.cell.shapes(layer).clear()
        for polygon in region.each():
            self.cell.shapes(layer).insert(polygon)

    def _split_on_straights(self, pts, mx):
        """在严格水平/垂直直波导段内部分段，禁止在弯曲段分段。

        使用严格坐标判断：
        - 水平段：相邻点 y 坐标在 DBU 舍入后完全相同
        - 垂直段：相邻点 x 坐标在 DBU 舍入后完全相同
        - 若找不到安全直段，抛出异常而不是在弯曲段强行切分
        """
        if len(pts) <= mx:
            return [pts]

        dbu = getattr(getattr(self, "layout", None), "dbu", 0.001)
        effective_radius = effective_bend_radius(
            self.bend_type,
            self.bend_radius,
            self.Euler_Rmax,
            self.Euler_Rmin,
        )
        safe_margin = max(
            10.0,
            0.25 * effective_radius,
            5.0 * max(float(self.straight_width), float(self.bend_width)),
        )

        def _round_dbu(val):
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

        segs = []
        start = 0
        prefix = []

        while start < len(pts) - 1:
            end = min(len(pts), start + mx)
            if end >= len(pts):
                seg = prefix + pts[start:]
                if len(seg) >= 2:
                    segs.append(seg)
                break

            # 在 [start, end) 范围内寻找安全直段
            found_start = None
            found_end = None
            found_is_h = None

            run_start = start
            while run_start < end - 1:
                seg_type = _classify_segment(pts[run_start], pts[run_start + 1])
                if seg_type is None:
                    run_start += 1
                    continue

                # 向后扩展同向线段
                run_end = run_start + 1
                while run_end < end and run_end + 1 < len(pts):
                    next_type = _classify_segment(pts[run_end], pts[run_end + 1])
                    if next_type != seg_type:
                        break
                    run_end += 1

                # 检查长度是否足够，并与当前有效弯曲半径保持安全距离。
                if run_end > run_start:
                    run_length = math.hypot(
                        pts[run_end].x - pts[run_start].x,
                        pts[run_end].y - pts[run_start].y,
                    )
                    if run_length >= 2.0 * safe_margin:
                        found_start = run_start
                        found_end = run_end
                        found_is_h = (seg_type == 'h')
                        break  # 找到第一个安全直段就用

                run_start = run_end if run_end > run_start else run_start + 1

            if found_start is None:
                raise RuntimeError(
                    "Composite Waveguide：在点数 [%d..%d) 范围内找不到安全直波导段，"
                    "无法进行 GDS 分段。请减少 points_per_90 或增加 bend_radius 后重试。"
                    % (start, end)
                )

            # split point 取直段中点，使用固定坐标
            split_idx = (found_start + found_end) // 2
            split_idx = max(found_start + 1, min(split_idx, end - 1, found_end - 1))

            mid_x = 0.5 * (pts[split_idx].x + pts[split_idx + 1].x)
            mid_y = 0.5 * (pts[split_idx].y + pts[split_idx + 1].y)

            # 获取固定坐标
            if found_is_h:
                fixed_coord = pts[found_start].y
                split_point = pya.DPoint(mid_x, fixed_coord)
            else:
                fixed_coord = pts[found_start].x
                split_point = pya.DPoint(fixed_coord, mid_y)

            seg = prefix + pts[start:split_idx + 1]
            seg.append(split_point)
            if len(seg) >= 2:
                segs.append(seg)

            prefix = [split_point]
            start = split_idx + 1

        return segs

    # ============ pins / text ============

    def _insert_pins(self, pts, layer):
        if len(pts) < 2: return
        sw = float(self.straight_width)
        bw = float(self.bend_width)

        # opt1 端口宽度：根据端口方向决定（水平用 sw，垂直用 bw）
        dir1 = self._cdir(pts[0].x-pts[1].x, pts[0].y-pts[1].y)
        w1 = sw if dir1 in (0, 180) else bw
        self._mkpin("opt1", pts[0], w1, layer, dir1)

        # opt2 端口宽度
        dir2 = self._cdir(pts[-1].x-pts[-2].x, pts[-1].y-pts[-2].y)
        w2 = sw if dir2 in (0, 180) else bw
        self._mkpin("opt2", pts[-1], w2, layer, dir2)

    def _insert_text(self, pts, layer):
        if not pts: return
        x, y = int(round((min(p.x for p in pts)+max(p.x for p in pts))*0.5/self.layout.dbu)), int(round((min(p.y for p in pts)+max(p.y for p in pts))*0.5/self.layout.dbu))
        lbl = "CPclip L=%.3f dL=%.3f" % (self.total_length, self.delta_L)
        if self.bend_type == "Euler":
            lbl += " Reff=%.3f Rmax=%.3f Rmin=%.3f" % (
                self.Euler_Reff,
                self.Euler_Rmax,
                self.Euler_Rmin,
            )
        tx = pya.Text(lbl, pya.Trans(pya.Trans.R0, x, y))
        sh = self.cell.shapes(layer).insert(tx)
        sh.text_halign = sh.text_valign = 1

    def _mkpin(self, name, center, w_um, layer, direction):
        dbu = self.layout.dbu
        x, y = int(round(center.x/dbu)), int(round(center.y/dbu))
        w = max(1, int(round(float(w_um)/dbu)))
        hl = max(1, int(round(0.5*PIN_LENGTH_UM/dbu)))
        tx = pya.Text(name, pya.Trans(pya.Trans.R0, x, y))
        sh = self.cell.shapes(layer).insert(tx)
        sh.text_dsize = max(float(w_um)*0.5, dbu)
        sh.text_valign = 1
        direction %= 360
        if direction == 0: p1, p2 = pya.Point(x-hl, y), pya.Point(x+hl, y); sh.text_halign = 2
        elif direction == 90: p1, p2 = pya.Point(x, y-hl), pya.Point(x, y+hl); sh.text_halign = 2; sh.text_rot = 1
        elif direction == 180: p1, p2 = pya.Point(x+hl, y), pya.Point(x-hl, y); sh.text_halign = 3
        else: p1, p2 = pya.Point(x, y+hl), pya.Point(x, y-hl); sh.text_halign = 3; sh.text_rot = 1
        self.cell.shapes(layer).insert(pya.Path([p1, p2], w))

    # ============ utilities ============

    @staticmethod
    def _uv(p1, p2): dx, dy = p2.x-p1.x, p2.y-p1.y; L = math.hypot(dx, dy); return (dx/L, dy/L, L) if L else (0,0,0)
    @staticmethod
    def _ap(pts, pt):
        if not pts or math.hypot(pts[-1].x-pt.x, pts[-1].y-pt.y) > 1e-9: pts.append(pt)
    @staticmethod
    def _dedup(pts):
        clean = []
        for p in pts: PaperclipSpiralWithCompositeWaveguide._ap(clean, p)
        return clean
    @staticmethod
    def _plen(points): return sum(math.hypot(points[i].x-points[i-1].x, points[i].y-points[i-1].y) for i in range(1, len(points)))
    @staticmethod
    def _cdir(dx, dy): return 0 if abs(dx)>=abs(dy) and dx>=0 else 180 if abs(dx)>=abs(dy) else 90 if dy>=0 else 270
    @staticmethod
    def _fval(val, fb):
        try: return float(val)
        except Exception: return float(fb)
    @staticmethod
    def _ival(val, fb):
        try: return int(val)
        except Exception: return int(fb)
    def _port_type(self):
        raw = str(getattr(self, "ports_type", ""))
        return raw if raw in _choice_values(PORTS_TYPE_CHOICES) else "type1"

__all__ = ["PaperclipSpiralWithCompositeWaveguide"]
