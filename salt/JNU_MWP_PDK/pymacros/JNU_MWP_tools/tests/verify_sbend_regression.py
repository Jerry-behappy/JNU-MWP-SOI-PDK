# -*- coding: utf-8 -*-
"""验证 S_Bend Bezier 参数语义和 SBend connect 默认值。"""

import os
from pathlib import Path
import sys
import tempfile

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

from JNU_MWP_pcells.s_bend_waveguide import (  # noqa: E402
    DEFAULT_BEZIER,
    _bezier_control_points,
)
from JNU_MWP_tools.actions.sbend_connect import (  # noqa: E402
    DEFAULT_SBEND_CONNECT_BEZIER,
    DEFAULT_SBEND_CONNECT_RADIUS,
    _create_sbend_connect_pcell,
)


DBU = 0.001
SI_LAYER = pya.LayerInfo(1, 0)
WG_LAYER = pya.LayerInfo(1, 99)
PIN_LAYER = pya.LayerInfo(1, 10)
DEVREC_LAYER = pya.LayerInfo(68, 0)


def _assert_close(actual, expected, label, tolerance=1e-12):
    if abs(float(actual) - float(expected)) > tolerance:
        raise RuntimeError("%s：期望 %.12f，实际 %.12f。" % (label, expected, actual))


def _check_bezier_control_semantics():
    """B 必须直接等于第二控制点的归一化水平坐标。"""
    length = 60.0
    height = 20.0
    for bezier in (0.35, 0.365):
        p0, p1, p2, p3 = _bezier_control_points(length, height, bezier)
        _assert_close(p0.x, 0.0, "P0.x")
        _assert_close(p1.x / length, 1.0 - bezier, "P1.x/L")
        _assert_close(p2.x / length, bezier, "P2.x/L")
        _assert_close(p3.x, length, "P3.x")
        _assert_close(p1.y, 0.0, "P1.y")
        _assert_close(p2.y, height, "P2.y")


def _check_connect_defaults_and_geometry():
    """连接工具必须创建 Bezier、B=0.3、R=30 的可编辑 PCell。"""
    layout = pya.Layout()
    layout.dbu = DBU
    top = layout.create_cell("SBEND_CONNECT_REGRESSION")
    cell = _create_sbend_connect_pcell(layout, 0.5, 60.0, 20.0)
    if cell is None or not cell.is_pcell_variant():
        raise RuntimeError("SBend connect 未创建 S_Bend PCell variant。")

    declaration = cell.pcell_declaration()
    declaration_name = declaration.name() if declaration is not None else ""
    if declaration_name != "S_Bend":
        raise RuntimeError("SBend connect 创建的公开 PCell 名称不是 S_Bend。")
    library = pya.Library.library_by_name("JNULib")
    public_names = set(library.layout().pcell_names()) if library is not None else set()
    if "S_Bend" not in public_names or "S_Bend_Waveguide" in public_names:
        raise RuntimeError("公开 PCell 列表未完成 S_Bend 唯一名称迁移。")

    params = cell.pcell_parameters_by_name()
    if str(params.get("bend_type")) != "Bezier":
        raise RuntimeError("SBend connect 默认弯曲类型不是 Bezier。")
    _assert_close(params.get("bezier"), DEFAULT_SBEND_CONNECT_BEZIER, "默认 B")
    _assert_close(params.get("radius"), DEFAULT_SBEND_CONNECT_RADIUS, "默认 R")
    _assert_close(DEFAULT_BEZIER, 0.35, "S_Bend 默认 B")

    top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans()))
    if not cell.shapes(layout.layer(WG_LAYER)).is_empty():
        raise RuntimeError("S_Bend 不应再向 1/99 写入中心线图形。")
    for layer_info, label in ((SI_LAYER, "Si"), (DEVREC_LAYER, "DevRec")):
        shapes = list(cell.shapes(layout.layer(layer_info)).each())
        if not shapes or any(shape.is_path() for shape in shapes):
            raise RuntimeError("S_Bend %s 层未完全转换为 Polygon。" % label)
        if any(not (shape.is_polygon() or shape.is_simple_polygon()) for shape in shapes):
            raise RuntimeError("S_Bend %s 层包含非 Polygon 实体。" % label)
    pin_paths = [shape.path for shape in cell.shapes(layout.layer(PIN_LAYER)).each() if shape.is_path()]
    if len(pin_paths) != 2:
        raise RuntimeError("S_Bend PinRec 端口数量错误。")
    pin_points = [list(path.each_point()) for path in pin_paths]
    if any(len(points) != 2 or points[0].y != points[1].y for points in pin_points):
        raise RuntimeError("S_Bend PinRec 端口不是严格水平短 Path。")
    directions = sorted(1 if points[1].x > points[0].x else -1 for points in pin_points)
    if directions != [-1, 1]:
        raise RuntimeError("S_Bend opt1/opt2 的 Path 点序方向错误。")

    output = Path(tempfile.gettempdir()) / "jnu_sbend_regression.gds"
    try:
        layout.write(str(output))
        reread = pya.Layout()
        reread.read(str(output))
        if [item.name for item in reread.top_cells()] != ["SBEND_CONNECT_REGRESSION"]:
            raise RuntimeError("S_Bend GDS 重读后出现额外顶层 cell。")
        reread_cell = reread.cell(cell.name)
        if reread_cell is None:
            raise RuntimeError("S_Bend GDS 重读后缺少波导 cell。")
        if not reread_cell.shapes(reread.layer(WG_LAYER)).is_empty():
            raise RuntimeError("S_Bend GDS 重读后重新出现 1/99 图形。")
        for layer_info, label in ((SI_LAYER, "Si"), (DEVREC_LAYER, "DevRec")):
            shapes = list(reread_cell.shapes(reread.layer(layer_info)).each())
            if not shapes or any(shape.is_path() for shape in shapes):
                raise RuntimeError("S_Bend GDS 重读后 %s 不是 Polygon。" % label)
        reread_pins = [
            shape.path
            for shape in reread_cell.shapes(reread.layer(PIN_LAYER)).each()
            if shape.is_path()
        ]
        if len(reread_pins) != 2:
            raise RuntimeError("S_Bend GDS 重读后 PinRec Path 数量错误。")
    finally:
        try:
            os.remove(str(output))
        except OSError:
            pass


def main():
    _check_bezier_control_semantics()
    _check_connect_defaults_and_geometry()
    print("S_Bend regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
