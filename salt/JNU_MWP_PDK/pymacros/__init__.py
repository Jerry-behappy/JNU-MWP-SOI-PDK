# $autorun
# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

# 初始化 JNU MWP Python 器件库，并确保 Salt 安装时也能注册 Technology。

print("JNU MWP PDK: load JNULib")

import os

import pya


TECH_NAME = "JNU_MWP_PDK"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
PDK_ROOT = os.path.dirname(SCRIPT_DIR)
TECH_FILE = os.path.join(PDK_ROOT, "JNU_MWP_PDK.lyt")


def _load_jnu_technology():
    """从 Salt 包目录加载 JNU_MWP_PDK.lyt，避免依赖 KLayout/tech 目录副本。"""
    if not os.path.isfile(TECH_FILE):
        print("JNU MWP PDK: technology file not found:", TECH_FILE)
        return

    try:
        if not pya.Technology().has_technology(TECH_NAME):
            tech = pya.Technology().create_technology(TECH_NAME)
        else:
            tech = pya.Technology.technology_by_name(TECH_NAME)
        tech.load(TECH_FILE)
        print("JNU MWP PDK: technology loaded from", TECH_FILE)
    except Exception as error:
        print("JNU MWP PDK: technology load failed:", error)


_load_jnu_technology()

from . import JNULib           # 加载完整器件库 JNULib。
from . import JNULib_BlackBox  # 加载黑盒器件库 JNULib_BlackBox。

# 新建 LayoutView/CellView 时先注册工具内部 PCell，使 GDS 中保存的参数能够在读取时恢复。
from .JNU_MWP_tools.core.internal_waveguide_registry import (
    install_internal_waveguide_registration,
)

install_internal_waveguide_registration()
