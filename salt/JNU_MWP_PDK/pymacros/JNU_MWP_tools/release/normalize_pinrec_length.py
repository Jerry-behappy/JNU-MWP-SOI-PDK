# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

"""把固定 GDS 中的 PinRec 短路径统一为 20 nm。"""

import argparse
import glob
import os
from pathlib import Path
import math

import pya


PIN_LAYER = pya.LayerInfo(1, 10)
PIN_LENGTH_UM = 0.02


def normalize_layout(layout):
    """原地修正 layout 中所有 PinRec Path 的长度，返回修正数量。"""

    pin_index = layout.find_layer(PIN_LAYER)
    if pin_index is None:
        return 0

    expected_length = max(1, int(round(PIN_LENGTH_UM / layout.dbu)))
    changed = 0
    for cell in layout.each_cell():
        shapes = cell.shapes(pin_index)
        for shape in list(shapes.each()):
            if not shape.is_path():
                continue
            path = shape.path
            points = list(path.each_point())
            if len(points) < 2:
                continue
            start, end = points[0], points[-1]
            dx, dy = end.x - start.x, end.y - start.y
            length = math.hypot(dx, dy)
            if length == 0 or int(round(length)) == expected_length:
                continue

            half = expected_length / 2.0
            unit_x, unit_y = dx / length, dy / length
            center_x = (start.x + end.x) / 2.0
            center_y = (start.y + end.y) / 2.0
            normalized = pya.Path(
                [
                    pya.Point(
                        int(round(center_x - unit_x * half)),
                        int(round(center_y - unit_y * half)),
                    ),
                    pya.Point(
                        int(round(center_x + unit_x * half)),
                        int(round(center_y + unit_y * half)),
                    ),
                ],
                path.width,
            )
            shapes.replace(shape, normalized)
            changed += 1
    return changed


def normalize_file(path):
    path = Path(path)
    layout = pya.Layout()
    layout.read(str(path))
    changed = normalize_layout(layout)
    if changed:
        layout.write(str(path))
    return changed


def main():
    configured = os.environ.get("JNU_NORMALIZE_PATHS") or globals().get("normalize_paths")
    if configured:
        configured_paths = [value.strip() for value in str(configured).split(";") if value.strip()]
        parser = argparse.ArgumentParser(description="统一固定 GDS 的 PinRec 短路径为 20 nm。")
        parser.add_argument("paths", nargs="+", help="待处理的 GDS 文件。")
        args = parser.parse_args(["--"] + configured_paths)
    else:
        parser = argparse.ArgumentParser(description="统一固定 GDS 的 PinRec 短路径为 20 nm。")
        parser.add_argument("paths", nargs="+", help="待处理的 GDS 文件。")
        args = parser.parse_args()

    total = 0
    for raw_path in args.paths:
        matched_paths = sorted(Path(value) for value in glob.glob(raw_path))
        for path in matched_paths if matched_paths else [Path(raw_path)]:
            changed = normalize_file(path)
            total += changed
            print("%s: %d" % (path, changed))
    print("normalized_pinrec_paths=%d" % total)


if __name__ == "__main__":
    main()
