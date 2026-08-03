# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-08

"""JNU_MWP_PDK 的原生 Macro Development DRC 编辑与当前 Cell 执行工具。"""

import html
import os
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET

import pya


TOOL_TITLE = "JNU MWP DRC"
_RULE_CODE_TAG = "text"
_RESERVED_DSL_COMMANDS = ("source", "report")
_MACRO_DEVELOPMENT_ACTION = "macros_menu.macro_development"
_DEFAULT_REPORT_TITLE = "JNU MWP 设计规则检查"
_DEFAULT_REPORT_STATEMENT = 'report("%s")' % _DEFAULT_REPORT_TITLE


def drc_macro_path():
    """返回随 PDK 安装的、持久保存 DRC DSL 规则的宏文件路径。"""
    return Path(__file__).resolve().parents[3] / "drc" / "JNU_MWP_DRC.lydrc"


def _normalise_drc_code(code):
    """统一 DRC DSL 换行和末尾换行，避免保存后产生无意义差异。"""
    return str(code or "").replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"


def _is_single_argument_report(statement):
    """判断是否为原生 Macro Development 允许的单参数 report() 语句。"""
    return re.match(r'^report\s*\(\s*"(?:[^"\\]|\\.)*"\s*\)\s*$', statement) is not None


def _strip_single_argument_report(code):
    """移除原生编辑器的 report()，供当前 Cell 运行器注入临时报告路径。"""
    remaining = []
    for line in _normalise_drc_code(code).splitlines():
        statement = line.split("#", 1)[0].strip().lower()
        if _is_single_argument_report(statement):
            continue
        remaining.append(line)
    return "\n".join(remaining).strip() + "\n"


def _ensure_single_argument_report(code):
    """保证原生 Macro Development 直接运行时存在一个报告上下文。"""
    normalised = _normalise_drc_code(code)
    for line in normalised.splitlines():
        statement = line.split("#", 1)[0].strip().lower()
        if _is_single_argument_report(statement):
            return normalised
    return _DEFAULT_REPORT_STATEMENT + "\n\n" + normalised


def validate_drc_code(code):
    """检查规则代码；只允许一个单参数 report() 供原生编辑器直接运行。"""
    normalised = _normalise_drc_code(code)
    if not normalised.strip():
        raise ValueError("DRC 代码不能为空。")

    report_count = 0
    for line_number, line in enumerate(normalised.splitlines(), start=1):
        statement = line.split("#", 1)[0].strip().lower()
        if re.match(r"^source\s*\(", statement):
            raise ValueError(
                "第 %d 行不能调用 source()；"
                "JNU_MWP_PDK 会自动针对当前编辑 Cell 注入输入路径。" % line_number
            )
        if re.match(r"^report\s*\(", statement):
            if not _is_single_argument_report(statement):
                raise ValueError(
                    "第 %d 行的 report() 只能使用一个报告标题；"
                    "当前 Cell 运行器会自动注入报告文件路径。" % line_number
                )
            report_count += 1
    if report_count > 1:
        raise ValueError("DRC 代码只能包含一个单参数 report() 语句。")
    return normalised


def load_persisted_drc_code(macro_path=None):
    """从 JNU_MWP_DRC.lydrc 读取用户保存的 DSL 规则代码。"""
    path = Path(macro_path) if macro_path is not None else drc_macro_path()
    if not path.is_file():
        raise RuntimeError("未找到 JNU_MWP_DRC 规则文件：%s" % path)
    try:
        root = ET.parse(str(path)).getroot()
        text_node = root.find(_RULE_CODE_TAG)
    except (ET.ParseError, OSError) as error:
        raise RuntimeError("无法读取 JNU_MWP_DRC 规则文件：%s" % error)
    if text_node is None:
        raise RuntimeError("JNU_MWP_DRC 规则文件缺少 <text> 代码节点。")
    return validate_drc_code(text_node.text)


def save_persisted_drc_code(code, macro_path=None):
    """原子写回 DSL 规则，供自动化测试及非 GUI 调用使用。"""
    normalised = _ensure_single_argument_report(validate_drc_code(code))
    path = Path(macro_path) if macro_path is not None else drc_macro_path()
    if not path.is_file():
        raise RuntimeError("未找到 JNU_MWP_DRC 规则文件：%s" % path)
    try:
        tree = ET.parse(str(path))
        text_node = tree.getroot().find(_RULE_CODE_TAG)
    except (ET.ParseError, OSError) as error:
        raise RuntimeError("无法读取 JNU_MWP_DRC 规则文件：%s" % error)
    if text_node is None:
        raise RuntimeError("JNU_MWP_DRC 规则文件缺少 <text> 代码节点。")

    text_node.text = normalised
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".lydrc", prefix="jnu_mwp_drc_save_",
            dir=str(path.parent), delete=False,
        ) as handle:
            temporary_path = handle.name
        tree.write(temporary_path, encoding="utf-8", xml_declaration=True)
        os.replace(temporary_path, str(path))
        temporary_path = None
    except OSError as error:
        raise RuntimeError("无法保存 JNU_MWP_DRC 规则文件：%s" % error)
    finally:
        if temporary_path and os.path.isfile(temporary_path):
            try:
                os.remove(temporary_path)
            except OSError:
                pass
    return normalised


def _drc_string_literal(value):
    """把文件路径或 Cell 名称编码为 DRC DSL 的双引号字符串。"""
    return '"%s"' % str(value).replace("\\", "/").replace('"', '\\"')


def build_drc_text(drc_code, source_filename=None, top_cell_name=None, report_filename=None):
    """把规则代码与当前 Cell 的输入、报告路径组合成一次性 DRC DSL。"""
    code = _strip_single_argument_report(validate_drc_code(drc_code))
    if not all(value is not None for value in (source_filename, top_cell_name, report_filename)):
        raise ValueError("DRC 的输入版图、当前 Cell 与报告路径必须同时提供。")
    return "\n\n".join((
        "# DRC 输入版图、当前编辑 Cell 和报告输出。",
        "source(%s, %s)" % (
            _drc_string_literal(source_filename),
            _drc_string_literal(top_cell_name),
        ),
        "report(%s, %s)" % (
            _drc_string_literal(_DEFAULT_REPORT_TITLE),
            _drc_string_literal(report_filename),
        ),
        code.rstrip(),
        "",
    ))


def build_drc_macro_xml(drc_text):
    """把一次性 DRC DSL 封装为可执行的 XML 宏。"""
    escaped_text = html.escape(str(drc_text), quote=False)
    return """<?xml version="1.0" encoding="utf-8"?>
<klayout-macro>
 <description>JNU MWP temporary current-cell DRC</description>
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
    """写入一次性 DRC 宏；调用方执行后必须删除返回的文件。"""
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
    """取得当前 KLayout 主窗口。"""
    return pya.Application.instance().main_window()


def _current_layout_view_context():
    """取得当前 view、layout 与正在编辑的 DRC 目标 Cell。"""
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
    # cellview.cell 会随层级编辑同步变化，只检查该 Cell 及其子层级。
    active_cell = cellview.cell
    if active_cell is None:
        raise RuntimeError("当前视图没有正在编辑的 Cell。")
    return view, cellview, layout, active_cell


def _load_report_into_view(view, cellview, report_path, top_cell_name):
    """把临时 DRC 报告读入当前 Marker Browser。"""
    if not os.path.isfile(report_path):
        raise RuntimeError("DRC 没有生成报告文件。")
    report_id = view.create_rdb("JNU MWP DRC")
    report_database = view.rdb(report_id)
    report_database.load(report_path)
    report_database.top_cell_name = str(top_cell_name)
    report_database.create_cell(str(top_cell_name))
    view.show_rdb(report_id, cellview.cell_index)


def _show_error(message):
    """以一致方式显示 DRC 编辑或执行错误。"""
    pya.MessageBox.warning(TOOL_TITLE, str(message), pya.MessageBox.Ok)


def _macro_editor_path_text(path):
    """生成 KLayout 配置可识别的正斜杠绝对宏路径。"""
    return str(Path(path).resolve()).replace("\\", "/")


def _append_open_macro(existing_value, macro_path_text):
    """在不丢失用户已有编辑器标签页的前提下加入目标宏路径。"""
    target = "'%s'" % macro_path_text.replace("'", "\\'")
    existing = str(existing_value or "").strip()
    if target in existing:
        return existing
    return target if not existing else existing + ";" + target


def _ensure_native_editor_report_context():
    """补回被手动删除的 report()，避免原生绿色 Run 误把 output 当作图层输出。"""
    persisted = load_persisted_drc_code()
    normalised = _ensure_single_argument_report(persisted)
    if normalised != persisted:
        save_persisted_drc_code(normalised)


def _open_native_macro_editor(macro_path, application=None, main_window=None):
    """设置原生编辑器当前文件，并触发 KLayout Macro Development action。"""
    path = Path(macro_path)
    if not path.is_file():
        raise RuntimeError("未找到 JNU_MWP_DRC 规则文件：%s" % path)

    application = application if application is not None else pya.Application.instance()
    main_window = main_window if main_window is not None else _main_window()
    if application is None or main_window is None:
        raise RuntimeError("当前 KLayout 没有可用的主窗口。")

    path_text = _macro_editor_path_text(path)
    try:
        existing = application.get_config("macro-editor-open-macros")
    except Exception:
        existing = ""
    application.set_config("macro-editor-current-macro", path_text)
    application.set_config(
        "macro-editor-open-macros", _append_open_macro(existing, path_text),
    )

    action = main_window.menu().action(_MACRO_DEVELOPMENT_ACTION)
    if action is None:
        raise RuntimeError("未找到 KLayout 的 Macro Development 菜单动作。")
    action.trigger()
    return True


def open_drc_macro_editor():
    """在 KLayout 原生 Macro Development 中打开持久化的 JNU DRC 代码。"""
    try:
        _ensure_native_editor_report_context()
        return _open_native_macro_editor(drc_macro_path())
    except (RuntimeError, ValueError) as error:
        _show_error(error)
        return False


def run_current_cell_drc():
    """执行已保存规则，并且仅检查当前编辑 Cell 及其子层级。"""
    try:
        drc_code = load_persisted_drc_code()
        view, cellview, layout, active_cell = _current_layout_view_context()
    except (RuntimeError, ValueError) as error:
        _show_error(error)
        return False

    # DRC DSL 独立执行时不会继承 GUI 的输入上下文；先将当前内存版图
    # 写入临时 GDS，再显式 source 当前编辑 Cell 并在报告载入后清理文件。
    with tempfile.TemporaryDirectory(prefix="jnu_mwp_drc_run_") as directory:
        input_path = os.path.join(directory, "input.gds")
        report_path = os.path.join(directory, "result.lyrdb")
        temporary_macro = None
        try:
            layout.write(input_path)
            drc_text = build_drc_text(
                drc_code, input_path, active_cell.name, report_path,
            )
            temporary_macro = write_temporary_drc_macro(drc_text)
            pya.Macro(temporary_macro).run()
            _load_report_into_view(view, cellview, report_path, active_cell.name)
            return True
        except Exception as error:
            _show_error("DRC 执行失败：\n%s" % error)
            return False
        finally:
            if temporary_macro and os.path.isfile(temporary_macro):
                try:
                    os.remove(temporary_macro)
                except OSError:
                    pass


def run_drc():
    """兼容旧菜单回调：现在打开原生 Macro Development 编辑器。"""
    return open_drc_macro_editor()


__all__ = [
    "TOOL_TITLE",
    "drc_macro_path",
    "validate_drc_code",
    "load_persisted_drc_code",
    "save_persisted_drc_code",
    "build_drc_text",
    "build_drc_macro_xml",
    "write_temporary_drc_macro",
    "open_drc_macro_editor",
    "run_current_cell_drc",
    "run_drc",
]
