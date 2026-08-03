# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-08

"""验证原生 Macro Development DRC 编辑入口、规则持久化与当前 Cell 范围。"""

import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

from JNU_MWP_tools.actions import drc  # noqa: E402


def _expect_value_error(callback, message):
    """确认无效规则代码会被明确拒绝。"""
    try:
        callback()
    except ValueError:
        return
    raise AssertionError(message)


def _verify_active_cell_context():
    """用内存替身验证子 Cell 会成为 DRC source 的 top cell。"""
    layout = pya.Layout()
    top = layout.create_cell("DRC_TOP")
    child = layout.create_cell("DRC_CURRENT_CHILD")
    top.insert(pya.CellInstArray(child.cell_index(), pya.Trans()))

    class CellView:
        def __init__(self, current_layout, cell):
            self._layout = current_layout
            self.cell = cell

        def layout(self):
            return self._layout

    class View:
        def __init__(self, cellview):
            self._cellview = cellview

        def active_cellview(self):
            return self._cellview

    class MainWindow:
        def __init__(self, view):
            self._view = view

        def current_view(self):
            return self._view

    original_main_window = drc._main_window
    try:
        drc._main_window = lambda: MainWindow(View(CellView(layout, child)))
        _view, _cellview, current_layout, current_cell = drc._current_layout_view_context()
        assert current_layout is layout
        assert current_cell.cell_index() == child.cell_index()
    finally:
        drc._main_window = original_main_window
    return child.name


def _verify_native_macro_editor_launch(macro_path):
    """通过替身验证原生 Macro Development 的路径配置与 action 触发。"""
    class Action:
        def __init__(self):
            self.trigger_count = 0

        def trigger(self):
            self.trigger_count += 1

    class Menu:
        def __init__(self, action):
            self._action = action

        def action(self, action_id):
            assert action_id == "macros_menu.macro_development"
            return self._action

    class MainWindow:
        def __init__(self, action):
            self._menu = Menu(action)

        def menu(self):
            return self._menu

    class Application:
        def __init__(self):
            self.config = {"macro-editor-open-macros": "'C:/existing/example.lym'"}

        def get_config(self, key):
            return self.config.get(key, "")

        def set_config(self, key, value):
            self.config[key] = value

    action = Action()
    application = Application()
    assert drc._open_native_macro_editor(macro_path, application, MainWindow(action))
    path_text = str(Path(macro_path).resolve()).replace("\\", "/")
    assert application.config["macro-editor-current-macro"] == path_text
    assert "'C:/existing/example.lym'" in application.config["macro-editor-open-macros"]
    assert "'%s'" % path_text in application.config["macro-editor-open-macros"]
    assert action.trigger_count == 1


def main():
    default_code = drc.load_persisted_drc_code()
    assert "LayerM1.space(6.0 - tol)" in default_code
    assert "M1 最小间距违规，最小要求 6 um" in default_code
    assert "LayerM2.width(10.0 - tol" in default_code
    assert "LayerM2.space(6.0 - tol)" in default_code
    assert "M2 最小宽度违规，最小要求 10 um" in default_code
    assert "M2 最小间距违规，最小要求 6 um" in default_code
    assert "LayerDeepTrench.separation(LayerM2, 12.0 - tol)" in default_code
    assert "深槽与 M2 最小间距违规，最小要求 12 um" in default_code
    executable_lines = [line.split("#", 1)[0].strip() for line in default_code.splitlines()]
    assert not any(re.match(r"^source\s*\(", line) for line in executable_lines)
    assert sum(bool(re.match(r"^report\s*\(", line)) for line in executable_lines) == 1

    _expect_value_error(lambda: drc.validate_drc_code(""), "空 DRC 代码必须被拒绝。")
    _expect_value_error(
        lambda: drc.validate_drc_code('source("input.gds", "TOP")'),
        "用户代码中的 source() 必须被拒绝。",
    )
    _expect_value_error(
        lambda: drc.validate_drc_code('report("DRC", "result.lyrdb")'),
        "用户代码中的 report() 必须被拒绝。",
    )

    child_name = _verify_active_cell_context()
    scoped_code = drc.build_drc_text(
        default_code, "input.gds", child_name, "result.lyrdb",
    )
    assert 'source("input.gds", "DRC_CURRENT_CHILD")' in scoped_code
    assert 'report("JNU MWP 设计规则检查", "result.lyrdb")' in scoped_code
    assert drc._strip_single_argument_report(default_code).rstrip() in scoped_code

    macro_xml = drc.build_drc_macro_xml(scoped_code)
    root = ET.fromstring(macro_xml)
    assert root.findtext("interpreter") == "dsl"
    assert root.findtext("text") == scoped_code

    with tempfile.TemporaryDirectory(prefix="jnu_mwp_drc_test_") as directory:
        test_macro = Path(directory) / "JNU_MWP_DRC.lydrc"
        shutil.copyfile(drc.drc_macro_path(), test_macro)
        saved_code = default_code + "\n# 回归测试持久化标记\n"
        assert drc.save_persisted_drc_code(saved_code, test_macro) == drc.validate_drc_code(saved_code)
        assert drc.load_persisted_drc_code(test_macro) == drc.validate_drc_code(saved_code)
        persisted_root = ET.parse(str(test_macro)).getroot()
        assert persisted_root.findtext("text") == drc.validate_drc_code(saved_code)
        _verify_native_macro_editor_launch(test_macro)

    temporary_macro = drc.write_temporary_drc_macro(scoped_code)
    try:
        assert os.path.isfile(temporary_macro)
        with open(temporary_macro, "r", encoding="utf-8") as stream:
            assert ET.fromstring(stream.read()).findtext("text") == scoped_code
    finally:
        if os.path.isfile(temporary_macro):
            os.remove(temporary_macro)

    print("OK: native Macro Development DRC editor, persistence and active-cell scope")


if __name__ == "__main__":
    main()
