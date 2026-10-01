# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""构建一次隔离黑盒交付目录并重读全部器件与源码排除项。"""

import os
from collections import Counter
from pathlib import Path
import sys

import pya


PYMACROS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PYMACROS))
from JNU_MWP_tools.release.package_blackbox_pdk import package_blackbox_pdk
from JNU_MWP_tools.core.public_ebeam_cells import PUBLIC_EBEAM_CELLS


def _ports(cell, layout):
    """读取物理端口中心、宽度、方向及端口名，覆盖子 cell。"""
    paths = []
    texts = []
    iterator = cell.begin_shapes_rec(layout.layer(1, 10))
    while not iterator.at_end():
        shape = iterator.shape()
        transform = iterator.itrans()
        if shape.is_path():
            path = shape.path.transformed(transform)
            points = list(path.each_point())
            first, last = points[0], points[-1]
            paths.append((((first.x + last.x) * layout.dbu / 2),
                          ((first.y + last.y) * layout.dbu / 2),
                          path.width * layout.dbu,
                          (last.x > first.x) - (last.x < first.x),
                          (last.y > first.y) - (last.y < first.y)))
        elif shape.is_text():
            texts.append(shape.text.string)
        iterator.next()
    return paths, Counter(texts)


def _verify_source_ports(source_dir, blackbox_dir):
    mapping = dict(PUBLIC_EBEAM_CELLS)
    files = sorted(source_dir.glob("*.gds"))
    assert len(files) == 29, len(files)
    for path in files:
        source = pya.Layout()
        source.read(str(path))
        top = list(source.each_top_cell())
        assert len(top) == 1, path.name
        original = source.cell(top[0]) if isinstance(top[0], int) else top[0]
        target_name = mapping.get(path.stem, original.name)
        output_name = mapping.get(path.stem, path.stem) + ".gds"
        blackbox = pya.Layout()
        blackbox.read(str(blackbox_dir / output_name))
        result = blackbox.cell(target_name)
        assert result is not None, target_name
        source_paths, source_texts = _ports(original, source)
        box_paths, box_texts = _ports(result, blackbox)
        assert len(source_paths) == len(box_paths), target_name
        assert source_texts == box_texts, target_name
        remaining = box_paths[:]
        for x, y, width, dx, dy in source_paths:
            match = next((index for index, (bx, by, bw, bdx, bdy) in enumerate(remaining)
                          if abs(x - bx) <= 0.001 and abs(y - by) <= 0.001
                          and abs(width - bw) <= 0.001 and (dx, dy) == (bdx, bdy)), None)
            assert match is not None, (target_name, x, y, width, dx, dy)
            remaining.pop(match)


def main():
    output = Path(os.environ["JNU_BLACKBOX_TEST_OUTPUT"])
    assert not output.exists(), "测试包目录必须为新目录"
    count, package, _ = package_blackbox_pdk(output)
    assert count == 29, count
    macros = package / "pymacros"
    assert not (macros / "JNU_MWP_pcells").exists()
    assert not (macros / "JNU_MWP_gds").exists()
    assert not (macros / "JNULib.py").exists()
    assert not (macros / "JNU_MWP_tools" / "release").exists()
    assert (package / "LICENSE.md").is_file()
    assert (macros / "JNU_MWP_blackbox_gds" / "NOTICE.md").is_file()
    names = set()
    for path in sorted((macros / "JNU_MWP_blackbox_gds").glob("*.gds")):
        layout = pya.Layout()
        layout.read(str(path))
        for top in layout.each_top_cell():
            cell = layout.cell(top) if isinstance(top, int) else top
            assert cell.name not in names, cell.name
            names.add(cell.name)
            si = list(cell.shapes(layout.layer(1, 0)).each())
            assert len(si) == 1 and si[0].is_box(), cell.name
    assert len(names) == 29, len(names)
    assert {"Crossing4", "1310_TE_Terminator", "1550_TE_Terminator",
            "1310_Ybranch", "1550_Ybranch"} <= names
    assert not any(name.startswith("Pcell_") for name in names)
    assert not {"ebeam_crossing4", "ebeam_terminator_te1310", "ebeam_terminator_te1550",
                "ebeam_y_1310", "ebeam_y_1550"} & names
    if os.environ.get("JNU_WHITEBOX_GDS_DIR"):
        _verify_source_ports(Path(os.environ["JNU_WHITEBOX_GDS_DIR"]),
                             macros / "JNU_MWP_blackbox_gds")
    print("PASS: 29 fixed blackbox cells in standalone package; no whitebox GDS or PCell source.")


if __name__ == "__main__":
    main()
