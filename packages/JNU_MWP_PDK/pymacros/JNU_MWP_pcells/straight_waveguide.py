# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""两端口直波导 PCell。"""

import os
import sys

import pya


_PYMACROS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PYMACROS_DIR not in sys.path:
    sys.path.insert(0, _PYMACROS_DIR)

from JNU_MWP_tools.core.devrec import insert_device_devrec
from JNU_MWP_tools.core.make_pin import make_pin

try:
    from .pcell_defaults import default_float, default_layer_info, save_pcell_defaults
except ImportError:
    _PCELL_DIR = os.path.dirname(os.path.abspath(__file__))
    if _PCELL_DIR not in sys.path:
        sys.path.insert(0, _PCELL_DIR)
    from pcell_defaults import default_float, default_layer_info, save_pcell_defaults


PCELL_NAME = "Straight_Waveguide"
TEXT_LAYER = pya.LayerInfo(10, 0)
EDITABLE_PARAMETER_NAMES = ("wg_layer", "pin_layer", "width", "length")


class StraightWaveguide(pya.PCellDeclarationHelper):
    """沿 +X 方向生成固定宽度的直波导。"""

    def __init__(self):
        super(StraightWaveguide, self).__init__()

        self.param(
            "wg_layer",
            self.TypeLayer,
            "Waveguide layer",
            default=default_layer_info(
                PCELL_NAME,
                "wg_layer",
                pya.LayerInfo(1, 0),
            ),
        )
        self.param(
            "pin_layer",
            self.TypeLayer,
            "Pin recognition layer",
            default=default_layer_info(
                PCELL_NAME,
                "pin_layer",
                pya.LayerInfo(1, 10),
            ),
        )
        self.param(
            "width",
            self.TypeDouble,
            "Waveguide width",
            unit="um",
            default=default_float(PCELL_NAME, "width", 0.5),
        )
        self.param(
            "length",
            self.TypeDouble,
            "Waveguide length",
            unit="um",
            default=default_float(PCELL_NAME, "length", 50.0),
        )

    def display_text_impl(self):
        """在 Instance 列表中显示量化前的输入参数。"""

        return "Straight_Waveguide(W=%.3f,L=%.3f)" % (
            float(self.width),
            float(self.length),
        )

    def coerce_parameters_impl(self):
        """保证宽度和长度至少为一个数据库单位。"""

        dbu = float(self.layout.dbu) if self.layout is not None else 0.001
        self.width = max(dbu, float(self.width))
        self.length = max(dbu, float(self.length))
        save_pcell_defaults(self, PCELL_NAME, EDITABLE_PARAMETER_NAMES)

    def produce_impl(self):
        """生成 Si、PinRec、Text 和固定 68/0 DevRec。"""

        dbu = float(self.layout.dbu)
        width_dbu = max(1, int(round(float(self.width) / dbu)))
        length_dbu = max(1, int(round(float(self.length) / dbu)))
        bottom = -(width_dbu // 2)
        top = bottom + width_dbu

        waveguide_layer = self.layout.layer(self.wg_layer)
        pin_layer = self.layout.layer(self.pin_layer)
        text_layer = self.layout.layer(TEXT_LAYER)

        self.cell.shapes(waveguide_layer).insert(
            pya.Box(0, bottom, length_dbu, top)
        )

        make_pin(
            self.cell,
            "opt1",
            [0, 0],
            width_dbu,
            pin_layer,
            180,
        )
        make_pin(
            self.cell,
            "opt2",
            [length_dbu, 0],
            width_dbu,
            pin_layer,
            0,
        )

        label = "Straight_Waveguide W=%.3f L=%.3f" % (
            width_dbu * dbu,
            length_dbu * dbu,
        )
        text = pya.Text(
            label,
            pya.Trans(pya.Trans.R0, length_dbu // 2, 0),
        )
        text_shape = self.cell.shapes(text_layer).insert(text)
        text_shape.text_halign = 1
        text_shape.text_valign = 1
        text_shape.text_dsize = max(0.05, length_dbu * dbu * 0.02)

        # 两个端口所在的左右边保持与 Si 端面齐平，仅上下增加 1 um 净空。
        insert_device_devrec(
            self.cell,
            waveguide_layer,
            pin_layer,
        )


__all__ = ["StraightWaveguide"]
