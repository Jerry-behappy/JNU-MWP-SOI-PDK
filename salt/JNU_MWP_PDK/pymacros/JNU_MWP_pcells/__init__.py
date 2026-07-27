# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

# JNU_MWP_pcells PCell 子模块。
# 包含微环、双臂螺旋、回形针螺旋、普通波导、S 弯波导和 90° 弯曲等参数化器件定义。

import os
import sys

# 公共工具使用 JNU_MWP_tools 子包，确保 pymacros 父目录可被导入。
_PCELLS_DIR = os.path.dirname(os.path.abspath(__file__))
_PYMACROS_DIR = os.path.dirname(_PCELLS_DIR)
if _PYMACROS_DIR not in sys.path:
    sys.path.insert(0, _PYMACROS_DIR)

from .bend_90deg import Bend90deg
from .microring_doublebus import MicroringDoubleBus
from .paperclip_spiral import PaperclipSpiral
from .paperclip_spiral_composite import PaperclipSpiralWithCompositeWaveguide
from .s_bend_waveguide import SBendWaveguide
from .straight_waveguide import StraightWaveguide
from .Archimedean_spiral import ArchimedeanSpiral
from .taper import Taper
from .waveguide import Waveguide
from .composite_waveguide import CompositeWaveguide

__all__ = [
    "Bend90deg", "MicroringDoubleBus", "PaperclipSpiral",
    "PaperclipSpiralWithCompositeWaveguide", "ArchimedeanSpiral", "Taper", "Waveguide",
    "SBendWaveguide", "StraightWaveguide", "CompositeWaveguide",
]
