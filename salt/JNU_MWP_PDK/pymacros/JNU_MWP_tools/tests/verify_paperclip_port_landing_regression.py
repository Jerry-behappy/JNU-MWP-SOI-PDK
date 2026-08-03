# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-08
"""验证 Paperclip_Spiral 的 Si 端口内侧存在严格水平的 10 nm landing。"""

import os
import sys
import tempfile
from pathlib import Path

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

import JNULib  # noqa: F401,E402
from JNU_MWP_pcells.bend_90deg import PORT_STRAIGHT_UM  # noqa: E402


SI_LAYER = pya.LayerInfo(1, 0)
PIN_LAYER = pya.LayerInfo(1, 10)


def _si_region(cell, layer_index):
    """合并当前 cell 的 Si polygon，便于检查端口内部矩形是否完整覆盖。"""
    region = pya.Region()
    for shape in cell.shapes(layer_index).each():
        if shape.is_polygon() or shape.is_simple_polygon():
            region.insert(shape.polygon)
    return region.merged()


def _pin_paths(cell, layer_index):
    """读取两个 PinRec 短路径。"""
    paths = [shape.path for shape in cell.shapes(layer_index).each() if shape.is_path()]
    if len(paths) != 2:
        raise RuntimeError("Paperclip_Spiral 应有两个 PinRec Path，实际为 %d。" % len(paths))
    return paths


def _shape_covers_point(shape, point):
    """用 2×2 DBU 探针判断面积 shape 是否真实覆盖指定点。"""
    if shape.is_box():
        shape_region = pya.Region(shape.box)
    elif shape.is_polygon() or shape.is_simple_polygon():
        shape_region = pya.Region(shape.polygon)
    else:
        return False
    probe = pya.Region(
        pya.Box(point.x - 1, point.y - 1, point.x + 1, point.y + 1)
    )
    return not (shape_region & probe).is_empty()


def _has_vertical_port_face(cell, layer_index, x, center_y, half_width):
    """检查 Si polygon 是否在 PinRec 外端具有完整且严格竖直的端面。"""
    for shape in cell.shapes(layer_index).each():
        if not (shape.is_polygon() or shape.is_simple_polygon()):
            continue
        points = list(shape.polygon.each_point_hull())
        for index, point1 in enumerate(points):
            point2 = points[(index + 1) % len(points)]
            if point1.x != x or point2.x != x:
                continue
            lower = min(point1.y, point2.y)
            upper = max(point1.y, point2.y)
            if lower <= center_y - half_width and upper >= center_y + half_width:
                return True
    return False


def _assert_horizontal_landing(cell, layout):
    """确认 Si 端面位于 pin 中心，且只有 pin 内侧一半与 Si 重叠。"""
    dbu = layout.dbu
    landing_dbu = int(round(PORT_STRAIGHT_UM / dbu))
    si_layer = layout.layer(SI_LAYER)
    si_region = _si_region(cell, si_layer)
    component_count = sum(1 for _polygon in si_region.each())
    if component_count != 1:
        raise RuntimeError(
            "Paperclip_Spiral Si 波导包含 %d 个断开的区域。" % component_count
        )
    for path in _pin_paths(cell, layout.layer(PIN_LAYER)):
        points = list(path.each_point())
        dx = points[-1].x - points[0].x
        dy = points[-1].y - points[0].y
        if dy != 0 or dx == 0:
            raise RuntimeError("Paperclip_Spiral PinRec 必须严格为 0 或 180 度。")

        center_x = int(round(0.5 * (points[0].x + points[-1].x)))
        center_y = int(round(0.5 * (points[0].y + points[-1].y)))
        inward_sign = 1 if dx < 0 else -1
        inner_probe = pya.Point(center_x + inward_sign, center_y)
        port_shape_count = sum(
            1
            for shape in cell.shapes(si_layer).each()
            if _shape_covers_point(shape, inner_probe)
        )
        if port_shape_count != 1:
            raise RuntimeError(
                "Paperclip_Spiral 端口中心应只由 1 个合并 Si shape 覆盖，实际为 %d。"
                % port_shape_count
            )
        half_width = max(1, path.width // 2)
        outer_x = center_x - inward_sign * landing_dbu
        if not _has_vertical_port_face(
            cell, layout.layer(SI_LAYER), center_x, center_y, half_width
        ):
            raise RuntimeError("Paperclip_Spiral Si 端面不在 PinRec 中心或不严格竖直。")
        x1 = min(center_x, center_x + inward_sign * landing_dbu)
        x2 = max(center_x, center_x + inward_sign * landing_dbu)
        landing_box = pya.Box(x1, center_y - half_width, x2, center_y + half_width)
        missing = pya.Region(landing_box) - si_region
        if not missing.is_empty():
            raise RuntimeError("Paperclip_Spiral Si 端口内侧缺少严格 10 nm 水平 landing。")

        outer_box = pya.Box(
            min(outer_x, center_x),
            center_y - half_width,
            max(outer_x, center_x),
            center_y + half_width,
        )
        outside_si = pya.Region(outer_box) & si_region
        if not outside_si.is_empty():
            raise RuntimeError("Paperclip_Spiral PinRec 外侧一半仍被 Si 覆盖。")


def main():
    """创建全部组合，并在写出、重读 GDS 后再次检查端口连续性。"""
    layout = pya.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("PAPERCLIP_PORT_REGRESSION_TOP")
    variant_index = 0
    for bend_type in ("Circular", "Bezier", "Euler"):
        for ports_type in ("type1", "type2", "type3"):
            params = {
                "bend_type": bend_type,
                "bend_radius": 20.0,
                "bezier": 0.35,
                "Euler_Rmax": 30.0,
                "Euler_Rmin": 10.0,
                "wg_width": 0.5,
                "gap": 2.0,
                "length": 100.0,
                "loops": 2,
                "ports_type": ports_type,
            }
            cell = layout.create_cell("Paperclip_Spiral", "JNULib", params)
            if cell is None:
                raise RuntimeError("无法创建 Paperclip_Spiral PCell。")
            try:
                _assert_horizontal_landing(cell, layout)
            except Exception as error:
                raise RuntimeError(
                    "bend=%s ports=%s：%s" % (bend_type, ports_type, error)
                )
            top.insert(
                pya.CellInstArray(
                    cell.cell_index(), pya.Trans(variant_index * 500000, 0)
                )
            )
            variant_index += 1

    output_path = os.path.join(
        tempfile.gettempdir(), "jnu_paperclip_port_landing_regression.gds"
    )
    try:
        layout.write(output_path)
        reread = pya.Layout()
        reread.read(output_path)
        checked = 0
        for cell in reread.each_cell():
            if "paperclip_spiral" not in cell.name.lower():
                continue
            _assert_horizontal_landing(cell, reread)
            checked += 1
        if checked != 9:
            raise RuntimeError(
                "重读 GDS 后应检查 9 个 Paperclip variant，实际为 %d。" % checked
            )
    finally:
        if os.path.isfile(output_path):
            os.remove(output_path)
    print("Paperclip port landing regression: PASS")


main()
