# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-08

"""验证 Cell Connect by Waveguide 的内部 Waveguide 与 S_Bend 自动选择。"""

import os
from pathlib import Path
import sys
import tempfile

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

import JNULib  # noqa: F401,E402
from JNU_MWP_tools.actions.cell_connect_by_waveguide import (  # noqa: E402
    _insert_prepared_connection,
    _prepare_connection,
)
from JNU_MWP_tools.actions.sbend_connect import (  # noqa: E402
    _choose_sbend_pin_pair,
    _pins_for_instance,
)
from JNU_MWP_tools.actions.waveguide_to_path import (  # noqa: E402
    _path_from_waveguide_cell,
)
from JNU_MWP_tools.core.common import _OpticalPin  # noqa: E402


DBU = 0.001
PIN_LAYER = pya.LayerInfo(1, 10)


def _assert(condition, message):
    if not condition:
        raise RuntimeError(message)


def _pin(x, y, rotation, width=500):
    return _OpticalPin(pya.Point(x, y), rotation, width)


def _declaration_name(cell):
    declaration = cell.pcell_declaration()
    return declaration.name() if declaration is not None else ""


def _assert_connection(layout, top, start_pin, end_pin, is_vertical, expected_kind):
    connection = _prepare_connection(layout, start_pin, end_pin, is_vertical)
    _assert(connection["kind"] == expected_kind, "连接 PCell 类型选择错误。")
    _assert(connection["cell"].is_pcell_variant(), "连接结果不是可编辑 PCell variant。")
    _assert(
        _declaration_name(connection["cell"]) == expected_kind,
        "连接 PCell declaration 名称错误。",
    )

    if expected_kind == "Waveguide":
        params = connection["cell"].pcell_parameters_by_name()
        raw_dpath = params.get("path")
        _assert(isinstance(raw_dpath, pya.DPath), "共线连接没有保存原始 DPath 参数。")
        raw_points = list(raw_dpath.each_point())
        _assert(len(raw_points) == 2, "共线连接的原始 Path 不是两点直线。")
        _assert(
            raw_points[0] == pya.DPoint(0.0, 0.0)
            and abs(raw_points[1].x - connection["length_um"]) < 1e-12
            and abs(raw_points[1].y) < 1e-12,
            "共线连接的原始 Path 坐标错误。",
        )
        recovered = _path_from_waveguide_cell(connection["cell"], layout)
        _assert(recovered is not None, "共线连接无法由 Waveguide to Path 恢复。")

    instance = _insert_prepared_connection(top, connection)
    transformed_pins = _pins_for_instance(instance, instance.trans, layout)
    _assert(len(transformed_pins) == 2, "连接 PCell 的 PinRec 数量错误。")
    by_center = {(pin.center.x, pin.center.y): pin for pin in transformed_pins}
    start_key = (start_pin.center.x, start_pin.center.y)
    end_key = (end_pin.center.x, end_pin.center.y)
    _assert(start_key in by_center and end_key in by_center, "连接 PCell 端点未对准目标端口。")
    _assert(
        by_center[start_key].rotation == (start_pin.rotation + 180) % 360,
        "连接 PCell 起点方向未与器件端口相向。",
    )
    _assert(
        by_center[end_key].rotation == (end_pin.rotation + 180) % 360,
        "连接 PCell 终点方向未与器件端口相向。",
    )
    return connection


def main():
    layout = pya.Layout()
    layout.dbu = DBU
    top = layout.create_cell("CELL_CONNECT_REGRESSION")

    # 最近端口选择必须忽略距离更远但方向同样兼容的端口。
    near_start = _pin(0, 0, 0)
    near_end = _pin(60000, 0, 180)
    pair = _choose_sbend_pin_pair(
        [near_start, _pin(0, 200000, 0)],
        [near_end, _pin(60000, 240000, 180)],
    )
    _assert(pair is not None and pair[0] is near_start and pair[1] is near_end, "未选择最近端口对。")

    horizontal_waveguide = _assert_connection(
        layout, top, near_start, near_end, False, "Waveguide"
    )
    _assert(horizontal_waveguide["height_um"] == 0.0, "水平直波导不应有侧向偏移。")

    horizontal_sbend = _assert_connection(
        layout,
        top,
        _pin(0, 100000, 0),
        _pin(60000, 120000, 180),
        False,
        "S_Bend",
    )
    _assert(abs(horizontal_sbend["height_um"] - 20.0) < 1e-12, "水平 S_Bend 高度错误。")

    vertical_waveguide = _assert_connection(
        layout,
        top,
        _pin(200000, 200000, 270),
        _pin(200000, 140000, 90),
        True,
        "Waveguide",
    )
    _assert(vertical_waveguide["height_um"] == 0.0, "垂直直波导不应有侧向偏移。")

    vertical_sbend = _assert_connection(
        layout,
        top,
        _pin(300000, 200000, 270),
        _pin(320000, 140000, 90),
        True,
        "S_Bend",
    )
    _assert(abs(vertical_sbend["height_um"] - 20.0) < 1e-12, "垂直 S_Bend 偏移错误。")

    # 写出再读回，确认四个连接实例不会破坏 GDS 层级。
    output = Path(tempfile.gettempdir()) / "jnu_cell_connect_regression.gds"
    try:
        layout.write(str(output))
        reread = pya.Layout()
        reread.read(str(output))
        reread_top = reread.cell("CELL_CONNECT_REGRESSION")
        _assert(reread_top is not None, "GDS 重读后缺少连接测试顶层 Cell。")
        _assert(sum(1 for _inst in reread_top.each_inst()) == 4, "GDS 重读后连接实例数量错误。")
        _assert(reread.layer(PIN_LAYER) is not None, "GDS 重读后缺少 PinRec 图层。")
        recovered_paths = []
        for instance in reread_top.each_inst():
            recovered = _path_from_waveguide_cell(instance.cell, reread, instance)
            if recovered is not None:
                recovered_paths.append(recovered)
        _assert(len(recovered_paths) == 2, "GDS 重读后共线 Waveguide 恢复 Path 数量错误。")
    finally:
        try:
            os.remove(str(output))
        except OSError:
            pass

    print("OK: Cell Connect selected Path-to-Waveguide or S_Bend for horizontal and vertical pins")


if __name__ == "__main__":
    main()
