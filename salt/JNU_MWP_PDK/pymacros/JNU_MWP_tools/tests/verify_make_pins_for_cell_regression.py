# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""验证 Make Pins for Cell 的 DevRec 外扩与端口边界规则。"""

from pathlib import Path
import sys

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

from JNU_MWP_tools.actions.make_pins_for_cell import (
    DEVREC_NON_PORT_OFFSET_UM,
    make_pins_for_cell_impl,
)
from JNU_MWP_tools.core.common import DEVREC_LAYER, M1_LAYER, PIN_LAYER, SI_LAYER


def _assert(condition, message):
    if not condition:
        raise RuntimeError(message)


def _new_cell(name):
    layout = pya.Layout()
    layout.dbu = 0.001
    return layout, layout.create_cell(name)


def _box(left, bottom, right, top):
    return pya.Box(left, bottom, right, top)


def _devrec_bbox(cell):
    layout = cell.layout()
    return cell.bbox(layout.layer(DEVREC_LAYER))


def _pin_paths(cell):
    layout = cell.layout()
    return [
        shape.path
        for shape in cell.shapes(layout.layer(PIN_LAYER)).each()
        if shape.is_path()
    ]


def main():
    offset = int(round(DEVREC_NON_PORT_OFFSET_UM / 0.001))

    # 默认左右光学端口保持器件左右端面，顶部和底部各外扩 0.5 µm。
    layout, cell = _new_cell("lr")
    cell.shapes(layout.layer(SI_LAYER)).insert(_box(0, 0, 100000, 10000))
    _assert(make_pins_for_cell_impl(cell, ["L", "R"]) == 2, "左右端口数量错误。")
    _assert(
        _devrec_bbox(cell) == _box(0, -offset, 100000, 10000 + offset),
        "左右端口时 DevRec 未按非端口边 0.5 µm 外扩。",
    )
    _assert(len(_pin_paths(cell)) == 2, "PinRec 数量错误。")

    # 顶端口保持顶边，其他三边外扩；Pin 仍落在物理器件边界而不是扩展边。
    layout, cell = _new_cell("top")
    cell.shapes(layout.layer(SI_LAYER)).insert(_box(0, 0, 100000, 10000))
    _assert(make_pins_for_cell_impl(cell, ["T"]) == 1, "顶部端口数量错误。")
    _assert(
        _devrec_bbox(cell) == _box(-offset, -offset, 100000 + offset, 10000),
        "顶部端口时 DevRec 外扩规则错误。",
    )

    # M1 是单器件实体范围的一部分，DevRec 必须覆盖其外接框。
    layout, cell = _new_cell("m1")
    cell.shapes(layout.layer(SI_LAYER)).insert(_box(0, 0, 100000, 10000))
    cell.shapes(layout.layer(M1_LAYER)).insert(_box(30000, 12000, 70000, 16000))
    _assert(make_pins_for_cell_impl(cell, ["L", "R"]) == 2, "含 M1 时左右端口数量错误。")
    _assert(
        _devrec_bbox(cell) == _box(0, -offset, 100000, 16000 + offset),
        "DevRec 未覆盖 M1 器件层或缺少顶部净空。",
    )

    # 单一旧版 Box DevRec 应升级；带额外标注的自定义 DevRec 则保持原状。
    layout, cell = _new_cell("legacy")
    cell.shapes(layout.layer(SI_LAYER)).insert(_box(0, 0, 100000, 10000))
    cell.shapes(layout.layer(DEVREC_LAYER)).insert(_box(0, 0, 100000, 10000))
    _assert(make_pins_for_cell_impl(cell, ["L", "R"]) == 2, "旧版 DevRec 升级后端口数量错误。")
    _assert(
        _devrec_bbox(cell) == _box(0, -offset, 100000, 10000 + offset),
        "旧版小 DevRec 未升级。",
    )

    print("OK: Make Pins DevRec follows SiEPIC non-port 0.5 um clearance.")


if __name__ == "__main__":
    main()
