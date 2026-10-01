# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""在真实 GUI 文件打开流程中检查外部 GDS 的内部波导 PCell。"""

import json
import os
from pathlib import Path
import sys
import traceback

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

from JNU_MWP_tools.core.internal_waveguide_registry import ensure_internal_waveguide_pcells  # noqa: E402


SOURCE = Path(os.environ["JNU_WAVEGUIDE_GUI_GDS"])
REPORT = Path(os.environ["JNU_WAVEGUIDE_GUI_REPORT"])


def waveguide_names(layout):
    cells = [cell for cell in layout.each_cell()
             if str(cell.name).startswith(("Waveguide", "Composite_Waveguide"))]
    assert cells, "GDS 中没有内部波导 cell"
    for cell in cells:
        assert cell.is_pcell_variant(), "波导被读成普通 cell：%s" % cell.name
        declaration = cell.pcell_declaration()
        assert declaration is not None and declaration.name() in ("Waveguide", "Composite_Waveguide")
        assert cell.name not in ("Waveguide", "Composite_Waveguide"), cell.name
    return sorted(str(cell.name) for cell in cells)


baseline = pya.Layout()
ensure_internal_waveguide_pcells(baseline)
baseline.read(str(SOURCE))
ensure_internal_waveguide_pcells(baseline)
expected_names = waveguide_names(baseline)
expected_top = baseline.top_cell()
expected_bbox = expected_top.bbox().to_s()
expected_instances = sum(1 for _ in expected_top.each_inst())

app = pya.Application.instance()
window = app.main_window()


def finish():
    try:
        cellview = window.current_view().active_cellview()
        layout = cellview.layout()
        top = layout.top_cell()
        actual_names = waveguide_names(layout)
        assert actual_names == expected_names, (actual_names, expected_names)
        assert top.name == expected_top.name
        assert top.bbox().to_s() == expected_bbox
        assert sum(1 for _ in top.each_inst()) == expected_instances
        REPORT.write_text(json.dumps({
            "status": "PASS",
            "source": str(SOURCE),
            "top": str(top.name),
            "top_instances": expected_instances,
            "bbox": expected_bbox,
            "waveguide_pcells": actual_names,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print("PASS: GUI 打开外部 GDS 后全部波导保持参数名与 PCell 身份")
    except Exception:
        traceback.print_exc()
        app.exit(1)
    else:
        app.exit(0)


window.load_layout(str(SOURCE), 1)
timer = pya.QTimer()
timer.setSingleShot(True)
timer.timeout(finish)
timer.start(750)
