# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""线性 Taper PCell。

Si 实体由 Port 1 直段、线性渐变段和 Port 2 直段连续组成，并生成两端 PinRec、器件边界和 Text。
opt1 位于 (0,0)，方向 180°，宽度 width1。
opt2 位于三段总长度的末端，方向 0°，宽度 width2。
Pin 长度 20 nm。
"""

import os
import sys
import math

import pya

try:
    from .pcell_defaults import default_float, default_choice, default_bool
    from .pcell_defaults import apply_saved_defaults_to_states, save_pcell_defaults
except ImportError:
    PCELL_DIR = os.path.dirname(os.path.abspath(__file__))
    if PCELL_DIR not in sys.path:
        sys.path.insert(0, PCELL_DIR)
    from pcell_defaults import default_float, default_choice, default_bool
    from pcell_defaults import apply_saved_defaults_to_states, save_pcell_defaults


PCELL_NAME = "Taper"
TEXT_LAYER = pya.LayerInfo(10, 0)
PIN_LENGTH_UM = 0.02  # 端口总长, 单位 um

EDITABLE_PARAMETER_NAMES = (
    "width1",
    "width2",
    "length",
    "port1_extension_length",
    "port2_extension_length",
    "wg_layer",
    "pin_layer",
    "devrec_layer",
)
BUILTIN_DEFAULTS = {
    "width1": 0.5,
    "width2": 3.0,
    "length": 50.0,
    "port1_extension_length": 0.0,
    "port2_extension_length": 0.0,
    "wg_layer": "1/0",
    "pin_layer": "1/10",
}

WG_LAYER_CHOICES = (("1/0", "Si - waveguide layer (1/0)"), ("1/99", "Waveguide - raw path (1/99)"))
PIN_LAYER_CHOICES = (("1/10", "PinRec - optical pin layer (1/10)"),)
DEVREC_CHOICES = (("68/0", "DevRec (68/0)"),)


def _choice_values(choices):
    return tuple(v for v, _ in choices)


def _layer_info_from_choice(value, fallback):
    try:
        text = str(value)
        if "/" in text:
            layer, datatype = text.split("/", 1)
            return pya.LayerInfo(int(layer), int(datatype))
    except Exception:
        pass
    return fallback


class Taper(pya.PCellDeclarationHelper):
    """线性 Taper PCell。"""

    def __init__(self):
        super(Taper, self).__init__()

        wg_layer_default = default_choice(PCELL_NAME, "wg_layer", "1/0", _choice_values(WG_LAYER_CHOICES))
        pin_layer_default = default_choice(PCELL_NAME, "pin_layer", "1/10", _choice_values(PIN_LAYER_CHOICES))

        wg_param = self.param("wg_layer", self.TypeList, "Waveguide layer", default=wg_layer_default)
        for v, l in WG_LAYER_CHOICES:
            wg_param.add_choice(l, v)

        pin_param = self.param("pin_layer", self.TypeList, "Pin layer", default=pin_layer_default)
        for v, l in PIN_LAYER_CHOICES:
            pin_param.add_choice(l, v)

        devrec_param = self.param("devrec_layer", self.TypeList, "DevRec layer", default="68/0")
        for v, l in DEVREC_CHOICES:
            devrec_param.add_choice(l, v)

        self.param("width1", self.TypeDouble, "Width at port 1", unit="um",
                   default=default_float(PCELL_NAME, "width1", 0.5))
        self.param("width2", self.TypeDouble, "Width at port 2", unit="um",
                   default=default_float(PCELL_NAME, "width2", 3.0))
        self.param("length", self.TypeDouble, "Taper length", unit="um",
                   default=default_float(PCELL_NAME, "length", 50.0))
        self.param(
            "port1_extension_length",
            self.TypeDouble,
            "Port 1 straight extension length",
            unit="um",
            default=default_float(PCELL_NAME, "port1_extension_length", 0.0),
        )
        self.param(
            "port2_extension_length",
            self.TypeDouble,
            "Port 2 straight extension length",
            unit="um",
            default=default_float(PCELL_NAME, "port2_extension_length", 0.0),
        )

    def display_text_impl(self):
        return "Taper(w1=%.3f,w2=%.3f,L1=%.3f,Lt=%.3f,L2=%.3f)" % (
            self.width1,
            self.width2,
            self.port1_extension_length,
            self.length,
            self.port2_extension_length,
        )

    def coerce_parameters_impl(self):
        self.width1 = max(float(self.width1), 0.001)
        self.width2 = max(float(self.width2), 0.001)
        self.length = max(float(self.length), 0.1)
        self.port1_extension_length = max(
            float(self.port1_extension_length),
            0.0,
        )
        self.port2_extension_length = max(
            float(self.port2_extension_length),
            0.0,
        )
        save_pcell_defaults(self, PCELL_NAME, EDITABLE_PARAMETER_NAMES)

    def produce_impl(self):
        dbu = self.layout.dbu

        wg_layer = self.layout.layer(_layer_info_from_choice(self.wg_layer, pya.LayerInfo(1, 0)))
        pin_layer = self.layout.layer(_layer_info_from_choice(self.pin_layer, pya.LayerInfo(1, 10)))
        devrec_layer = self.layout.layer(_layer_info_from_choice(self.devrec_layer, pya.LayerInfo(68, 0)))
        text_layer = self.layout.layer(TEXT_LAYER)

        w1_dbu = int(round(float(self.width1) / dbu))
        w2_dbu = int(round(float(self.width2) / dbu))
        port1_length_dbu = max(
            0,
            int(round(float(self.port1_extension_length) / dbu)),
        )
        taper_length_dbu = max(1, int(round(float(self.length) / dbu)))
        port2_length_dbu = max(
            0,
            int(round(float(self.port2_extension_length) / dbu)),
        )
        taper_end_dbu = port1_length_dbu + taper_length_dbu
        total_length_dbu = taper_end_dbu + port2_length_dbu

        # 一条连续边界同时描述两端恒宽直段和中间线性渐变段，避免拼接缝隙。
        half_w1 = max(1, w1_dbu // 2)
        half_w2 = max(1, w2_dbu // 2)
        polygon_points = [
            pya.Point(0, half_w1),
            pya.Point(port1_length_dbu, half_w1),
            pya.Point(taper_end_dbu, half_w2),
            pya.Point(total_length_dbu, half_w2),
            pya.Point(total_length_dbu, -half_w2),
            pya.Point(taper_end_dbu, -half_w2),
            pya.Point(port1_length_dbu, -half_w1),
            pya.Point(0, -half_w1),
        ]
        clean_points = []
        for point in polygon_points:
            if not clean_points or clean_points[-1] != point:
                clean_points.append(point)
        poly = pya.Polygon(clean_points)
        self.cell.shapes(wg_layer).insert(poly)

        # DevRec 覆盖完整三段长度，并使用两端波导中的最大半宽。
        max_half_width = max(half_w1, half_w2)
        self.cell.shapes(devrec_layer).insert(
            pya.Box(0, -max_half_width, total_length_dbu, max_half_width)
        )

        # Text
        tx = "Taper w1=%.3f w2=%.3f L1=%.3f Lt=%.3f L2=%.3f L=%.3f" % (
            self.width1,
            self.width2,
            port1_length_dbu * dbu,
            taper_length_dbu * dbu,
            port2_length_dbu * dbu,
            total_length_dbu * dbu,
        )
        cx = total_length_dbu // 2
        cy = 0
        text_obj = pya.Text(tx, pya.Trans(pya.Trans.R0, cx, cy))
        shape = self.cell.shapes(text_layer).insert(text_obj)
        shape.text_halign = 1
        shape.text_valign = 1
        shape.text_dsize = max(0.05, total_length_dbu * dbu * 0.02)

        # 端口随两端直段移动到完整器件的外侧端面。
        self._make_pin("opt1", 0.0, 0.0, self.width1, pin_layer, 180)
        self._make_pin(
            "opt2",
            total_length_dbu * dbu,
            0.0,
            self.width2,
            pin_layer,
            0,
        )

    def _make_pin(self, name, cx_um, cy_um, width_um, layer, direction):
        dbu = self.layout.dbu
        x = int(round(cx_um / dbu))
        y = int(round(cy_um / dbu))
        w = max(1, int(round(float(width_um) / dbu)))
        hl = max(1, int(round(0.5 * PIN_LENGTH_UM / dbu)))

        text = pya.Text(name, pya.Trans(pya.Trans.R0, x, y))
        shape = self.cell.shapes(layer).insert(text)
        shape.text_dsize = max(float(width_um) * 0.5, dbu)
        shape.text_valign = 1

        direction %= 360
        if direction == 0:
            p1, p2 = pya.Point(x - hl, y), pya.Point(x + hl, y)
            shape.text_halign = 2
        elif direction == 90:
            p1, p2 = pya.Point(x, y - hl), pya.Point(x, y + hl)
            shape.text_halign = 2
            shape.text_rot = 1
        elif direction == 180:
            p1, p2 = pya.Point(x + hl, y), pya.Point(x - hl, y)
            shape.text_halign = 3
        else:
            p1, p2 = pya.Point(x, y + hl), pya.Point(x, y - hl)
            shape.text_halign = 3
            shape.text_rot = 1

        self.cell.shapes(layer).insert(pya.Path([p1, p2], w))

    def callback(self, layout, name, states):
        return super(Taper, self).callback(layout, name, states)

    def callback_impl(self, name):
        pass


def taper_polygon_between(cell, layer, pt1, pt2, w1, w2, nx, ny):
    """共享 taper polygon：从 pt1(w1) 到 pt2(w2)，法向 (nx, ny)。"""
    cell.shapes(layer).insert(pya.Polygon([
        pya.Point(int(pt1.x + nx * w1 // 2), int(pt1.y + ny * w1 // 2)),
        pya.Point(int(pt1.x - nx * w1 // 2), int(pt1.y - ny * w1 // 2)),
        pya.Point(int(pt2.x - nx * w2 // 2), int(pt2.y - ny * w2 // 2)),
        pya.Point(int(pt2.x + nx * w2 // 2), int(pt2.y + ny * w2 // 2))]))

__all__ = ["Taper", "taper_polygon_between"]
