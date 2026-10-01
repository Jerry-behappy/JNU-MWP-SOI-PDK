# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""独立于 EBeam 安装的四圆弧增量长度波导。"""

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
PORT_LAND_UM = 0.02


def bump_dimensions(delta_length, radius, max_theta):
    """用四段等半径圆弧的解析增量长度反解转角，返回角度和占用长度。"""
    radius = float(radius)
    delta_length = float(delta_length)
    max_theta = float(max_theta)
    if not all(math.isfinite(value) for value in (radius, delta_length, max_theta)):
        raise ValueError("Bump parameters must be finite")
    if radius <= 0 or delta_length < 0 or not 0 < max_theta < 180:
        raise ValueError("Bump radius, delta length or maximum angle is invalid")

    limit = math.radians(max_theta)
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


def bump_centerline(delta_length, radius, max_theta, dbu):
    """按 +、-、-、+ 曲率顺序生成四段圆弧及两个水平端口落脚段。"""
    theta, arc_length_x, actual_delta = bump_dimensions(delta_length, radius, max_theta)
    land = max(PORT_LAND_UM, 2.0 * dbu)
    if theta < 1e-9:
        length = max(2.0, 4.0 * land)
        return [pya.Point(0, 0), pya.Point(round(length / dbu), 0)], length, actual_delta

    coordinates = [(0.0, 0.0), (land, 0.0)]
    x, y, heading = land, 0.0, 0.0
    for sign in (1.0, -1.0, -1.0, 1.0):
        initial_x, initial_y, initial_heading = x, y, heading
        count = max(8, min(4096, int(math.ceil(radius * theta / 0.05))))
        for index in range(1, count + 1):
            turn = theta * index / count
            new_heading = initial_heading + sign * turn
            x = initial_x + radius / sign * (math.sin(new_heading) - math.sin(initial_heading))
            y = initial_y - radius / sign * (math.cos(new_heading) - math.cos(initial_heading))
            coordinates.append((x, y))
        heading = initial_heading + sign * theta

    end_x = land + arc_length_x
    coordinates[-1] = (end_x, 0.0)
    coordinates.append((end_x + land, 0.0))
    points = []
    for px, py in coordinates:
        point = pya.Point(round(px / dbu), round(py / dbu))
        if not points or point != points[-1]:
            points.append(point)
    return points, end_x + land, actual_delta


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
        self.max_theta = min(179.0, max(1.0, float(self.max_theta)))
        _, device_length, actual_delta = bump_dimensions(
            self.delta_length, self.radius, self.max_theta)
        self.actual_delta_length = round(actual_delta, 3)
        self.device_length = round(
            max(2.0, 4 * PORT_LAND_UM) if actual_delta == 0 else
            device_length + 2 * PORT_LAND_UM, 3)

    def produce_impl(self):
        dbu = float(self.layout.dbu)
        points, _, actual_delta = bump_centerline(
            self.delta_length, self.radius, self.max_theta, dbu)
        width_dbu = max(1, round(float(self.width) / dbu))
        si_layer = self.layout.layer(SI_LAYER)
        pin_layer = self.layout.layer(PIN_LAYER)
        text_layer = self.layout.layer(TEXT_LAYER)
        self.cell.shapes(si_layer).insert(pya.Path(points, width_dbu).polygon())
        make_pin(self.cell, "opt1", points[0], width_dbu, pin_layer, 180)
        make_pin(self.cell, "opt2", points[-1], width_dbu, pin_layer, 0)
        text = pya.Text("dL = %.3f um" % actual_delta,
                        pya.Trans(pya.Trans.R0, (points[0].x + points[-1].x) // 2, 0))
        shape = self.cell.shapes(text_layer).insert(text)
        shape.text_halign = 1
        shape.text_valign = 1
        shape.text_dsize = max(0.15, min(1.0, float(self.width)))
        insert_device_devrec(self.cell, si_layer, pin_layer)


__all__ = ["WaveguideBump", "bump_dimensions", "bump_centerline"]
