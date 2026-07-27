# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""验证 JNU 器件库的注册身份不随发行版本变化。"""

from pathlib import Path
import sys

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

import JNULib  # noqa: E402,F401
import JNULib_BlackBox  # noqa: E402,F401


WHITE_LIBRARY = "JNULib"
BLACKBOX_LIBRARY = "JNULib_BlackBox"
LEGACY_LIBRARY_NAMES = (
    "JNULib_v1.0",
    "JNULib_v1.1",
    "JNULib_BlackBox_v1.0",
    "JNULib_BlackBox_v1.1",
)


def _assert(condition, message):
    if not condition:
        raise RuntimeError(message)


def _library_count(name):
    return sum(
        1
        for library_id in pya.Library.library_ids()
        if pya.Library.library_by_id(library_id) is not None
        and pya.Library.library_by_id(library_id).name() == name
    )


def main():
    white = pya.Library.library_by_name(WHITE_LIBRARY)
    blackbox = pya.Library.library_by_name(BLACKBOX_LIBRARY)
    _assert(white is not None, "未注册稳定白盒库 JNULib。")
    _assert(blackbox is not None, "未注册稳定黑盒库 JNULib_BlackBox。")
    _assert(_library_count(WHITE_LIBRARY) == 1, "白盒库出现重复注册。")
    _assert(_library_count(BLACKBOX_LIBRARY) == 1, "黑盒库出现重复注册。")
    _assert("v1." not in white.name(), "白盒库名仍带发行版本号。")
    _assert("v1." not in blackbox.name(), "黑盒库名仍带发行版本号。")
    _assert(
        str(white.description).startswith("v1.1,"),
        "白盒库未在说明栏显示当前发行版本。",
    )
    _assert(
        str(blackbox.description).startswith("v1.1,"),
        "黑盒库未在说明栏显示当前发行版本。",
    )

    for legacy_name in LEGACY_LIBRARY_NAMES:
        _assert(
            pya.Library.library_by_name(legacy_name) is None,
            "旧版库名仍注册在当前会话中: %s" % legacy_name,
        )

    layout = pya.Layout()
    cell = layout.create_cell(
        "Straight_Waveguide", WHITE_LIBRARY, {"width": 0.5, "length": 50.0}
    )
    _assert(cell is not None, "稳定库名无法创建公开 PCell。")
    _assert(not cell.bbox().empty(), "公开 PCell 未生成几何。")
    print("OK: JNU library names are stable and descriptions display the release version.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
