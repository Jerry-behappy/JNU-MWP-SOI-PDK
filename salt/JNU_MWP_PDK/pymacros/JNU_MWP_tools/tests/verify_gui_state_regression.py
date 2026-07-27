# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""JNU 自定义对话框尺寸持久化回归。"""

import json
import os
from pathlib import Path
import sys
import tempfile

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

from JNU_MWP_tools.core import gui_state  # noqa: E402


def _assert(condition, message):
    if not condition:
        raise RuntimeError(message)


class _FakeApplication:
    def __init__(self):
        self.config = {}

    def get_config(self, key):
        return self.config.get(key, "")

    def set_config(self, key, value):
        self.config[key] = value


class _FakeDialog:
    def __init__(self, width=320, height=240, result=1, resized_on_exec=None):
        self.width = width
        self.height = height
        self.result = result
        self.resized_on_exec = resized_on_exec

    def resize(self, width, height):
        self.width = int(width)
        self.height = int(height)

    def exec_(self):
        if self.resized_on_exec is not None:
            self.resize(*self.resized_on_exec)
        return self.result


def _check_qt_dialog_when_available():
    if os.environ.get("JNU_RUN_QT_WIDGET_TESTS") != "1":
        return
    try:
        if pya.QApplication.instance() is None:
            return
    except Exception:
        return
    original_file = gui_state._gui_state_file
    with tempfile.TemporaryDirectory(prefix="jnu_gui_qt_state_") as directory:
        gui_state._gui_state_file = lambda: os.path.join(directory, "jnu_gui_state.json")
        try:
            dialog = pya.QDialog()
            timer = pya.QTimer(dialog)
            timer.setSingleShot(True)

            def resize_and_close():
                dialog.resize(1234, 678)
                dialog.reject()

            timer.timeout(resize_and_close)
            timer.start(0)
            gui_state.exec_dialog_with_persisted_size(
                dialog, "qt_dialog", (640, 480), _FakeApplication(),
            )
            reopened = pya.QDialog()
            gui_state.restore_dialog_size(
                reopened, "qt_dialog", (640, 480), _FakeApplication(),
            )
            _assert(int(reopened.width) == 1234, "实际 QDialog 宽度未恢复。")
            _assert(int(reopened.height) == 678, "实际 QDialog 高度未恢复。")
        finally:
            gui_state._gui_state_file = original_file


def main():
    _assert(gui_state.parse_dialog_size("980,620") == (980, 620), "字符串尺寸解析失败。")
    _assert(gui_state.parse_dialog_size([720, 420]) == (720, 420), "JSON尺寸解析失败。")
    _assert(gui_state.parse_dialog_size("20,20") is None, "非法小尺寸未拒绝。")

    original_file = gui_state._gui_state_file
    with tempfile.TemporaryDirectory(prefix="jnu_gui_state_") as directory:
        filepath = os.path.join(directory, "jnu_gui_state.json")
        gui_state._gui_state_file = lambda: filepath
        app = _FakeApplication()
        try:
            first = _FakeDialog(resized_on_exec=(1111, 777))
            result = gui_state.exec_dialog_with_persisted_size(
                first, "numerical_text_array", (640, 420), app,
            )
            _assert(result == 1, "对话框结果未透传。")
            _assert((first.width, first.height) == (1111, 777), "用户尺寸未保留到关闭时。")
            with open(filepath, "r", encoding="utf-8") as stream:
                saved = json.load(stream)
            _assert(
                saved["dialog_sizes"]["numerical_text_array"] == [1111, 777],
                "用户尺寸未写入独立JSON。",
            )

            reopened = _FakeDialog()
            restored = gui_state.restore_dialog_size(
                reopened, "numerical_text_array", (640, 420), app,
            )
            _assert(restored == (1111, 777), "重开时未读取用户尺寸。")
            _assert((reopened.width, reopened.height) == (1111, 777), "重开尺寸应用失败。")

            other = _FakeDialog()
            gui_state.restore_dialog_size(other, "make_pins_for_cell", (500, 300), app)
            _assert((other.width, other.height) == (500, 300), "不同窗口未使用独立默认尺寸。")
        finally:
            gui_state._gui_state_file = original_file

    _check_qt_dialog_when_available()
    print("GUI state regression: PASS")


if __name__ == "__main__":
    main()
