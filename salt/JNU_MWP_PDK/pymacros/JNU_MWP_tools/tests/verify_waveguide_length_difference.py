# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""验证两组多选长度差、非模态选取、整次取消、GDS 重读及双语菜单。"""

import builtins
from pathlib import Path
import re
import sys
import tempfile

import pya


TEST_DIR = Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

from verify_waveguide_length import PYMACROS, _fixture, _selection, _spiral_fixture, _variant  # noqa: E402
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


def _spiral_checks():
    layout = pya.Layout()
    top, waveguides = _fixture(layout)
    spirals, composite = _spiral_fixture(layout, top)
    # 从器件实际总长标注取得独立预期，不能使用内直段长度或目标长度。
    lengths = []
    for instance in spirals:
        values = [float(match.group(1))
                  for shape in instance.cell.shapes(layout.layer(10, 0)).each() if shape.is_text()
                  for match in re.finditer(r"\bL=([0-9.]+)um\b", shape.text.string)]
        assert len(values) == 1
        lengths.append(values[0])
        assert values[0] > instance.cell.pcell_parameters_by_name()["length"]
    for index, bend in enumerate(("Circular", "Bezier", "Euler")):
        details, difference = compare_selected_waveguides(_selection(top, [spirals[index], spirals[index + 3]]), 0)
        assert [item["kind"] for item in details] == ["paperclip", "archimedean"]
        assert [item["length_um"] for item in details] == [lengths[index], lengths[index + 3]]
        assert all(item["parameters"]["width"] == 0.7 and item["parameters"]["bend_type"] == bend for item in details)
        assert difference == abs(lengths[index] - lengths[index + 3])
    for index, spiral in enumerate(spirals):
        details, difference = compare_selected_waveguides(_selection(top, [waveguides[0], spiral]), 0)
        assert difference == abs(100.0 - lengths[index])
    # 同类、跨类型和反向顺序均可比较，复合 Spiral 优先于数量检查整批拒绝。
    for indices in ((0, 1), (3, 4), (4, 1)):
        assert compare_selected_waveguides(_selection(top, [spirals[i] for i in indices]), 0)[1] == abs(
            lengths[indices[0]] - lengths[indices[1]])
    for group in ([composite], [spirals[0], composite], [composite, spirals[3]],
                  [waveguides[0], spirals[0], composite]):
        _reject(_selection(top, group), "composite_spiral")

    with tempfile.TemporaryDirectory(prefix="jnu_spiral_difference_") as directory:
        for context in (True, False):
            path = Path(directory) / ("context.gds" if context else "plain.gds")
            options = pya.SaveLayoutOptions()
            options.set_format_from_filename(str(path))
            options.write_context_info = context
            layout.write(str(path), options)
            saved = pya.Layout()
            saved.read(str(path))
            saved_top = saved.cell(top.name)
            saved_instances = list(saved_top.each_inst())
            saved_spirals = saved_instances[len(waveguides):len(waveguides) + len(spirals)]
            for index in range(3):
                details, difference = compare_selected_waveguides(_selection(
                    saved_top, [saved_spirals[index], saved_spirals[index + 3]]), 0)
                assert [item["length_um"] for item in details] == [lengths[index], lengths[index + 3]]
                assert difference == abs(lengths[index] - lengths[index + 3])
                assert all(abs(item["parameters"]["width"] - 0.7) < 1e-12 for item in details)
            _reject(_selection(saved_top, [saved_spirals[0], saved_instances[-1]]), "composite_spiral")
    print("PASS: ordinary Spiral differences, Waveguide mixing, actual lengths, parameters, composite cancellation and context/plain GDS", flush=True)


def _gui_checks():
    from JNU_MWP_tools.actions import calculate_waveguide_length as length_action
    from JNU_MWP_tools.actions import calculate_waveguide_length_difference as action
    from JNU_MWP_tools.actions import startup_update
    from JNU_MWP_tools.core import ui_language

    window = pya.Application.instance().main_window()
    if window is None:
        return
    original_warning, original_show = action._warning, action._show_results
    original_exec = length_action.exec_dialog_with_persisted_size
    original_schedule = startup_update.schedule_startup_update_check
    messages = []
    action._warning = lambda title, text: messages.append(("warning", title, text, None))
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
        spirals, composite_spiral = _spiral_fixture(layout, top)
        other = layout.create_cell("OTHER_DEVICE")
        invalid = top.insert(pya.CellInstArray(other.cell_index(), pya.Trans()))
        array = top.insert(pya.CellInstArray(
            instances[0].cell_index, pya.Trans(), pya.Vector(150000, 0), pya.Vector(0, 10000), 2, 3,
        ))
        array_obj = pya.ObjectInstPath()
        array_obj.top = top.cell_index()
        array_obj.cv_index = cv_index
        array_obj.append_path(pya.InstElement(array, -1, -1))
        cell_count = layout.cells()
        instance_count = sum(1 for _ in top.each_inst())
        macro = pya.Macro(str(PYMACROS / "JNU_MWP_PDK_Menu.lym"))

        def start(menu_action):
            count = len(messages)
            if hasattr(view, "switch_mode"):
                view.switch_mode("path")
            menu_action.trigger()
            session = action._selection_session
            assert session is not None and _value(session.dialog, "visible")
            assert not _value(session.dialog, "modal") and _value(window, "enabled")
            if hasattr(view, "mode_name"):
                assert _value(view, "mode_name") == "select"
            assert len(messages) == count
            assert ("first group" if language == "en" else "第一组") in session.prompt.text
            menu_action.trigger()
            assert action._selection_session is session
            return session

        def compare(menu_action, group1, group2):
            session = start(menu_action)
            view.object_selection = _selection(top, group1, cv_index)
            session.confirm.click()
            assert action._selection_session is session and len(session.groups) == 1
            assert len(view.object_selection) == 0
            assert ("second group" if language == "en" else "第二组") in session.prompt.text
            chosen = _selection(top, group2, cv_index)
            view.object_selection = chosen
            session.confirm.click()
            assert action._selection_session is None
            assert messages[-1][0:2] == ("info", title)
            assert all(obj in view.object_selection for obj in chosen) and len(view.object_selection) == len(chosen)
            assert messages[-1][3] == "calculate_waveguide_length_difference"
            return messages[-1][2]

        for language, title in (("en", "Calculate Waveguide Length Difference"), ("zh_CN", "计算波导长度差")):
            setattr(builtins, ui_language._SESSION_KEY, language)
            macro.run()
            macro.run()
            assert len(window._jnu_menu_actions) == 14
            assert len({str(item.title) for item in window._jnu_menu_actions}) == 14
            menu_action = window.menu().action("jnu_mwp_pdk_menu.waveguides.jnu_action_calculate_waveguide_length_difference")
            assert menu_action.title == "计算波导长度差 / Calculate Waveguide Length Difference"
            report = compare(menu_action, instances[:2], [instances[0], long_instance])
            assert "|L1 − L2|" in report and "20.000 µm" in report and "0.020000 mm" in report
            assert "200.000 µm" in report and "220.000 µm" in report
            assert "100.000 µm" in report and "120.000 µm" in report
            assert ("Waveguide width: 0.800 µm" if language == "en" else "波导宽度：0.800 µm") in report
            assert ("Bend radius R: 20.000 µm" if language == "en" else "弯曲半径 R：20.000 µm") in report
            report = compare(menu_action, [instances[0], composite_instance], [long_instance])
            assert ("taper lengths are excluded" if language == "en" else "taper（宽度渐变段）长度不计入") in report
            assert "116.000" in report and "40.000 µm" in report
            assert ("Comparison by width" if language == "en" else "按宽度比较") in report
            for group in ([spirals[1], spirals[4]], [instances[0], spirals[0]], [spirals[3], spirals[4]]):
                report = compare(menu_action, group, [long_instance, instances[0]])
                assert "|L1 − L2|" in report
                assert ("Waveguide width: 0.700 µm" if language == "en" else "波导宽度：0.700 µm") in report
                for instance in group:
                    if "Paperclip" in instance.cell.name:
                        assert ("Paperclip Spiral" if language == "en" else "回形针 Spiral") in report
                    elif "Archimedean" in instance.cell.name:
                        assert ("Archimedean Spiral" if language == "en" else "阿基米德 Spiral") in report
                if group == [spirals[1], spirals[4]]:
                    assert "Bezier B: 0.400" in report
            # 整个阵列按实际副本计入，不再受旧版两个实例限制。
            session = start(menu_action)
            view.object_selection = [array_obj]
            session.confirm.click()
            assert action._group_length(session.groups[0]) == 600.0
            view.object_selection = _selection(top, instances[:2], cv_index)
            session.confirm.click()
            assert "600.000 µm" in messages[-1][2] and "400.000 µm" in messages[-1][2]
            # 第一组和第二组的非法器件都取消整次计算，不产生部分结果。
            for stage in (0, 1):
                for group in ([composite_spiral], [spirals[0], composite_spiral], [instances[0], invalid]):
                    session = start(menu_action)
                    if stage:
                        view.object_selection = _selection(top, instances[:2], cv_index)
                        session.confirm.click()
                    chosen = _selection(top, group, cv_index)
                    view.object_selection = chosen
                    count_before = len(messages)
                    session.confirm.click()
                    assert action._selection_session is None and len(messages) == count_before + 1
                    assert messages[-1][0:2] == ("warning", title)
                    if composite_spiral in group:
                        assert ("entire calculation was cancelled" if language == "en" else "已取消整次计算") in messages[-1][2]
                    assert len(view.object_selection) == len(chosen)
            # 空组不消费当前步骤；取消按钮和关闭窗口均不显示结果。
            for stage in (0, 1):
                session = start(menu_action)
                if stage:
                    view.object_selection = _selection(top, instances[:1], cv_index)
                    session.confirm.click()
                view.object_selection = []
                session.confirm.click()
                assert messages[-1][0:2] == ("warning", title)
                assert action._selection_session is session and len(session.groups) == stage
                count_before = len(messages)
                if stage:
                    session.dialog.close()
                else:
                    session.dialog.reject()
                assert action._selection_session is None and len(messages) == count_before
            # 选取中切换编辑 cell 后不混合两套上下文。
            session = start(menu_action)
            view.object_selection = _selection(top, instances[:1], cv_index)
            session.confirm.click()
            cellview.cell = other
            session.confirm.click()
            assert action._selection_session is None and messages[-1][0] == "warning"
            cellview.cell = top

        assert layout.cells() == cell_count and sum(1 for _ in top.each_inst()) == instance_count

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
        print("PASS: bilingual two-stage modeless groups, totals, arrays, empty retry, cancellation, context guard and native Qt results", flush=True)
    finally:
        if action._selection_session is not None:
            action._selection_session.dialog.reject()
        action._warning, action._show_results = original_warning, original_show
        length_action.exec_dialog_with_persisted_size = original_exec
        startup_update.schedule_startup_update_check = original_schedule


if __name__ == "__main__":
    _database_checks()
    _spiral_checks()
    if hasattr(pya, "Application"):
        _gui_checks()
