# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""JNU_MWP_PDK 的按层交互式 DRC 参数窗口。"""

import html
import os
import tempfile

import pya

from JNU_MWP_tools.core.gui_state import exec_dialog_with_persisted_size


TOOL_TITLE = "JNU MWP DRC"

# 每项都是界面、规则组合和回归测试共用的唯一默认来源。图层变量和中文
# 名称固定，用户每次仅临时修改 source specification 与规则表达式文本。
LAYER_DRC_SPECS = (
    {
        "key": "si",
        "variable": "LayerSi",
        "label": "硅波导层",
        "source": "input(1,0)",
        "checked": True,
        "rules": "\n".join((
            'LayerSi.width(0.06-tol, angle_limit(80)).output("硅宽度违规", "硅最小宽度违规，最小要求 60 nm")',
            'LayerSi.space(0.04-tol, angle_limit(80)).output("硅间距违规", "硅最小间距违规，最小要求 40 nm")',
        )),
    },
    {
        "key": "si_rib",
        "variable": "LayerSi_rib",
        "label": "脊型硅层",
        "source": "input(2,0)",
        "checked": False,
        "rules": "",
    },
    {
        "key": "devrec",
        "variable": "DevRec",
        "label": "器件识别层",
        "source": "input(68,0)",
        "checked": False,
        "rules": "",
    },
    {
        "key": "pinrec",
        "variable": "PinRec",
        "label": "端口/引脚层",
        "source": "input(1,10)",
        "checked": True,
        "rules": 'PinRec.not_inside(LayerSi).output("波导断开警告", "可能存在波导不匹配或断开：端口必须包裹硅材料")',
    },
    {
        "key": "floorplan",
        "variable": "LayerFP",
        "label": "版图边界层",
        "source": "input(99)",
        "checked": False,
        "rules": "",
    },
    {
        "key": "m1",
        "variable": "LayerM1",
        "label": "金属1层",
        "source": "input(11,0)",
        "checked": True,
        "rules": "\n".join((
            'LayerM1.width(1.0-tol, angle_limit(70)).output("M1宽度违规", "M1最小宽度违规，最小要求 1 µm")',
            'LayerM1.space(6.0-tol).output("M1间距违规", "M1最小间距违规，最小要求 5 µm")',
        )),
    },
    {
        "key": "m2",
        "variable": "LayerM2",
        "label": "金属2层",
        "source": "input(12,0)",
        "checked": True,
        "rules": "\n".join((
            'LayerM2.width(10.0-tol, angle_limit(70)).output("M2宽度违规", "M2最小宽度违规，最小要求 10 µm")',
            'LayerM2.space(6.0-tol).output("M2间距违规", "M2最小间距违规，最小要求 6 µm")',
            'LayerM2.overlap(LayerM1,3.0-tol).output("M2与M1重叠违规", "M2与M1最小重叠违规，最小要求 3 µm")',
        )),
    },
    {
        "key": "ml_open",
        "variable": "LayerMLOpen",
        "label": "金属焊盘开口层",
        "source": "input(13,0)",
        "checked": False,
        "rules": "",
    },
    {
        "key": "deep_trench",
        "variable": "LayerDeepTrench",
        "label": "深槽隔离层",
        "source": "input(40,0)",
        "checked": True,
        "rules": "\n".join((
            'LayerDeepTrench.separation(LayerM1, 12.0-tol).output("深槽与金属间距违规", "深槽与金属最小间距违规，最小要求 12 µm")',
            'LayerDeepTrench.separation(LayerM2, 20.0-tol).output("深槽与金属间距违规", "深槽与金属最小间距违规，最小要求 12 µm")',
        )),
    },
)


DEFAULT_GLOBAL_DRC_PARAMETERS = """# 全局 DRC 参数
# 容差用于避免曲线波导的临界尺寸误报。
tol = 2e-3
"""


def default_layer_settings():
    """返回一份可修改的九层默认设置副本。"""
    return [dict(spec) for spec in LAYER_DRC_SPECS]


def _normalize_layer_settings(layer_settings):
    """按固定图层顺序验证并规范化临时界面设置。"""
    try:
        received = list(layer_settings)
    except TypeError:
        raise ValueError("图层设置必须包含全部默认图层。")
    if len(received) != len(LAYER_DRC_SPECS):
        raise ValueError("图层设置数量与默认图层定义不一致。")

    normalized = []
    for spec, item in zip(LAYER_DRC_SPECS, received):
        if not isinstance(item, dict) or item.get("key") != spec["key"]:
            raise ValueError("图层设置顺序或标识不正确。")
        source = str(item.get("source", "")).strip()
        if not source:
            raise ValueError("%s 的 Source Specification 不能为空。" % spec["label"])
        normalized.append({
            "key": spec["key"],
            "variable": spec["variable"],
            "label": spec["label"],
            "source": source,
            "checked": bool(item.get("checked", False)),
            "rules": str(item.get("rules", "")).strip(),
        })
    return normalized


def build_layer_definitions(layer_settings):
    """把左栏 Source Specification 表单组合为 DRC DSL 图层定义。"""
    settings = _normalize_layer_settings(layer_settings)
    lines = ["# 图层定义"]
    for setting in settings:
        lines.append(
            "%s = %s  # %s" % (
                setting["variable"], setting["source"], setting["label"],
            )
        )
    return "\n".join(lines)


def build_selected_drc_rules(global_parameters, layer_settings):
    """组合全局参数和右栏所有已勾选图层的 DRC DSL 表达式。"""
    settings = _normalize_layer_settings(layer_settings)
    sections = []
    global_text = str(global_parameters or "").strip()
    if global_text:
        sections.append(global_text)
    for setting in settings:
        if not setting["checked"]:
            continue
        if not setting["rules"]:
            raise ValueError(
                "%s 已勾选 Rules to Check，但 DRC 规则参数为空。" % setting["label"]
            )
        sections.append("# %s DRC 规则\n%s" % (
            setting["label"], setting["rules"],
        ))
    if not sections:
        return "# 未选择任何 DRC 规则。"
    return "\n\n".join(sections)


def _drc_string_literal(value):
    """把文件路径或 Cell 名称编码成 DRC DSL 的双引号字符串。"""
    return '"%s"' % str(value).replace("\\", "/").replace('"', '\\"')


def build_drc_text(
    layer_definitions, drc_rules, source_filename=None,
    top_cell_name=None, report_filename=None,
):
    """组合当前对话框设置为可执行 DRC DSL，并检查必填输入。"""
    layers = str(layer_definitions or "").strip()
    rules = str(drc_rules or "").strip()
    if not layers:
        raise ValueError("图层定义不能为空。")
    if not rules:
        raise ValueError("DRC 规则不能为空。")
    has_explicit_io = any(value is not None for value in (
        source_filename, top_cell_name, report_filename,
    ))
    if has_explicit_io and not all(value is not None for value in (
        source_filename, top_cell_name, report_filename,
    )):
        raise ValueError("DRC 的输入版图、顶层 Cell 与报告路径必须同时提供。")
    if has_explicit_io:
        source_line = "source(%s, %s)" % (
            _drc_string_literal(source_filename),
            _drc_string_literal(top_cell_name),
        )
        report_line = "report(\"JNU MWP 设计规则检查\", %s)" % (
            _drc_string_literal(report_filename),
        )
    else:
        source_line = "source($input, $input.top_cell)"
        report_line = 'report("JNU MWP 设计规则检查", $output)'
    return "\n\n".join((
        "# DRC 输入版图、顶层 Cell 和报告输出。",
        source_line,
        report_line,
        layers,
        rules,
        "",
    ))


def build_drc_macro_xml(drc_text):
    """把 DRC DSL 封装为临时 .lydrc 文件可执行的 XML 宏。"""
    escaped_text = html.escape(str(drc_text), quote=False)
    return """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<klayout-macro>
 <description>JNU MWP temporary interactive DRC</description>
 <version/>
 <category>drc</category>
 <prolog/>
 <epilog/>
 <doc/>
 <autorun>false</autorun>
 <autorun-early>false</autorun-early>
 <priority>0</priority>
 <shortcut/>
 <show-in-menu>false</show-in-menu>
 <group-name>drc_scripts</group-name>
 <menu-path/>
 <interpreter>dsl</interpreter>
 <dsl-interpreter-name>drc-dsl-xml</dsl-interpreter-name>
 <text>%s</text>
</klayout-macro>
""" % escaped_text


def write_temporary_drc_macro(drc_text):
    """写入一次性 DRC 宏，调用方执行结束后必须删除返回的文件。"""
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".lydrc", prefix="jnu_mwp_drc_",
        delete=False,
    )
    try:
        handle.write(build_drc_macro_xml(drc_text))
        return handle.name
    finally:
        handle.close()


def _main_window():
    """取得当前 KLayout 主窗口，供 DRC 对话框附着。"""
    return pya.Application.instance().main_window()


def _current_layout_view_context():
    """取得当前 view、layout、用于 DRC 的顶层 Cell 与活动 Cell 索引。"""
    main_window = _main_window()
    view = main_window.current_view() if main_window is not None else None
    if view is None:
        raise RuntimeError("请先打开版图后再运行 DRC。")
    cellview = view.active_cellview()
    if cellview is None:
        raise RuntimeError("当前视图没有可用于 DRC 的版图。")
    layout = cellview.layout()
    if layout is None:
        raise RuntimeError("当前视图没有可用于 DRC 的版图。")
    top_cells = list(layout.top_cells())
    if not top_cells:
        raise RuntimeError("当前版图没有顶层 Cell。")
    top_cell = sorted(top_cells, key=lambda cell: str(cell.name))[0]
    return view, cellview, layout, top_cell


def _load_report_into_view(view, cellview, report_path, top_cell_name):
    """把临时 DRC 报告读入当前 Marker Browser 并显示在活动 CellView。"""
    if not os.path.isfile(report_path):
        raise RuntimeError("DRC 没有生成报告文件。")
    report_id = view.create_rdb("JNU MWP DRC")
    report_database = view.rdb(report_id)
    report_database.load(report_path)
    report_database.top_cell_name = str(top_cell_name)
    report_database.create_cell(str(top_cell_name))
    view.show_rdb(report_id, cellview.cell_index)


def _plain_text(editor):
    """兼容读取 QPlainTextEdit 的文本。"""
    value = getattr(editor, "toPlainText")
    return value() if callable(value) else value


def _line_text(editor):
    """兼容读取 QLineEdit 的文本。"""
    value = getattr(editor, "text")
    return value() if callable(value) else value


def _header_label(text, parent):
    """创建表格列标题，保持普通控件字体而非全局样式放大。"""
    label = pya.QLabel(text, parent)
    label.setStyleSheet("font-weight: bold;")
    return label


def _layer_definition_group(parent):
    """建立左侧固定层名与可编辑 Source Specification 表格。"""
    group = pya.QGroupBox("Layer Definitions", parent)
    layout = pya.QGridLayout(group)
    group.setLayout(layout)
    layout.addWidget(_header_label("Layer", group), 0, 0)
    layout.addWidget(_header_label("Source Specification", group), 0, 1)
    source_editors = {}
    for row, spec in enumerate(LAYER_DRC_SPECS, start=1):
        layout.addWidget(pya.QLabel(spec["label"], group), row, 0)
        editor = pya.QLineEdit(group)
        editor.setText(spec["source"])
        layout.addWidget(editor, row, 1)
        source_editors[spec["key"]] = editor
    return group, source_editors


def _global_parameters_group(parent):
    """建立右侧规则区域的公共 DRC 参数输入框。"""
    group = pya.QGroupBox("Global DRC Parameters [editable]", parent)
    layout = pya.QVBoxLayout(group)
    group.setLayout(layout)
    hint = pya.QLabel("在所有已勾选图层的规则前执行。", group)
    layout.addWidget(hint)
    editor = pya.QPlainTextEdit(group)
    editor.setPlainText(DEFAULT_GLOBAL_DRC_PARAMETERS)
    editor.setFixedHeight(52)
    layout.addWidget(editor)
    return group, editor


def _layer_rules_group(parent):
    """建立右侧按层勾选和可编辑 DRC DSL 参数表格。"""
    group = pya.QGroupBox("DRC Rules", parent)
    layout = pya.QGridLayout(group)
    group.setLayout(layout)
    layout.addWidget(_header_label("Rules to Check", group), 0, 0)
    layout.addWidget(_header_label("Layer", group), 0, 1)
    layout.addWidget(_header_label("DRC Rule Parameters", group), 0, 2)
    rule_controls = {}
    for row, spec in enumerate(LAYER_DRC_SPECS, start=1):
        check_box = pya.QCheckBox(group)
        check_box.setChecked(spec["checked"])
        check_box.setToolTip("勾选后对该层运行右侧规则参数。")
        layout.addWidget(check_box, row, 0)
        layout.addWidget(pya.QLabel(spec["label"], group), row, 1)
        editor = pya.QPlainTextEdit(group)
        editor.setPlainText(spec["rules"])
        editor.setFixedHeight(54)
        layout.addWidget(editor, row, 2)
        rule_controls[spec["key"]] = (check_box, editor)
    return group, rule_controls


def _collect_dialog_settings(source_editors, global_editor, rule_controls):
    """从表单读取本次 DRC 所需的临时设置，不触发任何持久化。"""
    settings = []
    for spec in LAYER_DRC_SPECS:
        check_box, rule_editor = rule_controls[spec["key"]]
        settings.append({
            "key": spec["key"],
            "source": _line_text(source_editors[spec["key"]]),
            "checked": check_box.isChecked(),
            "rules": _plain_text(rule_editor),
        })
    return {
        "layers": settings,
        "global_parameters": _plain_text(global_editor),
    }


def create_drc_dialog():
    """创建 DRC 对话框及控件，不执行 DRC，便于 GUI 回归检查。"""
    dialog = pya.QDialog(_main_window())
    dialog.setWindowTitle(TOOL_TITLE)

    root_layout = pya.QVBoxLayout(dialog)
    dialog.setLayout(root_layout)
    info = pya.QLabel(
        "左侧编辑每层 Source Specification；右侧勾选需要检查的层并编辑完整 DRC DSL 规则。\n"
        "所有内容仅对本次 OK 生效；关闭窗口后恢复默认。",
        dialog,
    )
    info.setWordWrap(True)
    root_layout.addWidget(info)

    columns = pya.QHBoxLayout(dialog)
    layer_group, source_editors = _layer_definition_group(dialog)
    global_group, global_editor = _global_parameters_group(dialog)
    rules_group, rule_controls = _layer_rules_group(dialog)
    right_column = pya.QVBoxLayout(dialog)
    right_column.addWidget(global_group)
    right_column.addWidget(rules_group, 1)
    columns.addWidget(layer_group, 1)
    columns.addLayout(right_column, 2)
    root_layout.addLayout(columns)

    buttons = pya.QHBoxLayout(dialog)
    ok_button = pya.QPushButton("OK", dialog)
    cancel_button = pya.QPushButton("Cancel", dialog)
    ok_button.clicked(lambda _checked: dialog.accept())
    cancel_button.clicked(lambda _checked: dialog.reject())
    buttons.addWidget(ok_button)
    buttons.addWidget(cancel_button)
    root_layout.addLayout(buttons)
    return dialog, source_editors, global_editor, rule_controls


def show_drc_dialog():
    """显示按层 DRC 设置窗口，取消时返回 ``None``。"""
    dialog, source_editors, global_editor, rule_controls = create_drc_dialog()
    if exec_dialog_with_persisted_size(
        dialog, "jnu_mwp_drc", default_size=(1440, 820),
    ) == 0:
        return None
    return _collect_dialog_settings(source_editors, global_editor, rule_controls)


def run_drc():
    """取得本次按层设置并执行 DRC，不修改默认规则文件。"""
    settings = show_drc_dialog()
    if settings is None:
        return False
    try:
        layer_definitions = build_layer_definitions(settings["layers"])
        selected_rules = build_selected_drc_rules(
            settings["global_parameters"], settings["layers"],
        )
        view, cellview, layout, top_cell = _current_layout_view_context()
    except (RuntimeError, ValueError) as error:
        pya.MessageBox.warning(TOOL_TITLE, str(error), pya.MessageBox.Ok)
        return False

    # DRC DSL 独立执行时不会继承 GUI 的 $input/$output。先将当前内存版图
    # 写入临时 GDS，再显式 source/report，并在结果显示后清理临时文件。
    with tempfile.TemporaryDirectory(prefix="jnu_mwp_drc_run_") as directory:
        input_path = os.path.join(directory, "input.gds")
        report_path = os.path.join(directory, "result.lyrdb")
        temporary_macro = None
        try:
            layout.write(input_path)
            drc_text = build_drc_text(
                layer_definitions, selected_rules,
                input_path, top_cell.name, report_path,
            )
            temporary_macro = write_temporary_drc_macro(drc_text)
            pya.Macro(temporary_macro).run()
            _load_report_into_view(view, cellview, report_path, top_cell.name)
            return True
        except Exception as error:
            pya.MessageBox.warning(
                TOOL_TITLE,
                "DRC 执行失败：\n%s" % error,
                pya.MessageBox.Ok,
            )
            return False
        finally:
            if temporary_macro and os.path.isfile(temporary_macro):
                try:
                    os.remove(temporary_macro)
                except OSError:
                    pass


__all__ = [
    "LAYER_DRC_SPECS",
    "DEFAULT_GLOBAL_DRC_PARAMETERS",
    "default_layer_settings",
    "build_layer_definitions",
    "build_selected_drc_rules",
    "build_drc_text",
    "build_drc_macro_xml",
    "write_temporary_drc_macro",
    "create_drc_dialog",
    "show_drc_dialog",
    "run_drc",
]
