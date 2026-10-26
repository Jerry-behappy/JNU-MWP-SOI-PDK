# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""验证输出层下拉框、三页签转换、同路径异层身份及 GDS 重读。"""

import builtins
from pathlib import Path
import sys
import tempfile

import pya

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from JNU_MWP_tools.actions import path_to_waveguide as tool
from JNU_MWP_tools.actions import waveguide_to_path as reverse_tool
from JNU_MWP_tools.core import ui_language
from JNU_MWP_tools.core.common import _value
from JNU_MWP_tools.core.internal_waveguide_registry import ensure_internal_waveguide_pcells


def main():
    window = pya.Application.instance().main_window()
    cv = window.create_layout(1)
    layout = cv.layout()
    layout.dbu = 0.001
    top = layout.create_cell("OUTPUT_LAYER_TEST")
    cv.cell = top
    view = window.current_view()
    layout.layer(pya.LayerInfo(42, 7, "Custom core"))
    original_file, original_message = tool._waveguide_params_file, tool._message
    original_language = getattr(builtins, ui_language._SESSION_KEY, None)
    failures, messages = [], []
    with tempfile.TemporaryDirectory(prefix="jnu-output-layer-") as directory:
        tool._waveguide_params_file = lambda: str(Path(directory) / "settings.json")
        tool._message = lambda title, text: messages.append(text)
        try:
            settings = tool._default_waveguide_params()
            assert settings["waveguide_layer"] == "1/0"
            # 自定义预设仍只保存几何，输出层由全局下拉框统一指定。
            settings, _preset, _created = tool._add_user_preset(settings, tool.TAB_SINGLE, settings["single"])
            tool._save_waveguide_params(settings)
            variants = []
            for row, (language, tab, layer_spec) in enumerate((
                ("en", 1, "4/0"), ("zh_CN", 2, "2/0"), ("zh_CN", 0, "42/7"),
            )):
                setattr(builtins, ui_language._SESSION_KEY, language)
                y = row * 300000
                shape = top.shapes(layout.layer(45, 0)).insert(pya.Path([
                    pya.Point(0, y), pya.Point(200000, y), pya.Point(200000, y + 200000),
                ], 500))
                selected = pya.ObjectInstPath()
                selected.top = top.cell_index()
                selected.cv_index = _value(view, "active_cellview_index")
                selected.shape, selected.layer = shape, layout.layer(45, 0)
                view.object_selection = [selected]

                def choose_layer():
                    dialog = pya.QApplication.activeModalWidget()
                    try:
                        combo = dialog.findChild("jnu_waveguide_layer")
                        assert combo is not None and not combo.isEditable()
                        choices = tool._waveguide_layer_choices(tool._load_waveguide_params()["waveguide_layer"])
                        specs = [spec for _name, spec in choices]
                        assert {"1/0", "4/0", "2/0", "42/7"} <= set(specs)
                        labels = [str(label.text) for label in dialog.findChildren() if isinstance(label, pya.QLabel)]
                        assert tool._dialog_text("Waveguide Layer：") in labels
                        tabs = dialog.findChild("jnu_path_to_waveguide_tabs")
                        for index in range(3):
                            tabs.setCurrentIndex(index)
                            assert not combo.isHidden()
                        tabs.setCurrentIndex(tab)
                        combo.setCurrentIndex(specs.index(layer_spec))
                        next(button for button in dialog.findChildren() if isinstance(button, pya.QPushButton)
                             and str(button.text) == tool._dialog_text("OK")).click()
                    except BaseException as error:
                        failures.append(repr(error))
                        dialog.reject()

                timer = pya.QTimer()
                timer.setSingleShot(True)
                timer.timeout(choose_layer)
                timer.start(0)
                old_indices = {inst.cell_index for inst in top.each_inst()}
                tool.path_to_waveguide()
                assert not failures, failures
                assert not messages, messages
                new = [inst.cell for inst in top.each_inst() if inst.cell_index not in old_indices]
                assert len(new) == 1
                cell = new[0]
                variants.append(cell)
                info = tool._parse_waveguide_layer(layer_spec)
                assert cell.pcell_parameters_by_name()["waveguide_layer"] == info
                assert not cell.shapes(layout.layer(info)).is_empty()
                assert cell.shapes(layout.layer(1, 0)).is_empty()
                assert len([s for s in cell.shapes(layout.layer(1, 10)).each() if s.is_path()]) == 2
                assert not cell.shapes(layout.layer(68, 0)).is_empty()
                assert tool._load_waveguide_params()["waveguide_layer"] == layer_spec
                assert reverse_tool._path_from_waveguide_cell(cell, layout) is not None
            assert top.shapes(layout.layer(45, 0)).is_empty()
            # 同路径和参数在不同层生成不同 variant，同层重复生成则复用。
            path = pya.DPath([pya.DPoint(0, 0), pya.DPoint(200, 0), pya.DPoint(200, 200)], 0.5)
            params = tool._result_from_editable_params(tool.TAB_SINGLE, settings["single"])
            default = tool._create_waveguide_cell(layout, path, params, 1)
            params["waveguide_layer"] = "4/0"
            other = tool._create_waveguide_cell(layout, path, params, 2)
            assert default.cell_index() != other.cell_index()
            assert other.cell_index() == tool._create_waveguide_cell(layout, path, params, 3).cell_index()
            assert not default.shapes(layout.layer(1, 0)).is_empty()
            output = str(Path(directory) / "output_layers.gds")
            options = pya.SaveLayoutOptions()
            options.set_format_from_filename(output)
            options.gds2_write_cell_properties = True
            layout.write(output, options)
            reread = pya.Layout()
            ensure_internal_waveguide_pcells(reread)
            reread.read(output)
            for cell in variants:
                restored = reread.cell(cell.name)
                assert restored is not None and restored.is_pcell_variant()
                info = cell.pcell_parameters_by_name()["waveguide_layer"]
                assert restored.pcell_parameters_by_name()["waveguide_layer"] == info
                assert (pya.Region(cell.begin_shapes_rec(layout.layer(info))) ^
                        pya.Region(restored.begin_shapes_rec(reread.layer(info)))).is_empty()
        finally:
            tool._waveguide_params_file, tool._message = original_file, original_message
            setattr(builtins, ui_language._SESSION_KEY, original_language)
    print("PASS: bilingual output-layer dropdown, all three tabs, custom layers, layer-specific variants and saved PCells", flush=True)


if __name__ == "__main__":
    main()
