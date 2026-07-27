# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""把中心线扫掠结果写成 Polygon 的公共几何工具。"""

import pya


def _dedupe_points(points):
    """将点量化为整数坐标，并删除连续重复点。"""

    clean = []
    for point in points:
        converted = pya.Point(int(round(point.x)), int(round(point.y)))
        if not clean or clean[-1] != converted:
            clean.append(converted)
    return clean


def centerline_path_region(points, width, bgn_ext=0, end_ext=0):
    """返回中心线按给定宽度扫掠并规范化后的 Polygon Region。"""

    clean = _dedupe_points(points)
    region = pya.Region()
    if len(clean) < 2:
        return region

    path = pya.Path(
        clean,
        max(1, int(round(width))),
        int(round(bgn_ext)),
        int(round(end_ext)),
    )
    region.insert(path.polygon())
    region.merge()
    return region


def insert_centerline_polygons(
    cell,
    layer,
    points,
    width,
    bgn_ext=0,
    end_ext=0,
):
    """把中心线扫掠区域仅以 Polygon 图形写入目标图层。"""

    region = centerline_path_region(points, width, bgn_ext, end_ext)
    count = 0
    for polygon in region.each():
        cell.shapes(layer).insert(polygon)
        count += 1
    return count


__all__ = ["centerline_path_region", "insert_centerline_polygons"]
