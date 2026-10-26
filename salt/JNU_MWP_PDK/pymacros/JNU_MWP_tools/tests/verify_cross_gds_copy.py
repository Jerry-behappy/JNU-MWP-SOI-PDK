# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""实际经过 GUI 深复制粘贴，验证上下文式旧波导和库 PCell 不变空。"""

from collections import Counter
from pathlib import Path
import sys
import tempfile

import pya

PYMACROS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PYMACROS))

from JNU_MWP_tools.core import internal_waveguide_registry as registry
from JNU_MWP_tools.core.pcell_geometry import layout_geometry_equal, cell_geometry_equal
from JNU_MWP_tools.release.repair_cross_gds_layout import repair_file


def _value(obj, name):
    value = getattr(obj, name)
    return value() if callable(value) else value


def _flush():
    dialog = pya.QDialog()
    timer = pya.QTimer(dialog)
    timer.setSingleShot(True)
    timer.timeout(dialog.accept)
    timer.start(30)
    dialog.exec_()


def _fixture(path):
    from JNU_MWP_pcells.taper import Taper
    from JNU_MWP_pcells.straight_waveguide import StraightWaveguide

    layout = pya.Layout()
    layout.dbu = 0.001
    registry.ensure_internal_waveguide_pcells(layout)
    waveguide = layout.create_cell("Waveguide", {
        "path": pya.DPath([pya.DPoint(0, 0), pya.DPoint(80, 0), pya.DPoint(80, 80)], 0.5),
        "width": 0.5, "radius": 20.0, "bend_type": "Circular",
    })
    waveguide.name = "RENAMED_LEGACY_ROUTE"
    for key in list(waveguide.properties()):
        waveguide.delete_property(key)
    layout.register_pcell("OLD_LOCAL_TAPER", Taper())
    taper = layout.create_cell("OLD_LOCAL_TAPER", {"length": 20.0, "width1": 0.5, "width2": 2.0})
    taper.set_property("user_note", "keep this cell property")
    layout.register_pcell("OLD_LOCAL_STRAIGHT", StraightWaveguide())
    straight = layout.create_cell("OLD_LOCAL_STRAIGHT", {"length": 50.0, "width": 0.5})
    class Unavailable(pya.PCellDeclarationHelper):
        def __init__(self):
            super().__init__()
            self.param("size", self.TypeInt, "Size", default=2000)

        def produce_impl(self):
            self.cell.shapes(self.layout.layer(1, 0)).insert(pya.Box(0, 0, self.size, self.size))

    layout.register_pcell("UNAVAILABLE_LOCAL_CELL", Unavailable())
    unavailable = layout.create_cell("UNAVAILABLE_LOCAL_CELL", {})
    top = layout.create_cell("LEGACY_COPY_TOP")
    for index, cell in enumerate((waveguide, taper, straight, unavailable)):
        instance = top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans(index * 100000, 0)))
        instance.set_property("design_tag", index)
    layout.write(str(path))


def _parameter_key(cell):
    return (cell.basic_name(), tuple(sorted((key, str(value)) for key, value in cell.pcell_parameters_by_name().items()
                                           if key != "name_suffix")))


def verify_clipboard_file(path, copied_output=None):
    """原生复制整个层级到全新 Layout，逐 cell 核对图形、层级和参数。"""
    window = pya.Application.instance().main_window()
    registry.install_internal_waveguide_registration(window)
    source_cv = window.load_layout(str(path), 1)
    _flush()
    source = source_cv.layout()
    assert not any(cell.is_cold_proxy() for cell in source.each_cell())
    top = source.top_cell()
    holder = source.create_cell("__CLIPBOARD_SOURCE_HOLDER")
    instance = holder.insert(pya.CellInstArray(top.cell_index(), pya.Trans()))
    source_cv.cell = holder
    view = window.current_view()
    selected = pya.ObjectInstPath()
    selected.top = holder.cell_index()
    selected.cv_index = _value(view, "active_cellview_index")
    selected.append_path(pya.InstElement(instance))
    view.object_selection = [selected]
    errors = []

    def accept_deep_copy():
        dialog = pya.QApplication.activeModalWidget()
        if dialog is None:
            return
        if str(dialog.windowTitle) != "Copy Options":
            errors.append(str(dialog.windowTitle))
            dialog.close()
            return

        def children(obj):
            return [obj] + [descendant for child in obj.children() for descendant in children(child)]

        next(child for child in children(dialog) if hasattr(child, "text")
             and str(child.text).startswith("Deep copy")).setChecked(True)
        dialog.accept()

    timer = pya.QTimer(window)
    timer.timeout(accept_deep_copy)
    timer.start(10)
    try:
        window.cm_copy()
        target_cv = window.create_layout(1)
        target = target_cv.layout()
        target.dbu = source.dbu
        # 不等待轮询 timer，空版图必须在创建返回时就已经可以接受粘贴。
        assert target.pcell_declaration("Waveguide") is not None
        target_top = target.create_cell("CLIPBOARD_TARGET")
        target_cv.cell = target_top
        window.cm_paste()
    finally:
        timer.stop()
        timer.deleteLater()
    assert not errors, errors
    assert len(list(target_top.each_inst())) == 1
    assert not any(cell.is_empty() or cell.is_cold_proxy() for cell in target.each_cell())
    names = {holder.name: target_top.name}
    variants = {_parameter_key(cell): cell for cell in target.each_cell() if cell.is_pcell_variant()}
    for cell in source.each_cell():
        if cell.is_pcell_variant():
            matched = variants.get(_parameter_key(cell))
            assert matched is not None, cell.name
            names[cell.name] = matched.name
    assert layout_geometry_equal(source, target, names)
    if copied_output:
        options = pya.SaveLayoutOptions()
        options.set_format_from_filename(str(copied_output))
        options.gds2_write_cell_properties = True
        target.write(str(copied_output), options)
        saved = pya.Layout()
        registry.ensure_internal_waveguide_pcells(saved)
        saved.read(str(copied_output))
        assert layout_geometry_equal(target, saved)
        assert not any(cell.is_cold_proxy() for cell in saved.each_cell())
    return {"source_cells": source.cells() - 1, "copied_cells": target.cells() - 1,
            "empty_cells": 0, "cold_proxies": 0, "all_geometry_and_hierarchy_equal": True,
            "pcells": dict(Counter(cell.basic_name() for cell in target.each_cell() if cell.is_pcell_variant()))}


def main():
    with tempfile.TemporaryDirectory(prefix="jnu_cross_gds_") as directory:
        directory = Path(directory)
        source, repaired = directory / "legacy.gds", directory / "portable.gds"
        _fixture(source)
        raw = pya.Layout()
        raw.read(str(source))
        assert registry._has_unrecognized_waveguides(raw)
        assert not raw.cell("RENAMED_LEGACY_ROUTE").properties()
        # 缓存已被更改时不允许以当前实现覆盖，等价性检查必须能拒绝差异。
        first, second = pya.Layout(), pya.Layout()
        a, b = first.create_cell("TEST"), second.create_cell("TEST")
        a.shapes(first.layer(1, 0)).insert(pya.Box(0, 0, 100, 100))
        b.shapes(second.layer(1, 0)).insert(pya.Box(0, 0, 100, 101))
        assert not cell_geometry_equal(a, b)
        window = pya.Application.instance().main_window()
        registry.install_internal_waveguide_registration(window)
        cv = window.load_layout(str(source), 1)
        _flush()
        assert cv.layout().cell("RENAMED_LEGACY_ROUTE") is None
        waves = [cell for cell in cv.layout().each_cell() if cell.is_pcell_variant()]
        assert len(waves) == 1 and waves[0].basic_name() == "Waveguide"
        report = repair_file(source, repaired)
        assert report["restored_count"] == 3 and report["static_count"] == 1, report
        copied = verify_clipboard_file(repaired, directory / "copied.gds")
        assert copied["pcells"] == {"Waveguide": 1, "Pcell_Taper": 1, "Pcell_Straight_Waveguide": 1}, copied
    print("PASS: context-only legacy recovery, exact geometry gate, native cross-GDS paste and reopened PCells", flush=True)


if __name__ == "__main__":
    main()
