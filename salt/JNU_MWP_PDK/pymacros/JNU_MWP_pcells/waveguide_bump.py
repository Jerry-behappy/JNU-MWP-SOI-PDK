# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""独立于 EBeam 安装的四圆弧增量长度波导。

器件由两段严格水平的端口直段和四段等半径圆弧组成。直段长度固定为 20 nm
（DBU 较粗时退回 10 nm），圆弧在连接点处与直段相切，因此端口可以直接与
直波导对接。累计圆弧转角超过 150° 后，第一、四段圆弧会越过端口平面折回，
压住端口直段并让两个端口几乎重合，因此几何统一按 149° 封顶。
"""

import math
import os
import sys

import pya


_PYMACROS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PYMACROS_DIR not in sys.path:
    sys.path.insert(0, _PYMACROS_DIR)

from JNU_MWP_tools.core.devrec import insert_device_devrec
from JNU_MWP_tools.core.make_pin import make_pin


SI_LAYER = pya.LayerInfo(1, 0)
PIN_LAYER = pya.LayerInfo(1, 10)
TEXT_LAYER = pya.LayerInfo(10, 0)

# 端口直段优先保留 20 nm；DBU 较粗时退回 10 nm，但至少保留 2 DBU。
PORT_LAND_UM = 0.02
MIN_PORT_LAND_UM = 0.01
# 圆弧折回端口平面的解析边界为 150°，取 149° 留出量化余量。
FOLD_FREE_MAX_ANGLE_DEG = 149.0
# 圆弧采样上限：弦长 50 nm、单步转角 0.25°，保证弧内折线平滑。
ARC_CHORD_UM = 0.05
ARC_STEP_DEG = 0.25
MAX_ARC_SAMPLES = 20000


def port_land_dbu(dbu):
    """返回端口直段长度（DBU）：优先 20 nm，DBU 较粗时退回 10 nm。"""
    dbu = float(dbu)
    if dbu <= 0:
        raise ValueError("Bump dbu must be positive")
    for target in (PORT_LAND_UM, MIN_PORT_LAND_UM):
        count = int(round(target / dbu))
        if count >= 2:
            return count
    return 2


def effective_max_theta(max_theta):
    """返回实际参与几何计算的圆弧半角上限。"""
    return min(max(1.0, float(max_theta)), FOLD_FREE_MAX_ANGLE_DEG)


def arc_sample_count(radius, theta):
    """按弦长与单步转角双重上限计算单段圆弧的采样点数。"""
    by_chord = int(math.ceil(float(radius) * float(theta) / ARC_CHORD_UM))
    by_angle = int(math.ceil(float(theta) / math.radians(ARC_STEP_DEG)))
    return max(8, min(MAX_ARC_SAMPLES, max(by_chord, by_angle)))


def bump_dimensions(delta_length, radius, max_theta):
    """用四段等半径圆弧的解析增量长度反解转角，返回角度和占用长度。"""
    radius = float(radius)
    delta_length = float(delta_length)
    max_theta = float(max_theta)
    if not all(math.isfinite(value) for value in (radius, delta_length, max_theta)):
        raise ValueError("Bump parameters must be finite")
    if radius <= 0 or delta_length < 0 or not 0 < max_theta < 180:
        raise ValueError("Bump radius, delta length or maximum angle is invalid")

    limit = math.radians(effective_max_theta(max_theta))
    maximum_delta = 4.0 * radius * (limit - math.sin(limit))
    target = min(delta_length, maximum_delta)
    low, high = 0.0, limit
    for _ in range(56):
        theta = (low + high) / 2.0
        if 4.0 * radius * (theta - math.sin(theta)) < target:
            low = theta
        else:
            high = theta
    theta = (low + high) / 2.0
    return theta, 4.0 * radius * math.sin(theta), target


def _bump_trace(delta_length, radius, max_theta, dbu):
    """返回未量化的中心坐标、解析切线及增量长度。"""
    dbu = float(dbu)
    theta, arc_length_x, actual_delta = bump_dimensions(
        delta_length, radius, max_theta)
    land_dbu = port_land_dbu(dbu)
    land = land_dbu * dbu
    if theta < 1e-9:
        length_dbu = max(4 * land_dbu, int(round(2.0 / dbu)))
        return [(0.0, 0.0, 0.0), (length_dbu * dbu, 0.0, 0.0)], actual_delta

    coordinates = [(0.0, 0.0, 0.0), (land, 0.0, 0.0)]
    x, y, heading = land, 0.0, 0.0
    for sign in (1.0, -1.0, -1.0, 1.0):
        initial_x, initial_y, initial_heading = x, y, heading
        count = arc_sample_count(radius, theta)
        for index in range(1, count + 1):
            turn = theta * index / count
            new_heading = initial_heading + sign * turn
            x = initial_x + radius / sign * (math.sin(new_heading) - math.sin(initial_heading))
            y = initial_y - radius / sign * (math.cos(new_heading) - math.cos(initial_heading))
            coordinates.append((x, y, new_heading))
        heading = initial_heading + sign * theta

    end_x = land + arc_length_x
    coordinates[-1] = (end_x, 0.0, 0.0)
    coordinates.append((end_x + land, 0.0, 0.0))
    return coordinates, actual_delta


def bump_centerline(delta_length, radius, max_theta, dbu):
    """按 +、-、-、+ 曲率顺序生成四段圆弧及两个水平端口直段。"""
    coordinates, actual_delta = _bump_trace(delta_length, radius, max_theta, dbu)
    points = []
    for px, py, _ in coordinates:
        point = pya.Point(int(round(px / dbu)), int(round(py / dbu)))
        if not points or point != points[-1]:
            points.append(point)
    if len(points) < 2:
        points = [pya.Point(0, 0), pya.Point(2 * port_land_dbu(dbu), 0)]
    return points, points[-1].x * dbu, actual_delta


def bump_polygon(delta_length, radius, max_theta, width_dbu, dbu):
    """用解析法线生成圆弧边界，保持端口直段和端面不被简化。"""
    coordinates, _ = _bump_trace(delta_length, radius, max_theta, dbu)
    # 两侧使用整数 DBU 偏移，使奇数宽度也保持准确的端口截面宽度。
    lower_half = int(width_dbu) // 2
    upper_half = int(width_dbu) - lower_half
    sides = []
    for offset in (upper_half, -lower_half):
        points = []
        for x, y, heading in coordinates:
            point = pya.Point(
                int(round(x / dbu - offset * math.sin(heading))),
                int(round(y / dbu + offset * math.cos(heading))),
            )
            if not points or point != points[-1]:
                points.append(point)
        sides.append(points)
    # 不调用 Path.polygon()：其宽度相关简化会吞掉短端段，并改变输出端面方向。
    return pya.Polygon(sides[0] + list(reversed(sides[1])))


def centerline_metrics(points, dbu):
    """按量化后的中心线返回物理长度、端口间距和实际增量长度。"""
    dbu = float(dbu)
    physical = sum(math.hypot(b.x - a.x, b.y - a.y) * dbu
                   for a, b in zip(points, points[1:]))
    straight = (points[-1].x - points[0].x) * dbu
    return physical, straight, physical - straight


class WaveguideBump(pya.PCellDeclarationHelper):
    """可直接编辑的 JNU Si 波导长度补偿器。"""

    def __init__(self):
        super(WaveguideBump, self).__init__()
        self.param("delta_length", self.TypeDouble, "Incremental length", unit="um", default=0.2)
        self.param("width", self.TypeDouble, "Waveguide width", unit="um", default=0.5)
        self.param("radius", self.TypeDouble, "Effective bend radius", unit="um", default=20.0)
        self.param("max_theta", self.TypeDouble, "Maximum angle", unit="deg", default=149.0)
        self.param("actual_delta_length", self.TypeDouble, "Actual incremental length [uneditable]",
                   unit="um", default=0.2, readonly=True)
        self.param("device_length", self.TypeDouble, "Device length [uneditable]",
                   unit="um", default=0.0, readonly=True)

    def display_text_impl(self):
        return "Pcell_Waveguide_Bump(dL=%.3f,W=%.3f,R=%.3f)" % (
            self.delta_length, self.width, self.radius)

    def coerce_parameters_impl(self):
        dbu = float(self.layout.dbu) if self.layout is not None else 0.001
        if not all(math.isfinite(float(value)) for value in
                   (self.delta_length, self.width, self.radius, self.max_theta)):
            raise ValueError("Bump parameters must be finite")
        self.delta_length = max(0.0, float(self.delta_length))
        self.width = max(dbu, float(self.width))
        self.radius = max(dbu, float(self.radius))
        # 上限固定为不折回端口平面的角度，界面值与实际几何保持一致。
        self.max_theta = effective_max_theta(
            min(FOLD_FREE_MAX_ANGLE_DEG, max(1.0, float(self.max_theta))))
        points, _, _ = bump_centerline(
            self.delta_length, self.radius, self.max_theta, dbu)
        _, straight, actual_delta = centerline_metrics(points, dbu)
        self.actual_delta_length = round(max(0.0, actual_delta), 3)
        self.device_length = round(straight, 3)

    def produce_impl(self):
        dbu = float(self.layout.dbu)
        points, _, _ = bump_centerline(
            self.delta_length, self.radius, self.max_theta, dbu)
        _, _, actual_delta = centerline_metrics(points, dbu)
        width_dbu = max(1, round(float(self.width) / dbu))
        si_layer = self.layout.layer(SI_LAYER)
        pin_layer = self.layout.layer(PIN_LAYER)
        text_layer = self.layout.layer(TEXT_LAYER)
        self.cell.shapes(si_layer).insert(bump_polygon(
            self.delta_length, self.radius, self.max_theta, width_dbu, dbu))
        make_pin(self.cell, "opt1", points[0], width_dbu, pin_layer, 180)
        make_pin(self.cell, "opt2", points[-1], width_dbu, pin_layer, 0)
        text = pya.Text("dL = %.3f um" % actual_delta,
                        pya.Trans(pya.Trans.R0, (points[0].x + points[-1].x) // 2, 0))
        shape = self.cell.shapes(text_layer).insert(text)
        shape.text_halign = 1
        shape.text_valign = 1
        shape.text_dsize = max(0.15, min(1.0, float(self.width)))
        insert_device_devrec(self.cell, si_layer, pin_layer)


__all__ = [
    "WaveguideBump",
    "bump_dimensions",
    "bump_centerline",
    "bump_polygon",
    "centerline_metrics",
    "port_land_dbu",
    "effective_max_theta",
    "arc_sample_count",
    "PORT_LAND_UM",
    "MIN_PORT_LAND_UM",
    "FOLD_FREE_MAX_ANGLE_DEG",
]
