# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-08

"""在 KLayout 隐藏 GUI 中验证菜单宏和 PDK 重载入口的幂等性。"""

from pathlib import Path
import sys

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))


MENU_MACRO = PYMACROS_DIR / "JNU_MWP_PDK_Menu.lym"
EXPECTED_ACTION_COUNT = 10
EXPECTED_SHORTCUTS = {
    "jnu_action_path_to_waveguide": "9",
    "jnu_action_waveguide_to_path": "8",
    "jnu_action_sbend_connect_between_two_cells": "7",
    "jnu_action_snap_components": "6",
    "jnu_action_make_pins_for_cell": "Ctrl+Alt+M",
    "jnu_action_layer_exclude": "Ctrl+Alt+L",
    "jnu_action_numerical_text_array": "Ctrl+Alt+N",
    "jnu_action_jnu_mwp_drc": "Ctrl+Alt+D",
    "jnu_action_run_jnu_mwp_drc": "",
    "jnu_action_reload_jnu_pdk": "Ctrl+Alt+R",
}


def _assert(condition, message):
    if not condition:
        raise RuntimeError(message)


def _check_menu(main_window):
    actions = getattr(main_window, "_jnu_menu_actions", [])
    _assert(len(actions) == EXPECTED_ACTION_COUNT, "JNU 菜单 Action 数量错误：%d。" % len(actions))
    titles = sorted(str(action.title) for action in actions)
    _assert("Reload JNU PDK" in titles, "根菜单缺少 Reload JNU PDK。")
    _assert(len(titles) == len(set(titles)), "JNU 菜单存在重复 Action。")


def _action_value(action, name):
    value = getattr(action, name)
    return value() if callable(value) else value


def _set_test_shortcuts(main_window):
    actions_by_id = getattr(main_window, "_jnu_menu_actions_by_id", {})
    _assert(set(actions_by_id) == set(EXPECTED_SHORTCUTS), "JNU Action ID 映射不完整。")
    for item_id, shortcut in EXPECTED_SHORTCUTS.items():
        actions_by_id[item_id].shortcut = shortcut


def _set_configured_shortcuts(app):
    """把测试快捷键写入隔离配置，验证当前 Action 已为空时仍能恢复。"""
    config = str(app.get_config("key-bindings") or "")
    mapping = {}
    for entry in config.split(";"):
        if ":" in entry:
            key, value = entry.split(":", 1)
            mapping[key] = value
    parent_by_id = {
        "jnu_action_path_to_waveguide": "jnu_mwp_pdk_menu.waveguides",
        "jnu_action_waveguide_to_path": "jnu_mwp_pdk_menu.waveguides",
        "jnu_action_sbend_connect_between_two_cells": "jnu_mwp_pdk_menu.waveguides",
        "jnu_action_snap_components": "jnu_mwp_pdk_menu.layout",
        "jnu_action_make_pins_for_cell": "jnu_mwp_pdk_menu.layout",
        "jnu_action_layer_exclude": "jnu_mwp_pdk_menu.layout",
        "jnu_action_numerical_text_array": "jnu_mwp_pdk_menu.layout",
        "jnu_action_jnu_mwp_drc": "jnu_mwp_pdk_menu.drc",
        "jnu_action_run_jnu_mwp_drc": "jnu_mwp_pdk_menu.drc",
        "jnu_action_reload_jnu_pdk": "jnu_mwp_pdk_menu",
    }
    for item_id, shortcut in EXPECTED_SHORTCUTS.items():
        mapping[parent_by_id[item_id] + "." + item_id] = "'%s'" % shortcut
    app.set_config(
        "key-bindings",
        ";".join("%s:%s" % item for item in sorted(mapping.items())),
    )


def _check_shortcuts(main_window):
    actions_by_id = getattr(main_window, "_jnu_menu_actions_by_id", {})
    for item_id, expected in EXPECTED_SHORTCUTS.items():
        actual = str(_action_value(actions_by_id[item_id], "shortcut"))
        _assert(actual == expected, "%s 快捷键丢失：%s != %s。" % (item_id, actual, expected))


def _verify_reload_timer_lifecycle(reload_pdk):
    """验证 timer 不写入 MainWindow 属性，并会合并重复菜单触发。"""
    class MainWindow:
        pass

    class Timer:
        def __init__(self, _parent):
            self._active = False
            self._callback = None
            self.single_shot = False

        def setSingleShot(self, value):
            self.single_shot = bool(value)

        def timeout(self, callback):
            self._callback = callback

        def start(self, _milliseconds):
            self._active = True

        def isActive(self):
            return self._active

        def fire(self):
            self._active = False
            self._callback()

    main_window = MainWindow()
    created = []
    runs = []
    original_runner = reload_pdk._run_reload_with_feedback
    original_timer = reload_pdk._PENDING_RELOAD_TIMER
    try:
        reload_pdk._PENDING_RELOAD_TIMER = None

        def timer_factory(parent):
            timer = Timer(parent)
            created.append(timer)
            return timer

        def fake_runner(window):
            runs.append(window)
            reload_pdk._clear_pending_reload_timer()

        reload_pdk._run_reload_with_feedback = fake_runner
        _assert(reload_pdk._schedule_reload(main_window, timer_factory), "首次重载 timer 未创建。")
        _assert(not hasattr(main_window, "_jnu_reload_pdk_timer"), "timer 不应写入 MainWindow 属性。")
        _assert(not reload_pdk._schedule_reload(main_window, timer_factory), "活跃 timer 未合并重复触发。")
        _assert(len(created) == 1, "重复触发创建了多个 timer。")
        created[0].fire()
        _assert(runs == [main_window], "timer 未执行重载回调。")
        _assert(reload_pdk._PENDING_RELOAD_TIMER is None, "timer 回调后未释放模块级引用。")
    finally:
        reload_pdk._run_reload_with_feedback = original_runner
        reload_pdk._PENDING_RELOAD_TIMER = original_timer


def main():
    app = pya.Application.instance()
    main_window = app.main_window() if app is not None else None
    _assert(main_window is not None, "该测试需要 KLayout -z -e 隐藏 GUI。")

    pya.Macro(str(MENU_MACRO)).run()
    _check_menu(main_window)
    _set_test_shortcuts(main_window)

    # 模拟从没有 action-ID 映射的旧菜单首次升级，必须按唯一标题保留快捷键。
    del main_window._jnu_menu_actions_by_id
    pya.Macro(str(MENU_MACRO)).run()
    _check_menu(main_window)
    _check_shortcuts(main_window)

    # 模拟快捷键已被旧版热重载清空，从 KLayout 的稳定菜单路径配置恢复。
    _set_configured_shortcuts(app)
    for action in main_window._jnu_menu_actions:
        action.shortcut = ""
    del main_window._jnu_menu_actions_by_id
    pya.Macro(str(MENU_MACRO)).run()
    _check_menu(main_window)
    _check_shortcuts(main_window)

    pya.Macro(str(MENU_MACRO)).run()
    _check_menu(main_window)
    _check_shortcuts(main_window)

    cellview = main_window.create_layout(1)
    layout = cellview.layout()
    from JNU_MWP_pcells.composite_waveguide import CompositeWaveguide
    from JNU_MWP_pcells.waveguide import Waveguide

    layout.register_pcell("Waveguide", Waveguide())
    layout.register_pcell("Composite_Waveguide", CompositeWaveguide())

    from JNU_MWP_tools.actions import reload_pdk

    _verify_reload_timer_lifecycle(reload_pdk)

    for _index in range(3):
        result = reload_pdk.reload_jnu_pdk(main_window=main_window, reload_menu=True)
        _assert(result["layout_count"] >= 1, "热重载未枚举当前隐藏视图中的 layout。")
        _assert(result["internal_refresh_count"] == 2, "热重载未替换两个内部波导声明。")
        _check_menu(main_window)
        _check_shortcuts(main_window)

    library_count = sum(
        1
        for library_id in pya.Library.library_ids()
        if pya.Library.library_by_id(library_id).name() == "JNULib"
    )
    _assert(library_count == 1, "GUI 重载后存在重复 JNULib。")
    print("OK: menu, shortcuts and Reload JNU PDK remained stable after repeated GUI reloads.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
