# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""验证 GUI 首次打开含裸名副本的 GDS 时恢复内部 PCell，并可再次保存重读。"""

from pathlib import Path
import sys
import tempfile
import traceback

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

from JNU_MWP_tools.core.internal_waveguide_registry import ensure_internal_waveguide_pcells  # noqa: E402


def _make_source(path):
    layout = pya.Layout()
    layout.dbu = 0.001
    ensure_internal_waveguide_pcells(layout)
    declaration = layout.pcell_declaration("Waveguide")
    values = [parameter.default for parameter in declaration.get_parameters()]
    overrides = {
        "path": pya.DPath([
            pya.DPoint(0, 0), pya.DPoint(80, 0), pya.DPoint(80, 60),
        ], 0.35),
        "width": 0.35,
        "radius": 20.0,
        "bend_type": "Bezier",
        "bezier_k": 0.35,
    }
    for index, parameter in enumerate(declaration.get_parameters()):
        if parameter.name in overrides:
            values[index] = overrides[parameter.name]
    source = layout.cell(layout.add_pcell_variant(layout.pcell_id("Waveguide"), values))
    top = layout.create_cell("GUI_COPY_TOP")
    top.insert(pya.CellInstArray(source.cell_index(), pya.Trans()))
    copied = top.insert(pya.CellInstArray(source.cell_index(), pya.Trans(100000, 0)))
    copied.change_pcell_parameter("path", pya.DPath([
        pya.DPoint(0, 0), pya.DPoint(0, 80), pya.DPoint(-60, 80),
    ], 0.35))
    assert copied.cell_index != source.cell_index()
    copied.cell.name = "Waveguide"
    options = pya.SaveLayoutOptions()
    options.set_format_from_filename(str(path))
    options.gds2_write_cell_properties = True
    options.write_context_info = True
    layout.write(str(path), options)
    return top.bbox().to_s()


def _waveguide_instances(layout, expected_count=2):
    top = layout.cell("GUI_COPY_TOP")
    assert top is not None
    instances = list(top.each_inst())
    assert len(instances) == expected_count
    for instance in instances:
        cell = instance.cell
        assert cell.is_pcell_variant(), "GUI 首开 GDS 后波导仍是普通 cell：%s" % cell.name
        assert cell.pcell_declaration().name() == "Waveguide"
        assert cell.name.startswith("Waveguide_w") and cell.name != "Waveguide", cell.name
    return top.bbox().to_s()


def main():
    temporary = tempfile.TemporaryDirectory(prefix="jnu_gui_waveguide_open_")
    directory = Path(temporary.name)
    source = directory / "copied.gds"
    saved = directory / "saved_again.gds"
    original_bbox = _make_source(source)

    def finish():
        try:
            view = pya.Application.instance().main_window().current_view()
            assert view.active_cellview().cell.name == "GUI_COPY_TOP"
            layout = view.active_cellview().layout()
            assert _waveguide_instances(layout) == original_bbox
            assert layout.cell("Waveguide") is None
            top = layout.cell("GUI_COPY_TOP")
            source = list(top.each_inst())[0]
            copied = top.insert(pya.CellInstArray(source.cell_index, pya.Trans(200000, 0)))
            copied.change_pcell_parameter("path", pya.DPath([
                pya.DPoint(0, 0), pya.DPoint(80, 0), pya.DPoint(80, -60),
            ], 0.35))
            assert copied.cell.name.startswith("Waveguide_w")
            expected_bbox = _waveguide_instances(layout, 3)
            layout.write(str(saved))
            reread = pya.Layout()
            ensure_internal_waveguide_pcells(reread)
            reread.read(str(saved))
            ensure_internal_waveguide_pcells(reread)
            assert _waveguide_instances(reread, 3) == expected_bbox
            assert reread.cell("Waveguide") is None
            print("PASS: GUI first-open, copied PCell naming, save and reopen")
        except Exception:
            traceback.print_exc()
            pya.Application.instance().exit(1)
        else:
            pya.Application.instance().exit(0)
        finally:
            temporary.cleanup()

    window = pya.Application.instance().main_window()
    window.load_layout(str(source), 1)
    timer = pya.QTimer()
    timer.setSingleShot(True)
    timer.timeout(finish)
    timer.start(400)
    return timer


if __name__ == "__main__":
    timer = main()
