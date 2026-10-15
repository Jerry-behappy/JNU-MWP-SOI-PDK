# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""验证两个波导的长度差、复合 taper 排除、GDS 重读和真实双语菜单。"""

import builtins
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

import pya


TEST_DIR = Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

from verify_waveguide_length import PYMACROS, _fixture, _selection, _variant  # noqa: E402
from JNU_MWP_tools.core.common import _value  # noqa: E402
from JNU_MWP_tools.core.waveguide_length import (  # noqa: E402
    WaveguideLengthError,
    compare_selected_waveguides,
)


def _reject(selection, reason):
    try:
        compare_selected_waveguides(selection, 0)
    except WaveguideLengthError as error:
        assert error.reason == reason, (error.reason, reason)
    else:
        raise AssertionError("无效选择没有报错：%s" % reason)


def _database_checks():
    layout = pya.Layout()
    top, instances = _fixture(layout)
    long_cell = _variant(layout, [(0, 0), (120, 0)], width=0.8)
    long_instance = top.insert(pya.CellInstArray(long_cell.cell_index(), pya.Trans()))
    chosen = _selection(top, [instances[0], long_instance])
    details, difference = compare_selected_waveguides(chosen, 0)
    assert [item["length_um"] for item in details] == [100.0, 120.0]
    assert difference == 20.0
    assert compare_selected_waveguides(chosen[::-1], 0)[1] == 20.0
    assert compare_selected_waveguides(chosen + [chosen[0].dup()], 0)[1] == 20.0
    assert compare_selected_waveguides(_selection(top, instances[:2]), 0)[1] == 0.0
    _reject([], "empty")
    _reject(chosen[:1], "not_two")
    _reject([chosen[0], chosen[0].dup()], "not_two")
    _reject(_selection(top, instances), "not_two")
    _reject(_selection(top, [instances[0], long_instance], 1), "unsupported")

    array = top.insert(pya.CellInstArray(
        instances[0].cell_index, pya.Trans(), pya.Vector(150000, 0), pya.Vector(0, 10000), 2, 3,
    ))
    array_obj = pya.ObjectInstPath()
    array_obj.top = top.cell_index()
    array_obj.cv_index = 0
    array_obj.append_path(pya.InstElement(array, -1, -1))
    _reject([chosen[0], array_obj], "not_two")
    members = []
    for index in (0, 1):
        member = pya.ObjectInstPath()
        member.top = top.cell_index()
        member.cv_index = 0
        member.append_path(pya.InstElement(array, index, 0))
        members.append(member)
    assert compare_selected_waveguides(members, 0)[1] == 0.0

    scaled = top.insert(pya.CellInstArray(instances[0].cell_index, pya.ICplxTrans(2.0, 90, True, 0, 0)))
    assert compare_selected_waveguides(_selection(top, [instances[0], scaled]), 0)[1] == 100.0
    other = layout.create_cell("OTHER_DEVICE")
    invalid = top.insert(pya.CellInstArray(other.cell_index(), pya.Trans()))
    _reject(_selection(top, [instances[0], invalid]), "unsupported")
    missing = layout.create_cell("Waveguide_missing_length")
    invalid_length = top.insert(pya.CellInstArray(missing.cell_index(), pya.Trans()))
    _reject(_selection(top, [instances[0], invalid_length]), "missing_length")

    composites = []
    for taper in (20.0, 10.0):
        cell = _variant(layout, [(0, 0), (100, 0), (100, 100)], composite=True, taper_length=taper)
        composites.append(top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans())))
    composite_details, composite_difference = compare_selected_waveguides(_selection(top, composites), 0)
    # 两条中心线全长相同，但排除的渐变段分别为 40 与 20 µm。
    assert composite_difference == 20.0
    assert [item["excluded_taper_length_um"] for item in composite_details] == [40.0, 20.0]
    assert [item["length_by_width_um"][2.0] for item in composite_details] == [116.0, 136.0]
    mixed, mixed_difference = compare_selected_waveguides(_selection(top, [instances[0], composites[0]]), 0)
    assert abs(mixed_difference - (mixed[1]["length_um"] - 100.0)) < 1e-9

    with tempfile.TemporaryDirectory(prefix="jnu_length_difference_") as directory:
        path = Path(directory) / "difference.gds"
        options = pya.SaveLayoutOptions()
        options.set_format_from_filename(str(path))
        options.gds2_write_cell_properties = True
        options.write_context_info = False
        layout.write(str(path), options)
        saved = pya.Layout()
        saved.read(str(path))
        saved_top = saved.cell(top.name)
        for before in (details, composite_details):
            names = [item["cell_name"] for item in before]
            saved_instances = [next(i for i in saved_top.each_inst() if i.cell.name == name) for name in names]
            assert all(not i.cell.is_pcell_variant() for i in saved_instances)
            reread_details, reread_difference = compare_selected_waveguides(_selection(saved_top, saved_instances), 0)
            assert reread_difference == 20.0
            assert [item["length_by_width_um"] for item in reread_details] == [item["length_by_width_um"] for item in before]
    print("PASS: absolute differences, copies, arrays, scales, strict selection, taper exclusion and reopened GDS", flush=True)


def _gui_checks():
    from JNU_MWP_tools.actions import calculate_waveguide_length as length_action
    from JNU_MWP_tools.actions import calculate_waveguide_length_difference as action
    from JNU_MWP_tools.actions import startup_update
    from JNU_MWP_tools.core import ui_language

    window = pya.Application.instance().main_window()
    if window is None:
        return
    original_pya, original_show = action.pya, action._show_results
    original_exec = length_action.exec_dialog_with_persisted_size
    original_schedule = startup_update.schedule_startup_update_check
    messages = []
    action.pya = SimpleNamespace(MessageBox=SimpleNamespace(
        Ok=1, warning=lambda title, text, _buttons: messages.append(("warning", title, text, None)),
    ))
    action._show_results = lambda title, text, key: messages.append(("info", title, text, key))
    startup_update.schedule_startup_update_check = lambda: False
    try:
        cellview = window.create_layout(1)
        layout = cellview.layout()
        top, instances = _fixture(layout)
        cellview.cell = top
        view = window.current_view()
        cv_index = _value(view, "active_cellview_index")
        long_cell = _variant(layout, [(0, 0), (120, 0)], width=0.8)
        long_instance = top.insert(pya.CellInstArray(long_cell.cell_index(), pya.Trans()))
        composite = _variant(layout, [(0, 0), (100, 0), (100, 100)], composite=True)
        composite_instance = top.insert(pya.CellInstArray(composite.cell_index(), pya.Trans()))
        other = layout.create_cell("OTHER_DEVICE")
        invalid = top.insert(pya.CellInstArray(other.cell_index(), pya.Trans()))
        macro = pya.Macro(str(PYMACROS / "JNU_MWP_PDK_Menu.lym"))
        for language, title in (("en", "Calculate Waveguide Length Difference"), ("zh_CN", "计算波导长度差")):
            setattr(builtins, ui_language._SESSION_KEY, language)
            macro.run()
            macro.run()
            assert len(window._jnu_menu_actions) == 14
            assert len({str(item.title) for item in window._jnu_menu_actions}) == 14
            menu_action = window.menu().action("jnu_mwp_pdk_menu.waveguides.jnu_action_calculate_waveguide_length_difference")
            assert menu_action.title == "计算波导长度差 / Calculate Waveguide Length Difference"
            chosen = _selection(top, [instances[0], long_instance], cv_index)
            view.object_selection = chosen
            menu_action.trigger()
            report = messages[-1][2]
            assert messages[-1][0:2] == ("info", title)
            assert "|L1 − L2|" in report and "20.000 µm" in report and "0.020000 mm" in report
            assert "100.000 µm" in report and "120.000 µm" in report
            assert ("Waveguide width: 0.800 µm" if language == "en" else "波导宽度：0.800 µm") in report
            assert ("Bend radius R: 20.000 µm" if language == "en" else "弯曲半径 R：20.000 µm") in report
            assert all(obj in view.object_selection for obj in chosen) and len(view.object_selection) == 2
            assert messages[-1][3] == "calculate_waveguide_length_difference"
            view.object_selection = _selection(top, [instances[0], composite_instance], cv_index)
            menu_action.trigger()
            report = messages[-1][2]
            assert messages[-1][0:2] == ("info", title)
            assert ("taper lengths are excluded" if language == "en" else "taper（宽度渐变段）长度不计入") in report
            assert "116.000" in report and "40.000 µm" in report
            assert ("Comparison by width" if language == "en" else "按宽度比较") in report
            for group in ([], instances[:1], instances, [instances[0], invalid]):
                chosen = _selection(top, group, cv_index)
                view.object_selection = chosen
                menu_action.trigger()
                assert messages[-1][0:2] == ("warning", title)
                assert len(view.object_selection) == len(chosen)

        def check_dialog(dialog, key, default_size):
            output = dialog.findChild("waveguide_length_output")
            assert output.toPlainText() == report and _value(output, "readOnly")
            assert _value(_value(output, "font"), "pointSize") == 11
            assert key == "calculate_waveguide_length_difference"
            dialog.resize(*default_size)
            timer = pya.QTimer(dialog)
            timer.setSingleShot(True)
            timer.timeout(dialog.accept)
            timer.start(0)
            return dialog.exec_()

        length_action.exec_dialog_with_persisted_size = check_dialog
        original_show("计算波导长度差", report, "calculate_waveguide_length_difference")
        print("PASS: bilingual menu callbacks, duplicate registration, unchanged selection and native Qt difference dialog", flush=True)
    finally:
        action.pya, action._show_results = original_pya, original_show
        length_action.exec_dialog_with_persisted_size = original_exec
        startup_update.schedule_startup_update_check = original_schedule


if __name__ == "__main__":
    _database_checks()
    if hasattr(pya, "Application"):
        _gui_checks()
