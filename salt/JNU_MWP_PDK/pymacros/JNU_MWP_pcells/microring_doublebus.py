# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""微环双总线谐振器 PCell。"""

import math
import os
import sys

import pya

_pymacros_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _pymacros_dir not in sys.path:
    sys.path.insert(0, _pymacros_dir)
from JNU_MWP_tools.core.make_pin import make_pin
from JNU_MWP_tools.core.devrec import insert_device_devrec

try:
    from .pcell_defaults import (
        default_choice,
        default_float,
        default_int,
        default_layer_info,
        save_pcell_defaults,
    )
except ImportError:
    PCELL_DIR = os.path.dirname(os.path.abspath(__file__))
    if PCELL_DIR not in sys.path:
        sys.path.insert(0, PCELL_DIR)
    from pcell_defaults import (
        default_choice,
        default_float,
        default_int,
        default_layer_info,
        save_pcell_defaults,
    )


PCELL_NAME = "Microring_DoubleBus"


class MicroringDoubleBus(pya.PCellDeclarationHelper):
    """带 through/drop 双总线的微环谐振器 PCell。"""

    DROP_RIGHT_VERTICAL = "right_vertical"
    DROP_TOP_PARALLEL = "top_parallel"

    def __init__(self):
        super(MicroringDoubleBus, self).__init__()

        self.param(
            "wg_layer",
            self.TypeLayer,
            "Waveguide layer",
            default=default_layer_info(PCELL_NAME, "wg_layer", pya.LayerInfo(1, 0)),
        )
        self.param(
            "pin_layer",
            self.TypeLayer,
            "Pin recognition layer",
            default=default_layer_info(PCELL_NAME, "pin_layer", pya.LayerInfo(1, 10)),
        )
        self.param(
            "radius",
            self.TypeDouble,
            "Ring center radius",
            unit="um",
            default=default_float(PCELL_NAME, "radius", 50.0),
        )
        self.param(
            "gap",
            self.TypeDouble,
            "Coupling gap",
            unit="um",
            default=default_float(PCELL_NAME, "gap", 0.2),
        )
        self.param(
            "wg_width",
            self.TypeDouble,
            "Waveguide width",
            unit="um",
            default=default_float(PCELL_NAME, "wg_width", 0.5),
        )
        self.param(
            "bus_length",
            self.TypeDouble,
            "Bus waveguide length",
            unit="um",
            default=default_float(PCELL_NAME, "bus_length", 100.0),
        )
        self.param(
            "ring_points",
            self.TypeInt,
            "Ring points (0=auto)",
            default=default_int(PCELL_NAME, "ring_points", 0),
        )
        self.param(
            "drop_bus_position",
            self.TypeString,
            "Drop bus position",
            default=default_choice(
                PCELL_NAME,
                "drop_bus_position",
                self.DROP_RIGHT_VERTICAL,
                (self.DROP_RIGHT_VERTICAL, self.DROP_TOP_PARALLEL),
            ),
            choices=[
                ["Right vertical", self.DROP_RIGHT_VERTICAL],
                ["Top horizontal", self.DROP_TOP_PARALLEL],
            ],
        )

        # 只读派生参数统一放在全部可编辑参数之后。
        self.param(
            "effective_ring_points",
            self.TypeInt,
            "Effective ring points [uneditable]",
            default=0,
            readonly=True,
        )

    def display_text_impl(self):
        """显示关键几何参数。"""

        effective_points = self._effective_ring_points(float(self.radius))
        ring_points_text = (
            "auto(%d)" % effective_points
            if int(self.ring_points) == 0
            else str(effective_points)
        )
        return "Microring_DoubleBus(R=%.3f,g=%.3f,w=%.3f,L=%.3f,P=%s,%s)" % (
            self.radius,
            self.gap,
            self.wg_width,
            self.bus_length,
            ring_points_text,
            self.drop_bus_position,
        )

    def coerce_parameters_impl(self):
        """限制参数范围，并保存下次新建默认值。"""

        min_width = max(self.layout.dbu, 0.001) if self.layout is not None else 0.001
        self.wg_width = max(float(self.wg_width), min_width)
        self.radius = max(float(self.radius), self.wg_width)
        self.gap = max(float(self.gap), 0.0)
        self.bus_length = max(float(self.bus_length), 0.0)
        self.ring_points = max(int(self.ring_points), 0)
        self.effective_ring_points = self._effective_ring_points(self.radius)

        if self.drop_bus_position not in (self.DROP_RIGHT_VERTICAL, self.DROP_TOP_PARALLEL):
            self.drop_bus_position = self.DROP_RIGHT_VERTICAL

        save_pcell_defaults(
            self,
            PCELL_NAME,
            [
                "wg_layer",
                "pin_layer",
                "radius",
                "gap",
                "wg_width",
                "bus_length",
                "ring_points",
                "drop_bus_position",
            ],
        )

    def produce_impl(self):
        """绘制微环、through/drop 总线和 PinRec 端口。"""

        dbu = self.layout.dbu
        shapes = self.cell.shapes(self.wg_layer_layer)

        radius = float(self.radius)
        gap = float(self.gap)
        wg_width = float(self.wg_width)
        bus_length = float(self.bus_length)

        ring_region = self._ring_region(radius, wg_width, dbu)
        for poly in ring_region.each():
            shapes.insert(poly)

        bus_offset = radius + gap + wg_width
        bus_half_length = 0.5 * bus_length

        through_x_min = -bus_half_length
        through_x_max = bus_half_length
        through_y = -bus_offset
        shapes.insert(
            self._box_um(
                through_x_min,
                through_y - 0.5 * wg_width,
                through_x_max,
                through_y + 0.5 * wg_width,
                dbu,
            )
        )
        through_ports = [
            ("opt1", [through_x_min, through_y], 180),
            ("opt2", [through_x_max, through_y], 0),
        ]

        if self.drop_bus_position == self.DROP_TOP_PARALLEL:
            drop_ports = self._insert_top_parallel_drop(
                shapes,
                bus_offset,
                bus_half_length,
                wg_width,
                dbu,
            )
        else:
            drop_ports = self._insert_right_vertical_drop(
                shapes,
                bus_offset,
                bus_length,
                through_y,
                wg_width,
                dbu,
            )

        for name, center, direction in through_ports + drop_ports:
            make_pin(self.cell, name, center, wg_width, self.pin_layer_layer, direction)

        insert_device_devrec(
            self.cell,
            self.wg_layer_layer,
            self.pin_layer_layer,
        )

    def _insert_right_vertical_drop(self, shapes, bus_offset, bus_length, through_y, wg_width, dbu):
        """右侧垂直 drop 总线。"""

        bus_half_length = 0.5 * bus_length
        drop_x = bus_offset
        drop_y_min = -bus_half_length
        drop_y_max = bus_half_length

        shapes.insert(
            self._box_um(
                drop_x - 0.5 * wg_width,
                drop_y_min,
                drop_x + 0.5 * wg_width,
                drop_y_max,
                dbu,
            )
        )

        return [
            ("opt3", [drop_x, drop_y_min], 270),
            ("opt4", [drop_x, drop_y_max], 90),
        ]

    def _insert_top_parallel_drop(self, shapes, bus_offset, bus_half_length, wg_width, dbu):
        """上侧水平 drop 总线。"""

        drop_y = bus_offset
        shapes.insert(
            self._box_um(
                -bus_half_length,
                drop_y - 0.5 * wg_width,
                bus_half_length,
                drop_y + 0.5 * wg_width,
                dbu,
            )
        )

        return [
            ("opt3", [-bus_half_length, drop_y], 180),
            ("opt4", [bus_half_length, drop_y], 0),
        ]

    def _ring_region(self, radius_um, width_um, dbu):
        """用外圆减内圆得到环形波导区域。"""

        outer_radius = radius_um + 0.5 * width_um
        inner_radius = radius_um - 0.5 * width_um
        npoints = self._effective_ring_points(radius_um)

        outer = pya.Polygon(self._circle_points(outer_radius, dbu, npoints))
        inner = pya.Polygon(self._circle_points(inner_radius, dbu, npoints))
        return pya.Region(outer) - pya.Region(inner)

    def _circle_points(self, radius_um, dbu, npoints=None):
        """生成圆形多边形采样点。"""

        if npoints is None:
            npoints = self._effective_ring_points(radius_um)

        points = []
        for index in range(npoints):
            angle = 2.0 * math.pi * index / npoints
            points.append(
                pya.Point(
                    int(round(radius_um * math.cos(angle) / dbu)),
                    int(round(radius_um * math.sin(angle) / dbu)),
                )
            )
        return points

    def _effective_ring_points(self, radius_um):
        """返回实际使用的圆环采样点数。"""

        if self.ring_points > 0:
            return max(16, int(self.ring_points))
        return self._auto_ring_points(radius_um)

    @staticmethod
    def _auto_ring_points(radius_um):
        """按约 0.1 um 弧长间隔自动估算圆环点数。"""

        return max(96, int(math.ceil(2.0 * math.pi * radius_um / 0.1)))

    @staticmethod
    def _box_um(x1_um, y1_um, x2_um, y2_um, dbu):
        """把 um 坐标转换为 KLayout 数据库单位矩形。"""

        x1 = int(round(min(x1_um, x2_um) / dbu))
        y1 = int(round(min(y1_um, y2_um) / dbu))
        x2 = int(round(max(x1_um, x2_um) / dbu))
        y2 = int(round(max(y1_um, y2_um) / dbu))
        return pya.Box(x1, y1, x2, y2)


__all__ = ["MicroringDoubleBus"]
