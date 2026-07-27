# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""验证按层 DRC 参数界面的临时规则组合与实际执行。"""

import os
import sys
import tempfile
import xml.etree.ElementTree as ET

import pya


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PYMACROS_DIR = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
if PYMACROS_DIR not in sys.path:
    sys.path.insert(0, PYMACROS_DIR)

from JNU_MWP_tools.actions import drc


def _expect_value_error(callback, message):
    try:
        callback()
    except ValueError:
        return
    raise AssertionError(message)


def _setting_by_key(settings, key):
    for setting in settings:
        if setting["key"] == key:
            return setting
    raise AssertionError("未找到图层设置：%s" % key)


def main():
    defaults = drc.default_layer_settings()
    expected_keys = [spec["key"] for spec in drc.LAYER_DRC_SPECS]
    assert [setting["key"] for setting in defaults] == expected_keys
    assert len(defaults) == 9
    assert _setting_by_key(defaults, "si")["source"] == "input(1,0)"
    assert _setting_by_key(defaults, "pinrec")["source"] == "input(1,10)"
    assert _setting_by_key(defaults, "deep_trench")["source"] == "input(40,0)"

    checked_keys = [setting["key"] for setting in defaults if setting["checked"]]
    assert checked_keys == ["si", "pinrec", "m1", "m2", "deep_trench"]
    assert not _setting_by_key(defaults, "si_rib")["checked"]
    assert not _setting_by_key(defaults, "devrec")["checked"]
    assert not _setting_by_key(defaults, "floorplan")["checked"]
    assert not _setting_by_key(defaults, "ml_open")["checked"]

    layer_definitions = drc.build_layer_definitions(defaults)
    assert "LayerSi = input(1,0)" in layer_definitions
    assert "LayerM2 = input(12,0)" in layer_definitions
    assert "LayerDeepTrench = input(40,0)" in layer_definitions

    selected_rules = drc.build_selected_drc_rules(
        drc.DEFAULT_GLOBAL_DRC_PARAMETERS, defaults,
    )
    assert "tol = 2e-3" in selected_rules
    assert "LayerSi.width" in selected_rules
    assert "LayerM2.overlap(LayerM1" in selected_rules
    assert "PinRec.not_inside" in selected_rules
    assert "LayerDeepTrench.separation" in selected_rules

    without_m2 = drc.default_layer_settings()
    _setting_by_key(without_m2, "m2")["checked"] = False
    without_m2_rules = drc.build_selected_drc_rules(
        drc.DEFAULT_GLOBAL_DRC_PARAMETERS, without_m2,
    )
    assert "LayerM2.width" not in without_m2_rules
    assert "LayerM2.overlap" not in without_m2_rules
    assert "LayerM1.width" in without_m2_rules

    custom_si_rib = drc.default_layer_settings()
    rib = _setting_by_key(custom_si_rib, "si_rib")
    rib["checked"] = True
    rib["rules"] = 'LayerSi_rib.width(0.10).output("脊型硅宽度违规", "最小要求 100 nm")'
    custom_rules = drc.build_selected_drc_rules("", custom_si_rib)
    assert "LayerSi_rib.width" in custom_rules

    missing_source = drc.default_layer_settings()
    _setting_by_key(missing_source, "si")["source"] = ""
    _expect_value_error(
        lambda: drc.build_layer_definitions(missing_source),
        "空 Source Specification 必须被拒绝。",
    )

    missing_rule = drc.default_layer_settings()
    _setting_by_key(missing_rule, "devrec")["checked"] = True
    _expect_value_error(
        lambda: drc.build_selected_drc_rules("", missing_rule),
        "勾选但规则为空的图层必须被拒绝。",
    )

    edited = drc.default_layer_settings()
    _setting_by_key(edited, "si")["source"] = "input(101,7)"
    text = drc.build_drc_text(
        drc.build_layer_definitions(edited),
        drc.build_selected_drc_rules(drc.DEFAULT_GLOBAL_DRC_PARAMETERS, edited),
    )
    assert "LayerSi = input(101,7)" in text
    assert text.index("LayerSi =") < text.index("LayerSi.width")

    xml_text = drc.build_drc_macro_xml(text)
    root = ET.fromstring(xml_text)
    assert root.findtext("interpreter") == "dsl"
    assert root.findtext("dsl-interpreter-name") == "drc-dsl-xml"
    assert root.findtext("text") == text

    temporary = drc.write_temporary_drc_macro(text)
    try:
        assert os.path.isfile(temporary)
        with open(temporary, "r", encoding="utf-8") as stream:
            assert ET.fromstring(stream.read()).findtext("text") == text
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)

    # 使用显式 source/report 实际执行临时宏，确认每层表单能生成可运行 DRC。
    with tempfile.TemporaryDirectory(prefix="jnu_drc_input_") as directory:
        gds_path = os.path.join(directory, "input.gds")
        report_path = os.path.join(directory, "result.lyrdb")
        input_layout = pya.Layout()
        input_layout.dbu = 0.001
        top = input_layout.create_cell("TOP")
        top.shapes(input_layout.layer(1, 0)).insert(pya.Box(0, 0, 1000, 1000))
        input_layout.write(gds_path)
        temporary = drc.write_temporary_drc_macro(
            drc.build_drc_text(
                layer_definitions, selected_rules, gds_path, "TOP", report_path,
            )
        )
        try:
            pya.Macro(temporary).run()
            assert os.path.isfile(report_path), "临时 DRC 未输出报告。"
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)

    # 用替身对话框覆盖用户交互，完整验证 OK 分支会载入 RDB 到当前 LayoutView。
    main_window = pya.Application.instance().main_window()
    if main_window is not None:
        cellview = main_window.create_layout(1)
        view = main_window.current_view()
        layout = cellview.layout()
        layout.dbu = 0.001
        top = layout.create_cell("JNU_DRC_DIALOG_RUN")
        top.shapes(layout.layer(1, 0)).insert(pya.Box(0, 0, 1000, 1000))
        view.select_cell(top.cell_index(), 0)
        original_dialog = drc.show_drc_dialog
        try:
            drc.show_drc_dialog = lambda: {
                "layers": drc.default_layer_settings(),
                "global_parameters": drc.DEFAULT_GLOBAL_DRC_PARAMETERS,
            }
            assert drc.run_drc(), "OK 分支未成功执行 DRC。"
        finally:
            drc.show_drc_dialog = original_dialog

        dialog, source_editors, global_editor, rule_controls = drc.create_drc_dialog()
        try:
            assert len(source_editors) == 9
            assert len(rule_controls) == 9
            assert drc._line_text(source_editors["si"]) == "input(1,0)"
            assert drc._line_text(source_editors["m2"]) == "input(12,0)"
            assert global_editor.toPlainText() == drc.DEFAULT_GLOBAL_DRC_PARAMETERS
            assert rule_controls["si"][0].isChecked()
            assert not rule_controls["si_rib"][0].isChecked()
            assert rule_controls["deep_trench"][0].isChecked()
        finally:
            dialog.close()

    # 表单不读取或写入内容设置；下一次调用重新得到未修改的默认值。
    fresh_defaults = drc.default_layer_settings()
    assert _setting_by_key(fresh_defaults, "si")["source"] == "input(1,0)"
    assert _setting_by_key(fresh_defaults, "m2")["checked"]
    print("OK: layer-based interactive DRC settings and execution")


if __name__ == "__main__":
    main()
