# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""JNU_MWP_PDK 顶层初始化脚本。

加载 KLayout technology，并导入 pymacros 注册 JNULib / JNULib_BlackBox。
"""

import os
import sys


print("JNU MWP PDK")

PDK_ROOT = os.path.dirname(os.path.realpath(__file__))
PYMACROS_DIR = os.path.join(PDK_ROOT, "pymacros")
if PYMACROS_DIR not in sys.path:
    sys.path.insert(0, PYMACROS_DIR)
from JNU_MWP_tools.core.pdk_identity import load_jnu_technology

load_jnu_technology(PDK_ROOT)

# 导入 pymacros 子模块，触发 JNULib 和 JNULib_BlackBox 库加载。
from . import pymacros
