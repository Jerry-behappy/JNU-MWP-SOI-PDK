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
    _instance_local_ports,
    make_pins_for_cell_impl,
)
from JNU_MWP_tools.core.common import DEVREC_LAYER, M1_LAYER, PIN_LAYER, SI_LAYER
from JNU_MWP_tools.core.make_pin import make_pin


def _assert(condition, message):
    if not condition:
        raise RuntimeError(message)


def _new_cell(name, dbu=0.001):
    layout = pya.Layout()
    layout.dbu = dbu
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


def _check_pin_length_independent_of_dbu():
    """PinRec 短路径在任何 dbu 下都必须保持 20 nm。"""

    for dbu in (0.001, 0.0001):
        layout, cell = _new_cell("pin_length_%s" % dbu, dbu=dbu)
        width_dbu = int(round(0.5 / dbu))
        make_pin(cell, "opt1", pya.Point(0, 0), width_dbu, layout.layer(PIN_LAYER), 0)
        path = _pin_paths(cell)[0]
        points = list(path.each_point())
        expected_length = int(round(0.02 / dbu))
        _assert(
            abs(points[-1].x - points[0].x) == expected_length,
            "PinRec 短路径在 dbu=%s 时不是 20 nm。" % dbu,
        )


def _check_rotated_instance_port_mapping():
    """旋转实例时，GUI 选择的全局端口方向应映射到正确的 cell 本地边。"""

    cases = (
        (pya.Trans.R90, "T", "R"),
        (pya.Trans.R180, "T", "B"),
        (pya.Trans.R270, "T", "L"),
        (pya.Trans.M0, "T", "B"),
    )
    for rotation, requested, expected in cases:
        actual = _instance_local_ports([requested], pya.Trans(rotation))
        _assert(
            actual == [expected],
            "实例变换 %s 下全局 %s 端口被映射为 %s。" % (rotation, requested, actual),
        )

    layout, cell = _new_cell("rotated_instance")
    child = layout.create_cell("rotated_child")
    child.shapes(layout.layer(SI_LAYER)).insert(_box(0, 0, 100000, 10000))
    instance = cell.insert(pya.CellInstArray(child.cell_index(), pya.Trans(pya.Trans.R90)))
    local_ports = _instance_local_ports(["T"], instance.trans)
    _assert(make_pins_for_cell_impl(child, ports=local_ports) == 1,
            "旋转实例的全局顶边没有生成端口。")
    path = _pin_paths(child)[0]
    points = list(path.each_point())
    _assert(path.bbox().center().x == 100000 and points[1].x > points[0].x,
            "全局顶边端口没有映射到 cell 本地右边。")
    transformed_center = instance.trans * path.bbox().center()
    _assert(transformed_center.y == 100000,
            "旋转后端口没有落在实例顶层物理顶边上。")


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
    _check_pin_length_independent_of_dbu()
    _check_rotated_instance_port_mapping()
    print("OK: Make Pins uses physical boundaries independently of DevRec; GDS roundtrip passed.")


if __name__ == "__main__":
    main()
