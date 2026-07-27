# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""验证 JNU PDK 重载不会重复注册库，并刷新本地内部波导声明。"""

from pathlib import Path
import sys

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

import JNULib  # noqa: E402,F401  注册初始公开库。
import JNULib_BlackBox  # noqa: E402,F401  注册初始黑盒库。
from JNU_MWP_tools.actions import reload_pdk  # noqa: E402
from JNU_MWP_tools.actions.path_to_waveguide import _create_waveguide_cell  # noqa: E402


LIBRARY_NAME = "JNULib"
BLACKBOX_LIBRARY_NAME = "JNULib_BlackBox"


def _assert(condition, message):
    if not condition:
        raise RuntimeError(message)


def _library_count():
    count = 0
    for library_id in pya.Library.library_ids():
        library = pya.Library.library_by_id(library_id)
        if library is not None and library.name() == LIBRARY_NAME:
            count += 1
    return count


def _single_params():
    return {
        "width": 0.5,
        "radius": 20.0,
        "bend_type": "Bezier",
        "bezier": 0.35,
        "Euler_Rmax": 30.0,
        "Euler_Rmin": 10.0,
        "npoints": 0,
    }


def _composite_params():
    return {
        "mode": "composite",
        "straight_width": 2.0,
        "bend_width": 0.5,
        "start_width": 2.0,
        "end_width": 2.0,
        "taper_length": 20.0,
        "transition_length": 2.0,
        "radius": 30.0,
        "bend_type": "Bezier",
        "bezier": 0.3,
        "Euler_Rmax": 45.0,
        "Euler_Rmin": 15.0,
        "npoints": 0,
    }


def main():
    layout = pya.Layout()
    layout.dbu = 0.001
    public_cell = layout.create_cell(
        "Straight_Waveguide",
        LIBRARY_NAME,
        {"width": 0.5, "length": 50.0},
    )
    _assert(public_cell is not None, "无法创建热重载前的公开 PCell。")
    _assert(
        pya.Library.library_by_name(BLACKBOX_LIBRARY_NAME) is not None,
        "热重载前未注册黑盒库。",
    )
    public_index = public_cell.cell_index()
    public_bbox = public_cell.bbox()

    dpath = pya.DPath(
        [pya.DPoint(0, 0), pya.DPoint(100, 0), pya.DPoint(100, 100)],
        0.5,
    )
    single = _create_waveguide_cell(layout, dpath, _single_params(), 1)
    composite = _create_waveguide_cell(layout, dpath, _composite_params(), 2)
    _assert(single is not None and composite is not None, "无法创建内部波导 PCell。")
    single_id = layout.pcell_id("Waveguide")
    composite_id = layout.pcell_id("Composite_Waveguide")
    single_bbox = single.bbox()
    composite_bbox = composite.bbox()

    for iteration in range(3):
        result = reload_pdk._reload_runtime([layout])
        _assert(result["internal_refresh_count"] == 2, "内部波导声明刷新数量错误。")
        _assert(_library_count() == 1, "第 %d 次重载后存在重复公开库。" % (iteration + 1))
        library = pya.Library.library_by_name(LIBRARY_NAME)
        _assert(library is not None, "重载后公开库丢失。")
        _assert(
            pya.Library.library_by_name(BLACKBOX_LIBRARY_NAME) is not None,
            "重载后黑盒库丢失。",
        )
        _assert("Straight_Waveguide" in library.layout().pcell_names(), "重载后直波导 PCell 丢失。")
        _assert(layout.pcell_id("Waveguide") == single_id, "Waveguide PCell ID 在重载后变化。")
        _assert(
            layout.pcell_id("Composite_Waveguide") == composite_id,
            "Composite_Waveguide PCell ID 在重载后变化。",
        )
        _assert(layout.cell(single.cell_index()).bbox() == single_bbox, "Waveguide 重算后几何变化。")
        _assert(layout.cell(composite.cell_index()).bbox() == composite_bbox, "Composite_Waveguide 重算后几何变化。")
        _assert(layout.cell(public_index).bbox() == public_bbox, "公开 PCell 重载后几何变化。")

    _assert(
        layout.pcell_declaration("Waveguide").__class__.__module__
        == "JNU_MWP_pcells.waveguide",
        "Waveguide 未替换为重新导入的声明。",
    )
    _assert(
        layout.pcell_declaration("Composite_Waveguide").__class__.__module__
        == "JNU_MWP_pcells.composite_waveguide",
        "Composite_Waveguide 未替换为重新导入的声明。",
    )

    print("OK: JNU white/blackbox libraries and local Waveguide PCells reloaded three times without duplication.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
