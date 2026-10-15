# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""验证各宽度波导长度、taper 排除、GDS 重读及双语菜单回调。"""

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
from JNU_MWP_tools.core.common import RAW_PATH_GDS_PROPERTY, RAW_PATH_PROPERTY, _value  # noqa: E402
from JNU_MWP_tools.core.waveguide_length import (  # noqa: E402
    WaveguideLengthError,
    describe_selected_waveguides,
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


def _variant(layout, points, bend="Circular", composite=False, **overrides):
    params = {
        "mode": "composite" if composite else "single",
        "width": 0.5, "radius": 20.0, "bend_type": bend, "bezier": 0.35,
        "Euler_Rmax": 30.0, "Euler_Rmin": 10.0,
        "straight_width": 2.0, "start_width": 2.0, "end_width": 2.0,
        "bend_width": 0.5, "taper_length": 20.0, "transition_length": 2.0,
    }
    params.update(overrides)
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
    details = describe_selected_waveguides(chosen, 0)
    assert len(details) == 3
    assert all(item["parameters"]["width"] == 0.5 for item in details)
    assert details[2]["parameters"]["bend_type"] == "Circular"
    assert details[2]["parameters"]["radius"] == 20.0

    # 相同 variant 的副本分别计入；层级缩放改变长度而旋转镜像不改变。
    wrapper = layout.create_cell("SCALED_PARENT")
    nested = wrapper.insert(pya.CellInstArray(instances[0].cell_index, pya.Trans()))
    parent = top.insert(pya.CellInstArray(wrapper.cell_index(), pya.ICplxTrans(2.0, 90, True, 0, 0)))
    obj = _selection(top, [parent])[0]
    obj.append_path(pya.InstElement(nested))
    assert measure_selected_waveguides([obj], 0) == (1, 200.0)
    scaled = describe_selected_waveguides([obj], 0)[0]
    assert scaled["parameters"]["width"] == 1.0
    assert scaled["parameters"]["radius"] == 40.0

    array = top.insert(pya.CellInstArray(
        instances[0].cell_index, pya.Trans(), pya.Vector(150000, 0),
        pya.Vector(0, 10000), 2, 3,
    ))
    array_obj = pya.ObjectInstPath()
    array_obj.top = top.cell_index()
    array_obj.cv_index = 0
    array_obj.append_path(pya.InstElement(array, -1, -1))
    array_details = describe_selected_waveguides([array_obj], 0)[0]
    assert array_details["copies"] == 6
    assert array_details["length_um"] == 100.0 and array_details["total_length_um"] == 600.0

    curved_instances = []
    for bend in ("Bezier", "Euler"):
        cell = _variant(layout, [(0, 0), (80, 0), (80, 60)], bend)
        instance = top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans()))
        number, length = measure_selected_waveguides(_selection(top, [instance]), 0)
        assert number == 1 and 100.0 < length < 140.0, (bend, length)
        curved_instances.append(instance)
        params = describe_selected_waveguides(_selection(top, [instance]), 0)[0]["parameters"]
        if bend == "Bezier":
            assert params["bezier_k"] == 0.35
            assert abs(params["Bezier_Rmax"] - 36.214286) < 0.000001
            assert abs(params["Bezier_Rmin"] - 14.869640) < 0.000001
        else:
            assert params["Euler_Rmax"] == 30.0 and params["Euler_Rmin"] == 10.0
            assert 10.0 < params["Euler_Reff"] < 30.0

    # 单宽度与复合波导允许混选；普通 cell、Path 和空选择仍拒绝。
    composite = _variant(layout, [(0, 0), (100, 0)], composite=True)
    other = layout.create_cell("OTHER_DEVICE")
    missing = layout.create_cell("Waveguide_legacy_missing_length")
    composite_instance = top.insert(pya.CellInstArray(composite.cell_index(), pya.Trans()))
    assert measure_selected_waveguides(chosen[:1] + _selection(top, [composite_instance]), 0) == (2, 200.0)
    for cell, reason in ((other, "unsupported"), (missing, "missing_length")):
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
        for instance in curved_instances:
            saved_cell = reread.cell(instance.cell.name)
            saved_instance = next(i for i in saved_top.each_inst() if i.cell == saved_cell)
            params = describe_selected_waveguides(_selection(saved_top, [saved_instance]), 0)[0]["parameters"]
            if params["bend_type"] == "Bezier":
                assert params["bezier_k"] == 0.35 and params["radius"] == 20.0
            else:
                assert params["Euler_Rmax"] == 30.0 and params["Euler_Rmin"] == 10.0
                # Euler 的隐藏 radius 不代表其有效半径，不能用它替代 Reff。
                assert abs(params["Euler_Reff"] - 20.0) > 0.1

    legacy = layout.create_cell("Waveguide_legacy_without_B")
    legacy.shapes(layout.layer(10, 0)).insert(pya.Text(
        "Waveguide width=0.350um radius=10.000um bend=Bezier length=50.000um", pya.Trans(),
    ))
    instance = top.insert(pya.CellInstArray(legacy.cell_index(), pya.Trans()))
    legacy_detail = describe_selected_waveguides(_selection(top, [instance]), 0)[0]
    assert legacy_detail["parameters"]["bezier_k"] is None
    assert legacy_detail["length_um"] == 50.0
    print("PASS: lengths, bend parameters, copies, transforms, strict errors and stored GDS", flush=True)


def _composite_checks():
    """用已知直段长度核对 transition、端宽、压缩 taper 和保存重开。"""
    layout = pya.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("COMPOSITE_LENGTH_TEST")
    selected = []

    def measure(points, **params):
        cell = _variant(layout, points, composite=True, **params)
        instance = top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans()))
        obj = _selection(top, [instance])[0]
        selected.append(obj)
        return describe_selected_waveguides([obj], 0)[0]

    route = [(0, 0), (100, 0), (100, 100)]
    detail = measure(route)
    assert detail["kind"] == "composite"
    assert detail["excluded_taper_length_um"] == 40.0
    assert detail["length_by_width_um"][2.0] == 116.0
    assert abs(detail["length_by_width_um"][0.5] - (4.0 + 20.0 * math.pi / 2.0)) < 0.02
    full = detail["length_um"] + 40.0

    narrow_start = measure(route, start_width=0.5)
    assert narrow_start["excluded_taper_length_um"] == 20.0
    assert narrow_start["length_by_width_um"][2.0] == 58.0
    assert abs(narrow_start["length_um"] - (full - 20.0)) < 0.001
    narrow_ports = measure(route, start_width=0.5, end_width=0.5)
    assert narrow_ports["excluded_taper_length_um"] == 0.0
    assert set(narrow_ports["length_by_width_um"]) == {0.5}
    assert abs(narrow_ports["length_um"] - full) < 0.001

    no_taper = measure(route, taper_length=0.0)
    assert no_taper["excluded_taper_length_um"] == 0.0
    assert no_taper["length_by_width_um"][2.0] == 156.0
    equal = measure(route, bend_width=2.0)
    assert equal["excluded_taper_length_um"] == 0.0
    assert set(equal["length_by_width_um"]) == {2.0}
    assert abs(equal["length_um"] - full) < 0.001

    terminal = measure([(0, 0), (100, 0)], start_width=0.5)
    assert terminal["length_by_width_um"] == {2.0: 80.0}
    assert terminal["excluded_taper_length_um"] == 20.0
    narrow_straight = measure([(0, 0), (100, 0)], start_width=0.5, end_width=0.5)
    assert narrow_straight["length_by_width_um"] == {0.5: 100.0}
    compressed = measure([(0, 0), (25, 0), (25, 25)])
    assert abs(compressed["excluded_taper_length_um"] - 8.332) < 1e-9
    assert abs(compressed["length_by_width_um"][2.0] - 0.836) < 1e-9

    for bend in ("Bezier", "Euler"):
        curve = measure(route, bend=bend)
        assert curve["excluded_taper_length_um"] == 40.0
        assert set(curve["length_by_width_um"]) == {0.5, 2.0}
        assert all(length > 0 for length in curve["length_by_width_um"].values())

    # 层级缩放同时改变宽度及长度，不改变 taper 的排除规则。
    cell = selected[0].inst().cell
    scaled = top.insert(pya.CellInstArray(cell.cell_index(), pya.ICplxTrans(2.0, 90, True, 0, 0)))
    scaled_detail = describe_selected_waveguides(_selection(top, [scaled]), 0)[0]
    assert scaled_detail["excluded_taper_length_um"] == 80.0
    assert scaled_detail["length_by_width_um"][4.0] == 232.0
    assert abs(scaled_detail["length_um"] - detail["length_um"] * 2.0) < 0.001

    before = describe_selected_waveguides(selected, 0)
    with tempfile.TemporaryDirectory(prefix="jnu_composite_length_") as directory:
        path = Path(directory) / "composite_lengths.gds"
        options = pya.SaveLayoutOptions()
        options.set_format_from_filename(str(path))
        options.gds2_write_cell_properties = True
        options.write_context_info = False
        layout.write(str(path), options)
        reread = pya.Layout()
        reread.read(str(path))
        saved_top = reread.cell(top.name)
        saved_selection = _selection(saved_top, list(saved_top.each_inst())[:len(selected)])
        after = describe_selected_waveguides(saved_selection, 0)
        for first, saved in zip(before, after):
            assert first["length_by_width_um"] == saved["length_by_width_um"]
            assert first["excluded_taper_length_um"] == saved["excluded_taper_length_um"]
        # PCell 展开后 cell 属性可能丢失，实际转换动作还在实例上保存恢复数据。
        saved_instance = saved_selection[0].inst()
        for key in (RAW_PATH_PROPERTY, RAW_PATH_GDS_PROPERTY):
            value = saved_instance.cell.property(key)
            if value is not None:
                saved_instance.set_property(key, value)
                saved_instance.cell.delete_property(key)
        # 修改实例属性会更新 KLayout 的实例句柄，重新构造选择路径再读取。
        saved_instance = next(
            i for i in saved_top.each_inst()
            if i.cell.name == before[0]["cell_name"] and any(
                i.property(key) is not None for key in (RAW_PATH_PROPERTY, RAW_PATH_GDS_PROPERTY)
            )
        )
        restored = describe_selected_waveguides(_selection(saved_top, [saved_instance]), 0)[0]
        assert restored["length_by_width_um"] == before[0]["length_by_width_um"]
    print("PASS: composite width totals, transitions, taper exclusion, endpoint widths, compression and GDS", flush=True)


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
    original_show_results = action._show_results
    original_exec = action.exec_dialog_with_persisted_size
    action._show_results = lambda title, text: messages.append(("info", title, text))
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
            assert menu_action.title == "计算波导长度 / Calculate Waveguide Length"
            view.object_selection = chosen
            menu_action.trigger()
            assert messages[-1][0:2] == ("info", title)
            assert "200.000" in messages[-1][2]
            assert ("Waveguide width: 0.500 µm" if language == "en" else "波导宽度：0.500 µm") in messages[-1][2]
            assert ("Bend radius R: 20.000 µm" if language == "en" else "弯曲半径 R：20.000 µm") in messages[-1][2]
            assert len(view.object_selection) == len(chosen)
            assert all(obj in view.object_selection for obj in chosen)
            for bend in ("Bezier", "Euler"):
                curve = _variant(cellview.layout(), [(0, 0), (80, 0), (80, 60)], bend)
                curve_instance = top.insert(pya.CellInstArray(curve.cell_index(), pya.Trans()))
                view.object_selection = _selection(top, [curve_instance], cv_index)
                menu_action.trigger()
                report = messages[-1][2]
                assert messages[-1][0:2] == ("info", title)
                if bend == "Bezier":
                    assert "Bezier B: 0.350" in report and "36.214 µm" in report
                else:
                    assert "Euler Rmax: 30.000 µm" in report and "Euler Rmin: 10.000 µm" in report
                    assert ("Effective radius Reff: " if language == "en" else "有效半径 Reff：") in report
                    assert ("Bend radius R: " if language == "en" else "弯曲半径 R：") not in report
            view.object_selection = chosen
            composite = _variant(cellview.layout(), [(0, 0), (100, 0), (100, 100)], composite=True)
            composite_instance = top.insert(pya.CellInstArray(composite.cell_index(), pya.Trans()))
            mixed = chosen + _selection(top, [composite_instance], cv_index)
            view.object_selection = mixed
            menu_action.trigger()
            report = messages[-1][2]
            assert messages[-1][0:2] == ("info", title)
            assert ("taper lengths are excluded" if language == "en" else "taper（宽度渐变段）长度不计入") in report
            assert "116.000 µm" in report and "40.000 µm" in report
            assert len(view.object_selection) == len(mixed)
            other = cellview.layout().create_cell("OTHER_DEVICE")
            invalid = top.insert(pya.CellInstArray(other.cell_index(), pya.Trans()))
            mixed = chosen + _selection(top, [invalid], cv_index)
            view.object_selection = mixed
            menu_action.trigger()
            assert messages[-1][0:2] == ("warning", title)
            assert len(view.object_selection) == len(mixed)
            assert all(obj in view.object_selection for obj in mixed)
        action.pya = original_pya

        def check_dialog(dialog, key, default_size):
            output = dialog.findChild("waveguide_length_output")
            assert _value(output, "readOnly")
            assert output.toPlainText() == report
            assert _value(_value(output, "font"), "pointSize") == 11
            assert key == "calculate_waveguide_length"
            dialog.resize(*default_size)
            timer = pya.QTimer(dialog)
            timer.setSingleShot(True)
            timer.timeout(dialog.accept)
            timer.start(0)
            return dialog.exec_()

        action.exec_dialog_with_persisted_size = check_dialog
        original_show_results("计算波导长度", report)
        print("PASS: English/Chinese menu reports, strict errors and actual read-only Qt result dialog", flush=True)
    finally:
        action.pya = original_pya
        action._show_results = original_show_results
        action.exec_dialog_with_persisted_size = original_exec


if __name__ == "__main__":
    _database_checks()
    _composite_checks()
    if hasattr(pya, "Application"):
        _gui_checks()
