# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""验证 Path to Waveguide 的直接 PCell 层级、参数化命名和 GDS 往返。"""

import os
from pathlib import Path
import sys
import tempfile

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

from JNU_MWP_tools.actions.path_to_waveguide import (  # noqa: E402
    _create_waveguide_cell,
    _mark_waveguide,
    _normalize_dpath_to_origin,
    _store_waveguide_recovery_property,
)
from JNU_MWP_tools.actions.waveguide_to_path import (  # noqa: E402
    _is_waveguide_cell,
    _path_from_waveguide_cell,
)
from JNU_MWP_tools.core.common import SI_LAYER  # noqa: E402
from JNU_MWP_tools.core.internal_waveguide_registry import (  # noqa: E402
    ensure_internal_waveguide_pcells,
)


DBU = 0.001


def _path_points(path):
    return [(point.x, point.y) for point in path.each_point()]


def _params(mode):
    if mode == "composite":
        return {
            "mode": "composite",
            "straight_width": 2.0,
            "start_width": 2.0,
            "end_width": 2.0,
            "bend_width": 0.5,
            "taper_length": 20.0,
            "transition_length": 2.0,
            "radius": 30.0,
            "bend_type": "Bezier",
            "bezier": 0.3,
            "Euler_Rmax": 30.0,
            "Euler_Rmin": 10.0,
        }
    return {
        "mode": "single",
        "width": 0.5,
        "radius": 20.0,
        "bend_type": "Bezier",
        "bezier": 0.35,
        "Euler_Rmax": 30.0,
        "Euler_Rmin": 10.0,
    }


def _insert_waveguide(layout, parent, source_dpath, params, index):
    local_dpath, placement = _normalize_dpath_to_origin(source_dpath, layout.dbu)
    if local_dpath is None or placement is None:
        raise RuntimeError("Path 归一化失败。")
    waveguide_cell = _create_waveguide_cell(layout, local_dpath, params, index)
    instance = parent.insert(pya.CellInstArray(waveguide_cell.cell_index(), placement))
    _store_waveguide_recovery_property(instance, local_dpath)
    _mark_waveguide(instance, params["mode"])
    return instance


def _write_and_reread(layout):
    output = Path(tempfile.gettempdir()) / "jnu_waveguide_hierarchy_regression.gds"
    try:
        options = pya.SaveLayoutOptions()
        options.set_format_from_filename(str(output))
        options.gds2_write_cell_properties = True
        options.write_context_info = True
        layout.write(str(output), options)
        reread = pya.Layout()
        ensure_internal_waveguide_pcells(reread)
        reread.read(str(output))
        return reread
    finally:
        try:
            os.remove(str(output))
        except OSError:
            pass


def main():
    layout = pya.Layout()
    layout.dbu = DBU
    ensure_internal_waveguide_pcells(layout)
    top = layout.create_cell("JNU_WAVEGUIDE_HIERARCHY_REGRESSION")

    source_paths = [
        ("single", pya.DPath([
            pya.DPoint(0, 0), pya.DPoint(80, 0), pya.DPoint(80, 80),
        ], 0.5)),
        ("single", pya.DPath([
            pya.DPoint(200, 0), pya.DPoint(280, 0), pya.DPoint(280, 80),
        ], 0.5)),
        ("single", pya.DPath([
            pya.DPoint(400, 0), pya.DPoint(400, 80), pya.DPoint(480, 80),
        ], 0.5)),
        ("composite", pya.DPath([
            pya.DPoint(0, 300), pya.DPoint(160, 300), pya.DPoint(160, 460),
        ], 2.0)),
    ]
    inserted = [
        _insert_waveguide(layout, top, source, _params(mode), index)
        for index, (mode, source) in enumerate(source_paths, 1)
    ]

    direct_instances = list(top.each_inst())
    if len(direct_instances) != len(source_paths):
        raise RuntimeError("父 cell 未直接保留全部真实 Waveguide PCell 实例。")
    if any(instance.cell.name.startswith("__JNU_P2W_") for instance in direct_instances):
        raise RuntimeError("Path to Waveguide 不应再生成中间容器。")
    names = [instance.cell.name for instance in direct_instances]
    if any("$" in name or name.startswith("JNU_WG_") for name in names):
        raise RuntimeError("内部波导名称仍使用自动序号或哈希名称：%s" % names)
    if inserted[0].cell_index == inserted[1].cell_index:
        pass
    else:
        raise RuntimeError("平移后的相同路径未复用同一 PCell variant。")
    if not names[2].endswith("__002"):
        raise RuntimeError("同名不同路径未追加 __002 后缀：%s" % names[2])
    if not all(instance.cell.is_pcell_variant() for instance in direct_instances):
        raise RuntimeError("直接子实例中存在非 PCell 波导。")

    expected_region = pya.Region(top.begin_shapes_rec(layout.layer(SI_LAYER))).merged()
    reread = _write_and_reread(layout)
    reread_top = reread.cell("JNU_WAVEGUIDE_HIERARCHY_REGRESSION")
    reread_instances = list(reread_top.each_inst())
    reread_names = [instance.cell.name for instance in reread_instances]
    if len(reread_instances) != len(source_paths):
        raise RuntimeError("GDS 重读后直接实例数量发生变化。")
    if any("$" in name or name.startswith("JNU_WG_") for name in reread_names):
        raise RuntimeError("GDS 重读后波导名称不稳定：%s" % reread_names)
    if not all(instance.cell.is_pcell_variant() for instance in reread_instances):
        raise RuntimeError("GDS 重读前注册声明后仍未恢复真实 PCell。")

    restored_paths = []
    for instance in reread_instances:
        if not _is_waveguide_cell(instance.cell):
            raise RuntimeError("GDS 重读后实例未被识别为 Waveguide。")
        restored = _path_from_waveguide_cell(instance.cell, reread, instance)
        if restored is None:
            raise RuntimeError("GDS 重读后无法恢复原始 Manhattan Path。")
        restored_paths.append(_path_points(restored.transformed(instance.cplx_trans)))
    expected_paths = [
        [(int(round(point.x / DBU)), int(round(point.y / DBU))) for point in source.each_point()]
        for _mode, source in source_paths
    ]
    if restored_paths != expected_paths:
        raise RuntimeError("恢复后的 Path 点列错误：%s != %s" % (restored_paths, expected_paths))

    reread_region = pya.Region(reread_top.begin_shapes_rec(reread.layer(SI_LAYER))).merged()
    if not (expected_region ^ reread_region).is_empty():
        raise RuntimeError("GDS 重读后 Si Polygon 几何发生变化。")

    print("OK: direct Waveguide PCells, parameterized names, GDS roundtrip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
