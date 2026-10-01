# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""从独立 Library 仓库的全部固定白盒 GDS 同步公开黑盒。"""

import argparse
import os
from pathlib import Path
import sys
import tempfile

import pya


PYMACROS = Path(__file__).resolve().parents[2]
if str(PYMACROS) not in sys.path:
    sys.path.insert(0, str(PYMACROS))

from JNU_MWP_tools.core.public_ebeam_cells import PUBLIC_EBEAM_CELLS
from JNU_MWP_tools.release.package_blackbox_pdk import LIBRARY_DBU, _draw_blackbox_cell


SOURCE_NAMES = dict(PUBLIC_EBEAM_CELLS)


def _write_blackbox(cell, source_layout, destination, target_name=None):
    blackbox = pya.Layout()
    blackbox.dbu = LIBRARY_DBU
    _draw_blackbox_cell(cell, source_layout, blackbox, target_name=target_name)
    blackbox.write(str(destination))


def _gds_records_without_dates(path):
    """忽略 GDS 写出时间，仅比较版图记录内容。"""
    data = Path(path).read_bytes()
    records = []
    offset = 0
    while offset < len(data):
        if offset + 4 > len(data):
            raise RuntimeError("GDS 记录不完整：%s" % path)
        length = int.from_bytes(data[offset:offset + 2], "big")
        if length < 4 or offset + length > len(data):
            raise RuntimeError("GDS 记录长度无效：%s" % path)
        record = data[offset:offset + length]
        if record[2] in (1, 5) and length == 28:
            record = record[:4]
        records.append(record)
        offset += length
    return records


def sync_blackboxes(source, output=PYMACROS / "JNU_MWP_blackbox_gds"):
    """完整生成后更新有变化的黑盒，避免不完整白盒目录覆盖发布数据。"""
    source = Path(source).resolve()
    output = Path(output).resolve()
    if not source.is_dir() or not output.is_dir():
        raise FileNotFoundError("白盒源目录或黑盒输出目录不存在：%s / %s" % (source, output))
    source_files = sorted(path for path in source.glob("*.gds")
                          if not path.stem.startswith("Pcell_"))
    if len(source_files) < 29 or not all((source / (name + ".gds")).is_file()
                                           for name in SOURCE_NAMES):
        raise RuntimeError("独立器件库白盒不完整，至少需要现有 29 个 GDS（含五个 EBeam）：%s" % source)

    with tempfile.TemporaryDirectory(prefix="jnu-blackbox-sync-", dir=output.parent) as temporary:
        staged = Path(temporary)
        target_names = set()
        output_names = set()
        for path in source_files:
            layout = pya.Layout()
            layout.read(str(path))
            tops = list(layout.each_top_cell())
            if len(tops) != 1:
                raise RuntimeError("白盒 GDS 顶层 cell 数量应为 1：%s" % path)
            cell = layout.cell(tops[0]) if isinstance(tops[0], int) else tops[0]
            if cell.name.startswith("Pcell_"):
                continue
            if cell.bbox().empty() or (path.stem in SOURCE_NAMES and cell.name != path.stem):
                raise RuntimeError("白盒 GDS 源名称错误或器件为空：%s / %s" % (path, cell.name))
            target_name = SOURCE_NAMES.get(path.stem, cell.name)
            output_name = (SOURCE_NAMES.get(path.stem, path.stem) + ".gds")
            if target_name in target_names or output_name in output_names:
                raise RuntimeError("黑盒器件或文件重名：%s / %s" % (target_name, output_name))
            target_names.add(target_name)
            output_names.add(output_name)
            _write_blackbox(cell, layout, staged / output_name, target_name=target_name)
        if len(target_names) < 29:
            raise RuntimeError("独立器件库中固定白盒不足 29 个：%s" % source)

        changed = []
        for path in sorted(staged.glob("*.gds")):
            target = output / path.name
            if not target.is_file() or _gds_records_without_dates(path) != _gds_records_without_dates(target):
                os.replace(path, target)
                changed.append(path.name)
        obsolete = []
        for path in output.glob("*.gds"):
            if path.name not in output_names:
                path.unlink()
                obsolete.append(path.name)
    print("已同步 %d 个固定黑盒；更新 %d 个，移除 %d 个。" %
          (len(target_names), len(changed), len(obsolete)))
    return len(target_names), changed, obsolete


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=os.environ.get("JNU_WHITEBOX_GDS_DIR"),
                        help="JNU-MWP-SOI-Library/JNU_MWP_gds 完整白盒目录")
    parser.add_argument("--output", type=Path, default=PYMACROS / "JNU_MWP_blackbox_gds")
    args = parser.parse_args()
    if args.source is None:
        parser.error("必须通过 --source 或 JNU_WHITEBOX_GDS_DIR 指定独立 Library 白盒目录")
    sync_blackboxes(args.source, args.output)
