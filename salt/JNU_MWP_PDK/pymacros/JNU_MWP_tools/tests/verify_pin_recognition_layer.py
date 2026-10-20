# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""验证识别层输入、设置持久化及真实路径转换的端口吸附。"""

from pathlib import Path
import builtins
import sys
import tempfile

import pya

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from JNU_MWP_tools.actions import path_to_waveguide as tool
from JNU_MWP_tools.core import ui_language
from JNU_MWP_tools.core.common import _find_pins_in_cell, _value
from JNU_MWP_tools.core.make_pin import make_pin


def main():
    assert tool._default_waveguide_params()["pin_recognition_layer"] == "1/10"
    assert tool._parse_pin_recognition_layer(" 95 / 0 ").to_s() == "95/0"
    for invalid in ("", "95", "1/*", "-1/0", "65536/0", "1/1.5"):
        try:
            tool._parse_pin_recognition_layer(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(invalid)
    window = pya.Application.instance().main_window()
    cv = window.create_layout(1)
    layout = cv.layout()
    top = layout.create_cell("PIN_RECOGNITION_TEST")
    cv.cell = top
    view = window.current_view()
    child = layout.create_cell("CUSTOM_PINS")
    for x, direction, name in ((0, 0, "in"), (100000, 180, "out")):
        make_pin(child, name, pya.Point(x, 0), 500, layout.layer(95, 0), direction)
    top.insert(pya.CellInstArray(child.cell_index(), pya.Trans()))
    assert not _find_pins_in_cell(top, layout)
    assert len(_find_pins_in_cell(top, layout, pya.LayerInfo(95, 0))) == 2
    source = top.shapes(layout.layer(42, 7)).insert(pya.Path([pya.Point(1000, 0), pya.Point(99000, 0)], 500))
    obj = pya.ObjectInstPath()
    obj.top = top.cell_index()
    obj.cv_index = _value(view, "active_cellview_index")
    obj.shape = source
    obj.layer = layout.layer(42, 7)
    view.object_selection = [obj]
    original_file, original_message = tool._waveguide_params_file, tool._message
    session = getattr(builtins, ui_language._SESSION_KEY, None)
    errors, messages = [], []
    with tempfile.TemporaryDirectory(prefix="jnu-pin-recognition-") as directory:
        tool._waveguide_params_file = lambda: str(Path(directory) / "settings.json")
        tool._message = lambda title, text: messages.append(text)
        try:
            for language in ("en", "zh_CN"):
                setattr(builtins, ui_language._SESSION_KEY, language)
                def edit_dialog():
                    dialog = _value(pya.QApplication.instance(), "activeModalWidget")
                    try:
                        edit = dialog.findChild("jnu_pin_recognition_layer")
                        assert edit is not None and not edit.isReadOnly()
                        assert edit.text == ("1/10" if language == "en" else "95/0")
                        tabs = dialog.findChild("jnu_path_to_waveguide_tabs")
                        for index in range(3):
                            tabs.setCurrentIndex(index)
                            assert not edit.isHidden()
                        tabs.setCurrentIndex(1)
                        ok = next(button for button in dialog.findChildren()
                                  if isinstance(button, pya.QPushButton) and button.text == tool._dialog_text("OK"))
                        edit.setText("95")
                        ok.click()
                        assert messages and dialog.isVisible()
                        edit.setText("95/0")
                        ok.click()
                    except Exception as error:
                        errors.append(repr(error))
                        dialog.reject()
                timer = pya.QTimer()
                timer.setSingleShot(True)
                timer.timeout(edit_dialog)
                timer.start(0)
                result = tool._show_waveguide_dialog()
                assert not errors, errors
                assert result["pin_recognition_layer"] == "95/0"
                assert tool._load_waveguide_params()["pin_recognition_layer"] == "95/0"
            original_dialog = tool._show_waveguide_dialog
            tool._show_waveguide_dialog = lambda dbu: result
            try:
                tool.path_to_waveguide()
            finally:
                tool._show_waveguide_dialog = original_dialog
            assert top.shapes(layout.layer(42, 7)).is_empty()
            waveguide = next(instance.cell for instance in top.each_inst() if instance.cell.is_pcell_variant())
            points = list(waveguide.pcell_parameters_by_name()["path"].each_point())
            assert abs(points[-1].x - points[0].x) == 100.0, points
            assert len(_find_pins_in_cell(waveguide, layout)) == 2
        finally:
            tool._waveguide_params_file, tool._message = original_file, original_message
            setattr(builtins, ui_language._SESSION_KEY, session)
    print("PASS: bilingual editable PinRec input, invalid input blocking, persistence and custom-layer path snapping; generated pins stay on 1/10", flush=True)


if __name__ == "__main__":
    main()
