# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""仅安装黑盒交付包时，核验五个新增固定 cell 的冷启动可用性。"""

import json
import os
from pathlib import Path
import traceback

import pya


def _probe():
    assert pya.Technology.has_technology("JNU_MWP_PDK")
    assert pya.Library.library_by_name("EBeam") is None
    assert pya.Library.library_by_name("JNULib") is None
    black = pya.Library.library_by_name("JNULib_BlackBox")
    assert black is not None and "v1.2" in black.description
    assert not list(black.layout().pcell_names())
    names = {
        "Crossing4", "1310_TE_Terminator", "1550_TE_Terminator",
        "1310_Ybranch", "1550_Ybranch",
    }
    for old_name in ("ebeam_crossing4", "ebeam_terminator_te1310",
                     "ebeam_terminator_te1550", "ebeam_y_1310", "ebeam_y_1550"):
        assert black.layout().cell(old_name) is None
    assert len(list(black.layout().each_top_cell())) == 29
    assert black.layout().cell("Pcell_Waveguide_Bump") is None
    for name in names:
        layout = pya.Layout()
        cell = layout.create_cell(name, "JNULib_BlackBox")
        assert cell and not cell.is_pcell_variant()
        assert not cell.bbox(layout.layer(1, 0)).empty()
    Path(os.environ["JNU_BLACKBOX_COLD_REPORT"]).write_text(
        json.dumps({"count": 29, "new_devices": sorted(names), "ebeam_installed": False},
                   indent=2), encoding="utf-8")
    print("JNU_BLACKBOX_COLD_START_OK")


def _finish():
    try:
        _probe()
    except Exception:
        traceback.print_exc()
        pya.Application.instance().exit(1)
    else:
        pya.Application.instance().exit(0)


pya.Application.instance().main_window().create_layout("JNU_MWP_PDK", 1)
_timer = pya.QTimer()
_timer.setSingleShot(True)
_timer.timeout(_finish)
_timer.start(200)
