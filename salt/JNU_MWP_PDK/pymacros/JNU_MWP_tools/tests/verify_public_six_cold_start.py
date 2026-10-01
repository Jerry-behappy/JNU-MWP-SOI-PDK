# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""在隔离 KLayout GUI 冷启动后核验公开六器件与语言标签。"""

import json
import os
from pathlib import Path
import traceback

import pya


def _probe():
    assert pya.Technology.has_technology("JNU_MWP_PDK")
    assert pya.Library.library_by_name("EBeam") is None, "隔离环境意外加载 EBeam"
    white = pya.Library.library_by_name("JNULib")
    black = pya.Library.library_by_name("JNULib_BlackBox")
    assert white and black, "公开器件库未自动加载"
    assert "v1.2" in white.description and "v1.2" in black.description

    names = (
        "Crossing4", "1310_TE_Terminator", "1550_TE_Terminator",
        "1310_Ybranch", "1550_Ybranch", "Pcell_Waveguide_Bump",
    )
    for old_name in ("ebeam_crossing4", "ebeam_terminator_te1310",
                     "ebeam_terminator_te1550", "ebeam_y_1310", "ebeam_y_1550"):
        assert white.layout().cell(old_name) is None and black.layout().cell(old_name) is None
    assert len(list(black.layout().each_top_cell())) == 30
    assert not list(black.layout().pcell_names())
    for name in names:
        assert white.layout().cell(name) if name != "Pcell_Waveguide_Bump" else \
            name in set(white.layout().pcell_names()), name
        assert black.layout().cell(name), name
        target = pya.Layout()
        cell = target.create_cell(name, "JNULib_BlackBox")
        assert cell and not cell.bbox(target.layer(1, 0)).empty(), name
        if name != "Pcell_Waveguide_Bump":
            source = target.create_cell(name, "JNULib")
        else:
            source = target.create_cell(name, "JNULib", {"delta_length": 0.2})
            assert source.is_pcell_variant()
        assert source and not source.bbox(target.layer(1, 0)).empty(), name

    declaration = white.layout().pcell_declaration("Pcell_Waveguide_Bump")
    labels = {parameter.name: parameter.description for parameter in declaration.get_parameters()}
    chinese = os.environ.get("JNU_SIX_EXPECT_ZH") == "1"
    assert labels["delta_length"] == ("增量长度" if chinese else "Incremental length")
    assert labels["radius"] == ("有效弯曲半径" if chinese else "Effective bend radius")
    assert labels["max_theta"] == ("最大弯曲角度" if chinese else "Maximum angle")
    result = {"whitebox": list(names), "blackbox_count": 30,
              "language": "zh_CN" if chinese else "en", "ebeam_installed": False}
    Path(os.environ["JNU_SIX_REPORT"]).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("JNU_SIX_COLD_START_OK")


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
