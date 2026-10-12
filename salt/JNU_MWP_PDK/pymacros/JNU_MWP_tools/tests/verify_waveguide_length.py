# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""验证单宽度波导多选长度、错误选择、GDS 重读及实际菜单回调。"""

import builtins
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

import pya


PYMACROS = Path(__file__).resolve().parents[2]
if str(PYMACROS) not in sys.path:
    sys.path.insert(0, str(PYMACROS))

from JNU_MWP_tools.actions.path_to_waveguide import _create_waveguide_cell  # noqa: E402
from JNU_MWP_tools.core.common import _value  # noqa: E402
from JNU_MWP_tools.core.waveguide_length import (  # noqa: E402
    WaveguideLengthError,
    measure_selected_waveguides,
)


def _selection(top, instances, cv_index=0):
    selected = []
    for instance in instances:
        obj = pya.ObjectInstPath()
        obj.top = top.cell_index()
        obj.cv_index = cv_index
        obj.append_path(pya.InstElement(instance))
        selected.append(obj)
    return selected


def _variant(layout, points, bend="Circular", composite=False):
    params = {
        "mode": "composite" if composite else "single",
        "width": 0.5, "radius": 20.0, "bend_type": bend, "bezier": 0.35,
        "Euler_Rmax": 30.0, "Euler_Rmin": 10.0,
        "straight_width": 2.0, "start_width": 2.0, "end_width": 2.0,
        "bend_width": 0.5, "taper_length": 20.0, "transition_length": 2.0,
    }
    return _create_waveguide_cell(
        layout, pya.DPath([pya.DPoint(*xy) for xy in points], 0.5), params, 1
    )


def _fixture(layout):
    layout.dbu = 0.001
    top = layout.create_cell("LENGTH_TEST")
    straight = _variant(layout, [(0, 0), (100, 0)])
    first = top.insert(pya.CellInstArray(straight.cell_index(), pya.Trans()))
    copied = top.insert(pya.CellInstArray(straight.cell_index(), pya.Trans(0, 10000)))
    curved = _variant(layout, [(0, 0), (80, 0), (80, 60)])
    third = top.insert(pya.CellInstArray(curved.cell_index(), pya.Trans(200000, 0)))
    return top, [first, copied, third]


def _reject(selection, reason):
    try:
        measure_selected_waveguides(selection, 0)
    except WaveguideLengthError as error:
        assert error.reason == reason, (error.reason, reason)
    else:
        raise AssertionError("无效选择没有报错：%s" % reason)


def _database_checks():
    layout = pya.Layout()
    top, instances = _fixture(layout)
    chosen = _selection(top, instances)
    count, total = measure_selected_waveguides(chosen, 0)
    expected = 200.0 + 100.0 + 20.0 * math.pi / 2.0
    assert count == 3 and abs(total - expected) < 0.02, (count, total, expected)
    assert measure_selected_waveguides(chosen[:2], 0) == (2, 200.0)
    assert measure_selected_waveguides(chosen + [chosen[0].dup()], 0) == (count, total)

    # 相同 variant 的副本分别计入；层级缩放改变长度而旋转镜像不改变。
    wrapper = layout.create_cell("SCALED_PARENT")
    nested = wrapper.insert(pya.CellInstArray(instances[0].cell_index, pya.Trans()))
    parent = top.insert(pya.CellInstArray(wrapper.cell_index(), pya.ICplxTrans(2.0, 90, True, 0, 0)))
    obj = _selection(top, [parent])[0]
    obj.append_path(pya.InstElement(nested))
    assert measure_selected_waveguides([obj], 0) == (1, 200.0)

    for bend in ("Bezier", "Euler"):
        cell = _variant(layout, [(0, 0), (80, 0), (80, 60)], bend)
        instance = top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans()))
        number, length = measure_selected_waveguides(_selection(top, [instance]), 0)
        assert number == 1 and 100.0 < length < 140.0, (bend, length)

    # 复合波导、普通 cell、普通 Path 以及空选择均拒绝，不返回部分总长。
    composite = _variant(layout, [(0, 0), (100, 0)], composite=True)
    other = layout.create_cell("OTHER_DEVICE")
    missing = layout.create_cell("Waveguide_legacy_missing_length")
    for cell, reason in ((composite, "unsupported"), (other, "unsupported"), (missing, "missing_length")):
        instance = top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans()))
        _reject(chosen[:1] + _selection(top, [instance]), reason)
    shape = top.shapes(layout.layer(1, 0)).insert(pya.Path([pya.Point(0, 0), pya.Point(1000, 0)], 500))
    obj = pya.ObjectInstPath()
    obj.top = top.cell_index()
    obj.cv_index = 0
    obj.layer = layout.layer(1, 0)
    obj.shape = shape
    _reject(chosen[:1] + [obj], "unsupported")
    _reject([], "empty")
    _reject(_selection(top, instances[:1], 1), "unsupported")

    with tempfile.TemporaryDirectory(prefix="jnu_length_") as directory:
        path = Path(directory) / "length.gds"
        options = pya.SaveLayoutOptions()
        options.set_format_from_filename(str(path))
        options.gds2_write_cell_properties = True
        options.write_context_info = False
        layout.write(str(path), options)
        reread = pya.Layout()
        reread.read(str(path))
        saved_top = reread.cell(top.name)
        saved_instances = list(saved_top.each_inst())[:3]
        assert not saved_instances[0].cell.is_pcell_variant()
        assert measure_selected_waveguides(_selection(saved_top, saved_instances), 0) == (count, total)
    print("PASS: single-width multi-selection, copies, curves, transforms, strict errors and stored GDS", flush=True)


def _gui_checks():
    app = pya.Application.instance()
    window = app.main_window()
    if window is None:
        return
    from JNU_MWP_tools.actions import calculate_waveguide_length as action
    from JNU_MWP_tools.actions import startup_update
    from JNU_MWP_tools.core import ui_language

    # 隔离进程中捕获弹窗文字，使真实菜单回调可以自动验收而不会阻塞。
    messages = []
    original_pya = action.pya
    action.pya = SimpleNamespace(MessageBox=SimpleNamespace(
        Ok=1,
        info=lambda title, text, _buttons: messages.append(("info", title, text)),
        warning=lambda title, text, _buttons: messages.append(("warning", title, text)),
    ))
    startup_update.schedule_startup_update_check = lambda: False
    try:
        cellview = window.create_layout(1)
        top, instances = _fixture(cellview.layout())
        cellview.cell = top
        view = window.current_view()
        cv_index = _value(view, "active_cellview_index")
        chosen = _selection(top, instances[:2], cv_index)
        menu_macro = pya.Macro(str(PYMACROS / "JNU_MWP_PDK_Menu.lym"))
        for language, title in (("en", "Calculate Waveguide Length"), ("zh_CN", "计算波导长度")):
            setattr(builtins, ui_language._SESSION_KEY, language)
            menu_macro.run()
            menu_macro.run()
            menu_path = "jnu_mwp_pdk_menu.waveguides.jnu_action_calculate_waveguide_length"
            menu_action = window.menu().action(menu_path)
            assert menu_action.title == title
            view.object_selection = chosen
            menu_action.trigger()
            assert messages[-1][0:2] == ("info", title)
            assert "200.000" in messages[-1][2]
            assert len(view.object_selection) == len(chosen)
            assert all(obj in view.object_selection for obj in chosen)
            composite = _variant(cellview.layout(), [(0, 0), (100, 0)], composite=True)
            invalid = top.insert(pya.CellInstArray(composite.cell_index(), pya.Trans()))
            mixed = chosen + _selection(top, [invalid], cv_index)
            view.object_selection = mixed
            menu_action.trigger()
            assert messages[-1][0:2] == ("warning", title)
            assert len(view.object_selection) == len(mixed)
            assert all(obj in view.object_selection for obj in mixed)
        print("PASS: real English/Chinese menu callbacks, repeated registration and mixed-selection error", flush=True)
    finally:
        action.pya = original_pya


if __name__ == "__main__":
    _database_checks()
    if hasattr(pya, "Application"):
        _gui_checks()
