# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-06

"""JNU_MWP_PDK 顶层初始化脚本。

加载 KLayout technology，并导入 pymacros 注册 JNULib / JNULib_BlackBox。
"""

import os

import pya


print("JNU MWP PDK")

TECH_NAME = "JNU_MWP_PDK"
TECH_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), "JNU_MWP_PDK.lyt")

if not pya.Technology().has_technology(TECH_NAME):
    tech = pya.Technology().create_technology(TECH_NAME)
else:
    tech = pya.Technology.technology_by_name(TECH_NAME)

tech.load(TECH_FILE)

# 导入 pymacros 子模块，触发 JNULib 和 JNULib_BlackBox 库加载。
from . import pymacros
