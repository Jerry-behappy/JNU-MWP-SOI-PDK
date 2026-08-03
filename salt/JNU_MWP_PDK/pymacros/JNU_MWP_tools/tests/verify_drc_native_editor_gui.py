# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-08

"""在真实 KLayout GUI 进程中验证 JNU DRC 会打开原生 Macro Development。"""

from pathlib import Path
import sys


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

from JNU_MWP_tools.actions.drc import open_drc_macro_editor  # noqa: E402


if not open_drc_macro_editor():
    raise RuntimeError("未能打开 KLayout 原生 Macro Development。")

print("OK: KLayout Macro Development opened JNU_MWP_DRC.lydrc")
