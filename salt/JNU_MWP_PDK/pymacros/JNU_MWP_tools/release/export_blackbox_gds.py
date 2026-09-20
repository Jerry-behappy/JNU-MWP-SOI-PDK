# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

"""从本地白盒 GDS 导出可随源码仓库分发的固定黑盒 GDS。"""

import argparse
from pathlib import Path

import pya

from package_blackbox_pdk import LIBRARY_DBU, _draw_blackbox_cell


def export_blackbox_gds(source, output):
    """复用黑盒生成逻辑；仅创建新目录，避免覆盖已有器件。"""
    source = Path(source).resolve()
    output = Path(output).resolve()
    files = sorted(source.glob("*.gds"))
    if not files:
        raise RuntimeError("源目录没有固定器件 GDS：%s" % source)
    output.mkdir(parents=True, exist_ok=False)
    cell_count = 0
    for path in files:
        original = pya.Layout()
        original.read(str(path))
        blackbox = pya.Layout()
        blackbox.dbu = LIBRARY_DBU
        for top in original.each_top_cell():
            cell = original.cell(top) if isinstance(top, int) else top
            if cell.bbox().empty():
                raise RuntimeError("源器件为空：%s / %s" % (path.name, cell.name))
            _draw_blackbox_cell(cell, original, blackbox)
            cell_count += 1
        blackbox.write(str(output / path.name))
    print("已导出 %d 个 GDS、%d 个黑盒器件：%s" % (len(files), cell_count, output))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="本地固定白盒 GDS 目录")
    parser.add_argument("--output", required=True, type=Path, help="尚不存在的黑盒输出目录")
    args = parser.parse_args()
    export_blackbox_gds(args.source, args.output)
