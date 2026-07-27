# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""直段与弯曲采用不同宽度的可逆 Waveguide PCell。"""

import math
import os
import sys

import pya

try:
    from .pcell_defaults import default_choice, default_float, save_pcell_defaults
except ImportError:
    PCELL_DIR = os.path.dirname(os.path.abspath(__file__))
    if PCELL_DIR not in sys.path:
        sys.path.insert(0, PCELL_DIR)
    from pcell_defaults import default_choice, default_float, save_pcell_defaults

PYMACROS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PYMACROS_DIR not in sys.path:
    sys.path.insert(0, PYMACROS_DIR)

from JNU_MWP_tools.core.bend_curvature import bezier_Rmax_Rmin, euler_Reff
from JNU_MWP_tools.core.bend_sampling import AUTO_SAMPLE_COUNT, effective_points_per_90

from .bend_90deg import _normalize_bend_type, corner_points
from .waveguide import (
    DEVREC_LAYER,
    DEVREC_SIDE_CLEARANCE_UM,
    PIN_LAYER,
    SI_LAYER,
    TEXT_LAYER,
    _dedupe_points,
    _dpath_to_integer_path,
    _distance,
    _ensure_tools_path,
    _left_normal,
    _local_to_global,
    _path_length_um,
    _pin_direction,
    _store_raw_manhattan_path,
    _to_itype,
    _unit_step,
)


PCELL_NAME = "Composite_Waveguide"
DEFAULT_STRAIGHT_WIDTH = 2.0
DEFAULT_BEND_WIDTH = 0.5
DEFAULT_TAPER_LENGTH = 20.0
DEFAULT_TRANSITION_LENGTH = 2.0
DEFAULT_RADIUS = 30.0
DEFAULT_BEZIER_K = 0.3
DEFAULT_EULER_RMAX = 30.0
DEFAULT_EULER_RMIN = 10.0


def _canonical_points(points):
    """去除重复点和同向共线点，保留真正的Manhattan转角。"""
    clean = _dedupe_points(points)
    result = []
    for point in clean:
        result.append(point)
        while len(result) >= 3:
            a, b, c = result[-3:]
            ab = _unit_step(b - a)
            bc = _unit_step(c - b)
            if ab == bc:
                result.pop(-2)
            else:
                break
    return result


def build_route_primitives(points, radius_dbu, bend_type, npoints, bezier_k, euler_rmax, euler_rmin):
    """把Manhattan中心线拆成顺序明确的straight/bend primitive。"""
    points = _canonical_points(points)
    if len(points) < 2:
        return [], []
    if len(points) == 2:
        return [{"type": "straight", "start": points[0], "end": points[1]}], points

    primitives = []
    rounded = [points[0]]
    straight_start = points[0]
    for index in range(1, len(points) - 1):
        previous, corner, following = points[index - 1], points[index], points[index + 1]
        unit_in = _unit_step(corner - previous)
        unit_out = _unit_step(following - corner)
        cross = unit_in.x * unit_out.y - unit_in.y * unit_out.x
        if cross == 0:
            raise ValueError("Path包含180度折返或无效共线转角。")

        entry = corner - unit_in * int(radius_dbu)
        exit_point = corner + unit_out * int(radius_dbu)
        if straight_start != entry:
            primitives.append({"type": "straight", "start": straight_start, "end": entry})
            if rounded[-1] != entry:
                rounded.append(entry)

        local = corner_points(
            int(radius_dbu), bend_type, npoints, bezier_k, euler_rmax, euler_rmin
        )
        arc = [entry]
        for x, y in local[1:]:
            arc.append(_local_to_global(entry, unit_in, 1 if cross > 0 else -1, x, y))
        arc = _dedupe_points(arc)
        primitives.append({"type": "bend", "points": arc})
        rounded.extend(arc[1:])
        straight_start = exit_point

    if straight_start != points[-1]:
        primitives.append({"type": "straight", "start": straight_start, "end": points[-1]})
        if rounded[-1] != points[-1]:
            rounded.append(points[-1])
    return primitives, _dedupe_points(rounded)


def _point_along(start, end, distance):
    total = _distance(start, end)
    if total <= 0:
        return pya.Point(start.x, start.y)
    ratio = float(distance) / total
    return pya.Point(
        int(round(start.x + (end.x - start.x) * ratio)),
        int(round(start.y + (end.y - start.y) * ratio)),
    )


def _insert_taper(region, start, end, width_start, width_end):
    """沿Manhattan直段插入线性梯形，端面与相邻Path严格重合。"""
    if start == end:
        return
    unit = _unit_step(end - start)
    normal = _left_normal(unit)
    polygon = pya.Polygon([
        pya.Point(int(round(start.x + normal.x * width_start / 2.0)), int(round(start.y + normal.y * width_start / 2.0))),
        pya.Point(int(round(start.x - normal.x * width_start / 2.0)), int(round(start.y - normal.y * width_start / 2.0))),
        pya.Point(int(round(end.x - normal.x * width_end / 2.0)), int(round(end.y - normal.y * width_end / 2.0))),
        pya.Point(int(round(end.x + normal.x * width_end / 2.0)), int(round(end.y + normal.y * width_end / 2.0))),
    ])
    region.insert(polygon)


def _taper_length_for(width_a, width_b, taper_length):
    """只有宽度发生变化时才占用直段内的taper长度。"""
    if taper_length <= 0 or int(width_a) == int(width_b):
        return 0
    return int(taper_length)


def _draw_width_part(region, start, end, width_start, width_end):
    """按起止宽度绘制一个直段片段；等宽时保持Path，异宽时生成taper。"""
    if start == end:
        return
    if int(width_start) == int(width_end):
        region.insert(pya.Path([start, end], int(width_start)))
    else:
        _insert_taper(region, start, end, int(width_start), int(width_end))


def _bend_transition_parts(boundary_width, straight_width, taper_length, transition_length, reverse=False):
    """返回直宽与弯宽之间的恒宽-transition/taper/恒宽-transition片段。

    reverse=False 用于从弯曲切点走向直波导主体；
    reverse=True 用于从直波导主体走向弯曲切点。
    """
    if int(boundary_width) == int(straight_width):
        return []
    parts = [
        {"length": int(transition_length), "w0": int(boundary_width), "w1": int(boundary_width)},
        {"length": int(taper_length), "w0": int(boundary_width), "w1": int(straight_width)},
        {"length": int(transition_length), "w0": int(straight_width), "w1": int(straight_width)},
    ]
    if reverse:
        return [
            {"length": part["length"], "w0": part["w1"], "w1": part["w0"]}
            for part in reversed(parts)
        ]
    return parts


def _terminal_taper_parts(boundary_width, straight_width, taper_length, reverse=False):
    """返回端口宽度与直波导宽度之间的端部taper片段。"""
    if int(boundary_width) == int(straight_width):
        return []
    if reverse:
        return [{"length": int(taper_length), "w0": int(straight_width), "w1": int(boundary_width)}]
    return [{"length": int(taper_length), "w0": int(boundary_width), "w1": int(straight_width)}]


def _scale_part_lengths(parts, scale):
    """直接编辑PCell导致直段不足时，按比例压缩所有局部过渡片段。"""
    scaled = []
    for part in parts:
        item = dict(part)
        item["length"] = max(0, int(math.floor(int(part["length"]) * scale)))
        scaled.append(item)
    return scaled


def _draw_profile(
    region, primitives, straight_width, bend_width, taper_length,
    transition_length=None, start_width=None, end_width=None,
):
    """用同一primitive集合绘制端部、直段、弯曲及其局部taper。

    taper_length 是实际变宽/变窄的taper长度；
    transition_length 是taper两端保持恒定直宽或弯宽的直波导长度。
    """
    start_width = straight_width if start_width is None else start_width
    end_width = straight_width if end_width is None else end_width
    transition_length = taper_length if transition_length is None else transition_length
    for index, primitive in enumerate(primitives):
        if primitive["type"] == "bend":
            # 端点沿公共Bend的10 nm landing重叠，闭合Path在切点量化时的楔形缝隙。
            region.insert(pya.Path(primitive["points"], bend_width, 10, 10))
            continue

        start, end = primitive["start"], primitive["end"]
        has_bend_before = index > 0 and primitives[index - 1]["type"] == "bend"
        has_bend_after = index + 1 < len(primitives) and primitives[index + 1]["type"] == "bend"
        is_single_straight = len(primitives) == 1
        if is_single_straight and int(start_width) == int(end_width):
            region.insert(pya.Path([start, end], start_width))
            continue
        if index == 0 and has_bend_after and int(start_width) == int(bend_width):
            region.insert(pya.Path([start, end], bend_width))
            continue
        if index == len(primitives) - 1 and has_bend_before and int(end_width) == int(bend_width):
            region.insert(pya.Path([start, end], bend_width))
            continue

        if has_bend_before:
            start_parts = _bend_transition_parts(bend_width, straight_width, taper_length, transition_length)
        elif index == 0:
            start_parts = _terminal_taper_parts(start_width, straight_width, taper_length)
        else:
            start_parts = []
        if has_bend_after:
            end_parts = _bend_transition_parts(bend_width, straight_width, taper_length, transition_length, reverse=True)
        elif index == len(primitives) - 1:
            end_parts = _terminal_taper_parts(end_width, straight_width, taper_length, reverse=True)
        else:
            end_parts = []

        start_taper = sum(part["length"] for part in start_parts)
        end_taper = sum(part["length"] for part in end_parts)
        straight_length = _distance(start, end)
        total_taper = start_taper + end_taper
        if total_taper > straight_length and total_taper > 0:
            # 直接编辑PCell参数时可能绕过菜单容量检查；此处按比例裁剪，
            # 保持端面宽度语义并避免两个taper在同一直段内交叠。
            scale = float(straight_length) / float(total_taper)
            start_parts = _scale_part_lengths(start_parts, scale)
            end_parts = _scale_part_lengths(end_parts, scale)
            start_taper = sum(part["length"] for part in start_parts)
            end_taper = sum(part["length"] for part in end_parts)

        cursor = start
        consumed = 0
        for part in start_parts:
            if part["length"] <= 0:
                continue
            next_point = _point_along(start, end, consumed + part["length"])
            _draw_width_part(region, cursor, next_point, part["w0"], part["w1"])
            cursor = next_point
            consumed += part["length"]

        center_end = end
        if end_taper > 0:
            center_end = _point_along(end, start, end_taper)
        if cursor != center_end:
            region.insert(pya.Path([cursor, center_end], straight_width))
        cursor = center_end
        consumed = 0
        for part in end_parts:
            if part["length"] <= 0:
                continue
            next_point = _point_along(center_end, end, consumed + part["length"])
            _draw_width_part(region, cursor, next_point, part["w0"], part["w1"])
            cursor = next_point
            consumed += part["length"]


def draw_composite_waveguide_geometry(
    cell, layout, dpath, straight_width, bend_width, taper_length, radius,
    bend_type, bezier_k=DEFAULT_BEZIER_K,
    euler_rmax=DEFAULT_EULER_RMAX, euler_rmin=DEFAULT_EULER_RMIN,
    start_width=None, end_width=None, transition_length=DEFAULT_TRANSITION_LENGTH,
):
    """绘制复合宽度波导并返回DBU量化后的中心线长度。"""
    dbu = layout.dbu
    raw_path = _dpath_to_integer_path(dpath, dbu)
    raw_points = _dedupe_points(list(raw_path.each_point()))
    if len(raw_points) < 2:
        return 0.0

    bend_type = _normalize_bend_type(bend_type)
    effective_radius = euler_Reff(euler_rmax, euler_rmin) if bend_type == "Euler" else float(radius)
    radius_dbu = max(1, _to_itype(effective_radius, dbu))
    npoints = effective_points_per_90(AUTO_SAMPLE_COUNT, effective_radius, dbu)
    primitives, centerline = build_route_primitives(
        raw_points, radius_dbu, bend_type, npoints, bezier_k, euler_rmax, euler_rmin
    )

    straight_dbu = max(1, _to_itype(straight_width, dbu))
    start_dbu = straight_dbu if start_width is None else max(1, _to_itype(start_width, dbu))
    end_dbu = straight_dbu if end_width is None else max(1, _to_itype(end_width, dbu))
    bend_dbu = max(1, _to_itype(bend_width, dbu))
    taper_dbu = max(0, _to_itype(taper_length, dbu))
    transition_dbu = max(0, _to_itype(transition_length, dbu))
    si_layer = layout.layer(SI_LAYER)
    devrec_layer = layout.layer(DEVREC_LAYER)
    pin_layer = layout.layer(PIN_LAYER)
    text_layer = layout.layer(TEXT_LAYER)

    _store_raw_manhattan_path(
        cell, raw_path, raw_points, straight_dbu, dbu,
        {
            "straight_width_um": straight_dbu * dbu,
            "start_width_um": start_dbu * dbu,
            "end_width_um": end_dbu * dbu,
            "bend_width_um": bend_dbu * dbu,
            "taper_length_um": taper_dbu * dbu,
            "transition_length_um": transition_dbu * dbu,
        },
    )
    si_region = pya.Region()
    _draw_profile(si_region, primitives, straight_dbu, bend_dbu, taper_dbu, transition_dbu, start_dbu, end_dbu)
    cell.shapes(si_layer).insert(si_region.merged())
    clearance = max(0, _to_itype(DEVREC_SIDE_CLEARANCE_UM, dbu))
    devrec_region = pya.Region()
    _draw_profile(
        devrec_region, primitives,
        straight_dbu + 2 * clearance, bend_dbu + 2 * clearance, taper_dbu, transition_dbu,
        start_dbu + 2 * clearance, end_dbu + 2 * clearance,
    )
    cell.shapes(devrec_layer).insert(devrec_region.merged())

    _ensure_tools_path()
    from JNU_MWP_tools.core.make_pin import make_pin
    make_pin(cell, "opt1", centerline[0], start_dbu, pin_layer, _pin_direction(centerline[0], centerline[1]))
    make_pin(cell, "opt2", centerline[-1], end_dbu, pin_layer, _pin_direction(centerline[-1], centerline[-2]))

    length = round(_path_length_um(centerline, dbu), 3)
    text = pya.Text(
        "Composite Waveguide wstart=%.3fum ws=%.3fum wend=%.3fum wb=%.3fum taper=%.3fum transition=%.3fum radius=%.3fum bend=%s length=%.3fum"
        % (
            start_dbu * dbu, straight_width, end_dbu * dbu, bend_width,
            taper_length, transition_length, effective_radius, bend_type, length,
        ),
        pya.Trans(pya.Trans.R0, centerline[0].x, centerline[0].y),
    )
    shape = cell.shapes(text_layer).insert(text)
    shape.text_dsize = max(0.1, float(straight_width) * 0.5)
    return length


class CompositeWaveguide(pya.PCellDeclarationHelper):
    """由Path to Waveguide创建的复合宽度波导。"""

    def __init__(self):
        super(CompositeWaveguide, self).__init__()
        straight_default = default_float(PCELL_NAME, "straight_width", DEFAULT_STRAIGHT_WIDTH)
        self.param("path", self.TypeShape, "Path", default=pya.DPath([pya.DPoint(0, 0), pya.DPoint(100, 0)], DEFAULT_STRAIGHT_WIDTH))
        self.param("straight_width", self.TypeDouble, "Straight waveguide width", unit="um", default=straight_default)
        self.param("start_width", self.TypeDouble, "Start waveguide width", unit="um", default=default_float(PCELL_NAME, "start_width", straight_default))
        self.param("end_width", self.TypeDouble, "End waveguide width", unit="um", default=default_float(PCELL_NAME, "end_width", straight_default))
        self.param("bend_width", self.TypeDouble, "Bend waveguide width", unit="um", default=default_float(PCELL_NAME, "bend_width", DEFAULT_BEND_WIDTH))
        self.param("taper_length", self.TypeDouble, "Taper length", unit="um", default=default_float(PCELL_NAME, "taper_length", DEFAULT_TAPER_LENGTH))
        self.param("transition_length", self.TypeDouble, "Transition length", unit="um", default=default_float(PCELL_NAME, "transition_length", DEFAULT_TRANSITION_LENGTH))
        self.param("radius", self.TypeDouble, "Bend radius", unit="um", default=default_float(PCELL_NAME, "radius", DEFAULT_RADIUS))
        bend_default = _normalize_bend_type(default_choice(PCELL_NAME, "bend_type", "Bezier", ("Circular", "Bezier", "Euler")))
        bend = self.param("bend_type", self.TypeList, "Bend type", default=bend_default)
        for choice in ("Circular", "Bezier", "Euler"):
            bend.add_choice(choice, choice)
        self.bezier_param = self.param("bezier_k", self.TypeDouble, "Bezier shape factor", default=default_float(PCELL_NAME, "bezier_k", DEFAULT_BEZIER_K))
        self.euler_rmax_param = self.param("Euler_Rmax", self.TypeDouble, "Euler max radius (endpoint)", unit="um", default=default_float(PCELL_NAME, "Euler_Rmax", DEFAULT_EULER_RMAX))
        self.euler_rmin_param = self.param("Euler_Rmin", self.TypeDouble, "Euler min radius (midpoint)", unit="um", default=default_float(PCELL_NAME, "Euler_Rmin", DEFAULT_EULER_RMIN))
        # 内部后缀只用于区分参数化显示名称相同、但路径形状不同的 PCell variant。
        self.name_suffix_param = self.param("name_suffix", self.TypeString, "Internal name suffix", default="")
        try:
            self.name_suffix_param.hidden = True
        except Exception:
            pass
        self.bezier_rmax_param = self.param("Bezier_Rmax", self.TypeDouble, "Bezier max radius [uneditable]", unit="um", default=0.0, readonly=True)
        self.bezier_rmin_param = self.param("Bezier_Rmin", self.TypeDouble, "Bezier min radius [uneditable]", unit="um", default=0.0, readonly=True)
        self.euler_reff_param = self.param("Euler_Reff", self.TypeDouble, "Euler effective radius [uneditable]", unit="um", default=0.0, readonly=True)
        try:
            self.bezier_param.hidden = bend_default != "Bezier"
            self.bezier_rmax_param.hidden = bend_default != "Bezier"
            self.bezier_rmin_param.hidden = bend_default != "Bezier"
            self.euler_rmax_param.hidden = bend_default != "Euler"
            self.euler_rmin_param.hidden = bend_default != "Euler"
            self.euler_reff_param.hidden = bend_default != "Euler"
        except Exception:
            pass

    def display_text_impl(self):
        name_suffix = str(getattr(self, "name_suffix", "") or "")
        if self.bend_type == "Euler":
            return "Composite_Waveguide_wstart%.3f_ws%.3f_wend%.3f_wb%.3f_T%.3f_TR%.3f_Rmax%.3f_Rmin%.3f_Euler_L%.3f%s" % (
                self.start_width, self.straight_width, self.end_width, self.bend_width,
                self.taper_length, self.transition_length,
                self.Euler_Rmax, self.Euler_Rmin, getattr(self, "waveguide_length", 0.0), name_suffix,
            )
        suffix = "_B%.3f" % self.bezier_k if self.bend_type == "Bezier" else ""
        return "Composite_Waveguide_wstart%.3f_ws%.3f_wend%.3f_wb%.3f_T%.3f_TR%.3f_R%.3f_%s%s_L%.3f%s" % (
            self.start_width, self.straight_width, self.end_width, self.bend_width,
            self.taper_length, self.transition_length,
            self.radius, self.bend_type, suffix, getattr(self, "waveguide_length", 0.0), name_suffix,
        )

    def coerce_parameters_impl(self):
        self.straight_width = max(0.001, float(self.straight_width))
        self.start_width = max(0.001, float(self.start_width))
        self.end_width = max(0.001, float(self.end_width))
        self.bend_width = max(0.001, float(self.bend_width))
        self.taper_length = max(0.0, float(self.taper_length))
        self.transition_length = max(0.0, float(getattr(self, "transition_length", DEFAULT_TRANSITION_LENGTH)))
        self.radius = max(0.011, float(self.radius))
        self.bend_type = _normalize_bend_type(self.bend_type)
        self.bezier_k = max(0.05, min(0.95, float(self.bezier_k)))
        self.Euler_Rmax = max(0.001, float(self.Euler_Rmax))
        self.Euler_Rmin = max(0.001, min(float(self.Euler_Rmin), self.Euler_Rmax * 0.999))
        if self.bend_type == "Bezier":
            rmax, rmin = bezier_Rmax_Rmin(self.radius, self.bezier_k)
            self.Bezier_Rmax, self.Bezier_Rmin = round(rmax, 3), round(rmin, 3)
        elif self.bend_type == "Euler":
            self.Euler_Reff = round(euler_Reff(self.Euler_Rmax, self.Euler_Rmin), 3)
        save_pcell_defaults(
            self, PCELL_NAME,
            [
                "straight_width", "start_width", "end_width", "bend_width",
                "taper_length", "transition_length", "radius", "bend_type",
                "bezier_k", "Euler_Rmax", "Euler_Rmin",
            ],
        )

    def can_create_from_shape_impl(self):
        return self.shape.is_path()

    def transformation_from_shape_impl(self):
        return pya.Trans()

    def parameters_from_shape_impl(self):
        self.path = self.shape.path.to_dtype(self.layout.dbu)
        self.straight_width = max(0.001, self.shape.path.width * self.layout.dbu)
        self.start_width = self.straight_width
        self.end_width = self.straight_width

    def callback_impl(self, name):
        try:
            value = self.bend_type.value
            value = value() if callable(value) else value
            bend_type = _normalize_bend_type(value)
            is_bezier, is_euler = bend_type == "Bezier", bend_type == "Euler"
            self.radius.visible = not is_euler
            self.bezier_k.visible = is_bezier
            self.Bezier_Rmax.visible = is_bezier
            self.Bezier_Rmin.visible = is_bezier
            self.Euler_Rmax.visible = is_euler
            self.Euler_Rmin.visible = is_euler
            self.Euler_Reff.visible = is_euler
        except Exception:
            pass

    def produce_impl(self):
        self.waveguide_length = draw_composite_waveguide_geometry(
            self.cell, self.layout, self.path, self.straight_width, self.bend_width,
            self.taper_length, self.radius, self.bend_type, self.bezier_k,
            self.Euler_Rmax, self.Euler_Rmin,
            start_width=self.start_width, end_width=self.end_width,
            transition_length=self.transition_length,
        )


__all__ = ["CompositeWaveguide", "draw_composite_waveguide_geometry", "build_route_primitives"]
