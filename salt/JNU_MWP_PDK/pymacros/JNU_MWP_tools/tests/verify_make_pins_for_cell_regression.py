# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

"""验证 Make Pins for Cell 的 DevRec 外扩与端口边界规则。"""

from pathlib import Path
import sys
import tempfile

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


def _check_physical_pins(cell, ports, bbox):
    expected = {
        "L": (bbox.left, bbox.center().y, bbox.height(), -20, 0),
        "R": (bbox.right, bbox.center().y, bbox.height(), 20, 0),
        "T": (bbox.center().x, bbox.top, bbox.width(), 0, 20),
        "B": (bbox.center().x, bbox.bottom, bbox.width(), 0, -20),
    }
    actual = []
    silicon = pya.Region(cell.begin_shapes_rec(cell.layout().layer(SI_LAYER)))
    for path in _pin_paths(cell):
        points = list(path.each_point())
        center = path.bbox().center()
        actual.append((center.x, center.y, path.width,
                       points[-1].x - points[0].x, points[-1].y - points[0].y))
        pin = pya.Region(path.polygon())
        _assert((pin & silicon).area() * 2 == pin.area(),
                "PinRec 必须以物理端面为中心，一半露在 Si 外。")
    _assert(sorted(actual) == sorted(expected[side] for side in ports),
            "端口位置、宽度或方向受 DevRec 影响：%s" % (actual,))


def _check_devrec_independence():
    bbox = _box(0, 0, 100000, 10000)
    cases = [
        ("partial", _box(-5000, -5000, 100000, 15000), ["L", "R"]),
        ("oversized", _box(-5000, -5000, 105000, 15000), ["L", "R", "T", "B"]),
        ("inset", pya.Polygon(_box(1000, 1000, 99000, 9000)), ["L", "R", "T", "B"]),
    ]
    with tempfile.TemporaryDirectory(prefix="jnu-make-pins-") as directory:
        for name, devrec, ports in cases:
            layout, cell = _new_cell(name)
            cell.shapes(layout.layer(SI_LAYER)).insert(bbox)
            shapes = cell.shapes(layout.layer(DEVREC_LAYER))
            shapes.insert(devrec)
            before = [str(shape) for shape in shapes.each()]
            _assert(make_pins_for_cell_impl(cell, ports) == len(ports),
                    "已有 DevRec 时遗漏物理端口：%s" % name)
            _assert([str(shape) for shape in shapes.each()] == before,
                    "不应改写已有的较大或自定义 DevRec。")
            _check_physical_pins(cell, ports, bbox)
            filename = str(Path(directory) / (name + ".gds"))
            layout.write(filename)
            restored = pya.Layout()
            restored.read(filename)
            _check_physical_pins(restored.cell(name), ports, bbox)

    # 实体与 DevRec 均可来自子层级，实例变换后仍应使用实体端面。
    layout, cell = _new_cell("hierarchy")
    child = layout.create_cell("device")
    child.shapes(layout.layer(SI_LAYER)).insert(bbox)
    child.shapes(layout.layer(DEVREC_LAYER)).insert(
        pya.Polygon(_box(1000, 1000, 99000, 9000)))
    transform = pya.Trans(pya.Trans.R90, 200000, 300000)
    cell.insert(pya.CellInstArray(child.cell_index(), transform))
    ports = ["L", "R", "T", "B"]
    _assert(make_pins_for_cell_impl(cell, ports) == 4, "子层级端口数量错误。")
    _check_physical_pins(cell, ports, bbox.transformed(transform))

    # 只有器件识别层而没有物理图形时，不得凭 DevRec 生成 PinRec。
    layout, cell = _new_cell("devrec_only")
    cell.shapes(layout.layer(DEVREC_LAYER)).insert(bbox)
    _assert(make_pins_for_cell_impl(cell, ["L", "R"]) == 0,
            "无实体层时不应生成端口。")
    _assert(not _pin_paths(cell), "DevRec 不应被当作器件实体。")


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

    _check_devrec_independence()
    print("OK: Make Pins uses physical boundaries independently of DevRec; GDS roundtrip passed.")


if __name__ == "__main__":
    main()
