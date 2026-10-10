# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""验证 Waveguide_Bump 的端口直段、直弯相切、无折回和 GDS 重读。"""

from pathlib import Path
import math
import sys
import tempfile

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

import JNULib  # noqa: E402,F401  注册 JNULib。

from JNU_MWP_pcells.waveguide_bump import (  # noqa: E402
    ARC_STEP_DEG,
    FOLD_FREE_MAX_ANGLE_DEG,
    bump_centerline,
    bump_dimensions,
    centerline_metrics,
    port_land_dbu,
)

LIBRARY_NAME = "JNULib"
PCell_NAME = "Pcell_Waveguide_Bump"
SI_LAYER = pya.LayerInfo(1, 0)
PIN_LAYER = pya.LayerInfo(1, 10)
DEVREC_LAYER = pya.LayerInfo(68, 0)
TEXT_LAYER = pya.LayerInfo(10, 0)

CASES = (
    ("default", 0.001, {"delta_length": 0.2}),
    ("large_delta_capped", 0.001, {"delta_length": 300.0, "max_theta": 179.0}),
    ("small_radius", 0.001, {"delta_length": 5.0, "radius": 5.0}),
    ("zero_delta", 0.001, {"delta_length": 0.0}),
    ("wide", 0.001, {"delta_length": 0.2, "width": 2.0}),
    ("coarse_dbu", 0.005, {"delta_length": 0.2}),
)
BASE = {"delta_length": 0.2, "width": 0.5, "radius": 20.0, "max_theta": 149.0}


def _materialize(dbu, overrides):
    layout = pya.Layout()
    layout.dbu = dbu
    params = dict(BASE)
    params.update(overrides)
    cell = layout.create_cell(PCell_NAME, LIBRARY_NAME, params)
    if cell is None:
        raise RuntimeError("无法创建 Waveguide_Bump PCell。")
    return layout, cell, params


def _si_polygon(cell, layout):
    shapes = list(cell.shapes(layout.layer(SI_LAYER)).each())
    if len(shapes) != 1:
        raise RuntimeError("Bump Si 层应只包含一个连续 Polygon。")
    shape = shapes[0]
    if shape.is_path() or not (shape.is_polygon() or shape.is_simple_polygon()):
        raise RuntimeError("Bump Si 实体不是 Polygon。")
    return shape.polygon


def _pin_records(cell, layout):
    records = []
    for shape in cell.shapes(layout.layer(PIN_LAYER)).each():
        if not shape.is_path():
            # PinRec 图层同时承载 SiEPIC 端口文字，这里只检查端口短 Path。
            continue
        points = list(shape.path.each_point())
        if len(points) != 2 or points[0].y != points[1].y:
            raise RuntimeError("Bump PinRec 不是水平短 Path。")
        records.append((
            (points[0].x + points[1].x) // 2,
            shape.path.width,
            180 if points[1].x < points[0].x else 0,
        ))
    return sorted(records)


def _section(cell, layout, x_dbu):
    region = pya.Region(cell.begin_shapes_rec(layout.layer(SI_LAYER)))
    probe = pya.Region(pya.Box(x_dbu, -100000, x_dbu + 1, 100000))
    return (region & probe).bbox()


def _check_port_landing(cell, layout, tag):
    land = port_land_dbu(layout.dbu)
    half = int(round(float(cell.pcell_parameters_by_name()["width"])
                     / layout.dbu / 2.0))
    for probe in (0, land // 2, land):
        box = _section(cell, layout, probe)
        if box.empty():
            raise RuntimeError("%s: 端口直段在 x=%d DBU 处缺少 Si。" % (tag, probe))
        if box.bottom != -half or box.top != half:
            raise RuntimeError(
                "%s: 端口直段截面不是居中恒宽直波导：%s。" % (tag, box))
    probe = _section(cell, layout, land + 1)
    if probe.empty():
        raise RuntimeError("%s: 端口直段之后缺少 Si。" % tag)


def _check_no_fold(polygon, tag):
    if polygon.bbox().left < 0:
        raise RuntimeError("%s: 圆弧折回端口平面，Si 越过了输入端口。" % tag)


def _check_tangent(cell, layout, tag, params):
    points, _, _ = bump_centerline(
        params["delta_length"], params["radius"], params["max_theta"], layout.dbu)
    if len(points) < 3:
        return
    if points[1].y != points[0].y or points[1].x <= points[0].x:
        raise RuntimeError("%s: 入口直段不水平或长度为零。" % tag)
    if points[-1].y != points[-2].y or points[-1].x <= points[-2].x:
        raise RuntimeError("%s: 出口直段不水平或长度为零。" % tag)
    heading = math.degrees(math.atan2(points[2].y - points[1].y,
                                      points[2].x - points[1].x))
    if abs(heading) > ARC_STEP_DEG:
        raise RuntimeError("%s: 直弯连接处方向突变 %.4f°，超过采样上限。" % (tag, heading))


def _check_devrec(cell, layout, tag):
    shapes = list(cell.shapes(layout.layer(DEVREC_LAYER)).each())
    if len(shapes) != 1:
        raise RuntimeError("%s: Bump DevRec 不是单一矩形。" % tag)
    devrec = shapes[0].box
    si = cell.bbox(layout.layer(SI_LAYER))
    if devrec.left != si.left or devrec.right != si.right:
        raise RuntimeError("%s: Bump DevRec 未与两个端口端面齐平。" % tag)
    clearance = int(round(1.0 / layout.dbu))
    if devrec.bottom != si.bottom - clearance or devrec.top != si.top + clearance:
        raise RuntimeError("%s: Bump DevRec 上下净空不是 1 µm。" % tag)


def _check_parameter_order():
    declaration = pya.Library.library_by_name(LIBRARY_NAME).layout() \
        .pcell_declaration(PCell_NAME)
    if declaration is None:
        raise RuntimeError("无法读取 Bump PCell 声明。")
    flags = [(parameter.name, bool(parameter.readonly))
             for parameter in declaration.get_parameters()]
    names = [name for name, _ in flags]
    readonly = [name for name, flag in flags if flag]
    if not readonly:
        raise RuntimeError("Bump 缺少只读派生参数。")
    first_readonly = names.index(readonly[0])
    if flags[:first_readonly] != [(name, False) for name in names[:first_readonly]]:
        raise RuntimeError("Bump 可编辑参数与只读参数顺序错误。")
    if names[first_readonly:] != readonly:
        raise RuntimeError("Bump 只读参数未集中排在末尾。")
    if names[:first_readonly] != ["delta_length", "width", "radius", "max_theta"]:
        raise RuntimeError("Bump 可编辑参数顺序改变：%s。" % names[:first_readonly])


def _check_cases():
    for tag, dbu, overrides in CASES:
        layout, cell, params = _materialize(dbu, overrides)
        polygon = _si_polygon(cell, layout)
        _check_no_fold(polygon, tag)
        _check_port_landing(cell, layout, tag)
        _check_tangent(cell, layout, tag, params)
        _check_devrec(cell, layout, tag)
        if len(_pin_records(cell, layout)) != 2:
            raise RuntimeError("%s: Bump 端口数量不是 2。" % tag)
        records = _pin_records(cell, layout)
        directions = sorted(record[2] for record in records)
        if directions != [0, 180]:
            raise RuntimeError("%s: Bump 端口方向不是 180°/0°。" % tag)
        if any(record[1] != int(round(float(params["width"]) / dbu))
               for record in records):
            raise RuntimeError("%s: Bump PinRec 宽度与波导宽度不一致。" % tag)
        points, _, analytic_delta = bump_centerline(
            params["delta_length"], params["radius"], params["max_theta"], dbu)
        physical, straight, actual_delta = centerline_metrics(points, dbu)
        if abs(physical - straight - actual_delta) > 1e-9:
            raise RuntimeError("%s: Bump 增量长度派生不一致。" % tag)
        tolerance = max(0.01, 8 * dbu)
        if abs(actual_delta - analytic_delta) > tolerance:
            raise RuntimeError(
                "%s: Bump 量化后增量长度偏差 %.4f µm 超过容差。" % (
                    tag, abs(actual_delta - analytic_delta)))
        texts = [shape.text.string for shape in
                 cell.shapes(layout.layer(TEXT_LAYER)).each()]
        if not any("dL = " in text for text in texts):
            raise RuntimeError("%s: Bump 缺少增量长度文字。" % tag)


def _check_angle_clamp():
    layout = pya.Layout()
    layout.dbu = 0.001
    cell = layout.create_cell(PCell_NAME, LIBRARY_NAME, {
        "delta_length": 300.0, "width": 0.5, "radius": 20.0, "max_theta": 179.0})
    theta, _, actual = bump_dimensions(300.0, 20.0, 179.0)
    limit = math.radians(FOLD_FREE_MAX_ANGLE_DEG)
    if abs(theta - limit) > 1e-9:
        raise RuntimeError("Bump 端点直段在最大增量长度时仍可能被圆弧压住。")
    if actual >= 300.0:
        raise RuntimeError("Bump 未按不折回角度限制增量长度。")
    points, _, _ = bump_centerline(300.0, 20.0, 179.0, layout.dbu)
    if min(point.x for point in points) < 0:
        raise RuntimeError("Bump 中心线折回输入端口。")
    polygon = _si_polygon(cell, layout)
    if polygon.bbox().left < 0:
        raise RuntimeError("Bump Si 折回输入端口。")
    land = port_land_dbu(layout.dbu)
    for probe in (0, land // 2, land):
        box = _section(cell, layout, probe)
        if box.empty() or box.bottom != -250 or box.top != 250:
            raise RuntimeError("Bump 最大角度封顶后端口直段被破坏。")


def _check_gds_reopen():
    layout, cell, params = _materialize(0.001, {"delta_length": 1.0})
    top = layout.create_cell("JNU_BUMP_REGRESSION")
    top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans()))
    with tempfile.TemporaryDirectory(prefix="jnu_bump_") as temp_dir:
        output = str(Path(temp_dir) / "bump_regression.gds")
        layout.write(output)
        reopened = pya.Layout()
        reopened.read(output)
        if [name for name in (c.name for c in reopened.top_cells())] != [
                "JNU_BUMP_REGRESSION"]:
            raise RuntimeError("Bump GDS 重读后出现额外顶层 cell。")
        variant = next(reopened.cell(child.cell_index)
                       for child in reopened.cell("JNU_BUMP_REGRESSION").each_inst())
        if not variant.is_pcell_variant():
            raise RuntimeError("Bump GDS 重读后不再是 PCell。")
        if abs(float(variant.pcell_parameters_by_name()["delta_length"]) - 1.0) > 1e-6:
            raise RuntimeError("Bump GDS 重读后参数丢失。")
        _si_polygon(variant, reopened)
        _check_port_landing(variant, reopened, "reopen")
        _check_no_fold(_si_polygon(variant, reopened), "reopen")


def main():
    _check_cases()
    _check_angle_clamp()
    _check_parameter_order()
    _check_gds_reopen()
    print("Waveguide_Bump regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
