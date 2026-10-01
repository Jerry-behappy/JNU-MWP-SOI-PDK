# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""从公开 EBeam GDS 和 JNU 原生 bump 生成六个可追溯的固定黑盒。"""

import sys
from pathlib import Path

import pya


PYMACROS = Path(__file__).resolve().parents[2]
if str(PYMACROS) not in sys.path:
    sys.path.insert(0, str(PYMACROS))

from JNU_MWP_pcells.waveguide_bump import WaveguideBump
from JNU_MWP_tools.release.package_blackbox_pdk import LIBRARY_DBU, _draw_blackbox_cell


FIXED_NAMES = (
    "ebeam_crossing4", "ebeam_terminator_te1310", "ebeam_terminator_te1550",
    "ebeam_y_1310", "ebeam_y_1550",
)
BUMP_NAME = "Pcell_Waveguide_Bump"


def _write_one(src_cell, src_layout, output, name):
    blackbox = pya.Layout()
    blackbox.dbu = LIBRARY_DBU
    _draw_blackbox_cell(src_cell, src_layout, blackbox, target_name=name)
    blackbox.write(str(output / (name + ".gds")))


def update_public_ebeam_blackboxes():
    source = PYMACROS / "JNU_MWP_ebeam_gds"
    output = PYMACROS / "JNU_MWP_blackbox_gds"
    for name in FIXED_NAMES:
        layout = pya.Layout()
        layout.read(str(source / (name + ".gds")))
        cell = layout.cell(name)
        if cell is None:
            raise RuntimeError("源 GDS 缺少器件：%s" % name)
        _write_one(cell, layout, output, name)

    layout = pya.Layout()
    layout.dbu = LIBRARY_DBU
    layout.register_pcell(BUMP_NAME, WaveguideBump())
    declaration = layout.pcell_declaration(BUMP_NAME)
    parameters = list(declaration.get_parameters())
    values = [parameter.default for parameter in parameters]
    defaults = {"delta_length": 0.2, "width": 0.5, "radius": 20.0, "max_theta": 149.0}
    for index, parameter in enumerate(parameters):
        if parameter.name in defaults:
            values[index] = defaults[parameter.name]
    bump = layout.cell(layout.add_pcell_variant(layout.pcell_id(BUMP_NAME), values))
    if bump is None or bump.bbox().empty():
        raise RuntimeError("无法生成 bump 默认 PCell")
    _write_one(bump, layout, output, BUMP_NAME)
    print("已更新 6 个公开器件黑盒：%s" % output)


if __name__ == "__main__":
    update_public_ebeam_blackboxes()
