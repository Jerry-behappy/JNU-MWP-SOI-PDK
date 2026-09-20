# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-06

# JNULib_BlackBox 器件库的独立加载入口。

import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()

# KLayout 启动宏时不一定会把 pymacros 目录加入 sys.path，这里显式补上。
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    import JNU_MWP_blackbox  # 导入模块时会注册 JNULib_BlackBox。
except Exception as e:
    print("JNULib_BlackBox: register failed:", e)
