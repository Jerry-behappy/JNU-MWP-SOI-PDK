# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""显示波导按宽度汇总的长度与参数，复合波导排除 taper。"""

import math

import pya

from JNU_MWP_tools.core.common import _active_context, _main_window, _value
from JNU_MWP_tools.core.gui_state import exec_dialog_with_persisted_size
from JNU_MWP_tools.core.ui_language import LANGUAGE_ZH, active_language
from JNU_MWP_tools.core.waveguide_length import (
    WaveguideLengthError,
    describe_selected_waveguides,
)


def _ui(english, chinese):
    return chinese if active_language() == LANGUAGE_ZH else english


def _format_parameter(value, unit=" µm"):
    """缺少历史参数时明确显示未知，长度统计仍可正常显示。"""
    return _ui("Not stored", "未保存") if value is None else "%.3f%s" % (value, unit)


def _result_message(details):
    """按实例列出宽度、弯曲类型及对应参数，并汇总全部选中副本。"""
    count = sum(item["copies"] for item in details)
    length_um = math.fsum(item["total_length_um"] for item in details)
    has_composite = any(item["kind"] == "composite" for item in details)
    lines = [_ui(
        "Waveguides: %d\nTotal length (excluding tapers): %.3f µm (%.6f mm)" if has_composite
        else "Waveguides: %d\nTotal length: %.3f µm (%.6f mm)",
        "波导数量：%d\n总波导长度（不含 taper）：%.3f µm（%.6f mm）" if has_composite
        else "波导数量：%d\n总波导长度：%.3f µm（%.6f mm）",
    ) % (count, length_um, length_um / 1000.0)]
    if has_composite:
        lines.extend(["", _ui(
            "Note: taper lengths are excluded from every width subtotal and the total.\n"
            "Constant-width transition sections are included at their actual width.",
            "说明：taper（宽度渐变段）长度不计入各宽度小计及总长度。\n"
            "恒宽 transition 段计入对应宽度的长度。",
        )])
        excluded = math.fsum(item["excluded_taper_length_um"] * item["copies"] for item in details)
        lines.append(_ui("Excluded taper length: ", "已排除的 taper 总长度：") + _format_parameter(excluded))
    totals = {}
    for item in details:
        for width, length in item["length_by_width_um"].items():
            totals[width] = totals.get(width, 0.0) + length * item["copies"]
    if has_composite or len(totals) > 1:
        lines.extend(["", _ui("Lengths by width:", "按宽度汇总：")])
        for width in sorted(totals, key=lambda value: (value is None, value or 0)):
            lines.append(_ui("Width %s: %.3f µm", "宽度 %s：%.3f µm") % (
                _format_parameter(width), totals[width],
            ))
    for index, item in enumerate(details, 1):
        params = item["parameters"]
        lines.extend(["", "%d. %s" % (index, item["cell_name"])])
        composite = item["kind"] == "composite"
        lines.append((
            _ui("Length (excluding tapers): ", "长度（不含 taper）：") if composite else _ui("Length: ", "长度：")
        ) + _format_parameter(item["length_um"]))
        if item["copies"] > 1:
            lines.append(_ui("Copies: %d; subtotal: %.3f µm", "副本数量：%d；小计：%.3f µm") % (
                item["copies"], item["total_length_um"],
            ))
        if composite:
            for width, length in sorted(item["length_by_width_um"].items()):
                lines.append(_ui("Width %s: %.3f µm", "宽度 %s：%.3f µm") % (_format_parameter(width), length))
            for key, english, chinese in (
                ("straight_width", "Straight width: ", "直波导宽度："),
                ("bend_width", "Bend width: ", "弯曲波导宽度："),
                ("start_width", "Start width: ", "起始端宽度："),
                ("end_width", "End width: ", "终止端宽度："),
                ("transition_length", "Transition length: ", "恒宽 transition 设置长度："),
            ):
                lines.append(_ui(english, chinese) + _format_parameter(params[key]))
            lines.append(_ui("Excluded taper length: ", "已排除的 taper 长度：") + _format_parameter(item["excluded_taper_length_um"]))
        else:
            lines.append(_ui("Waveguide width: ", "波导宽度：") + _format_parameter(params["width"]))
        bend = params["bend_type"]
        bend_label = {
            "Circular": _ui("Circular", "圆弧（Circular）"),
            "Bezier": _ui("Bezier", "贝塞尔（Bezier）"),
            "Euler": _ui("Euler", "欧拉（Euler）"),
        }.get(bend, _ui("Not stored", "未保存"))
        lines.append(_ui("Bend type: ", "弯曲类型：") + bend_label)
        if bend in ("Circular", "Bezier"):
            lines.append(_ui("Bend radius R: ", "弯曲半径 R：") + _format_parameter(params["radius"]))
        if bend == "Bezier":
            lines.extend([
                "Bezier B: " + _format_parameter(params["bezier_k"], ""),
                _ui("Maximum curvature radius Rmax: ", "最大曲率半径 Rmax：") + _format_parameter(params.get("Bezier_Rmax")),
                _ui("Minimum curvature radius Rmin: ", "最小曲率半径 Rmin：") + _format_parameter(params.get("Bezier_Rmin")),
            ])
        elif bend == "Euler":
            lines.extend([
                "Euler Rmax: " + _format_parameter(params["Euler_Rmax"]),
                "Euler Rmin: " + _format_parameter(params["Euler_Rmin"]),
                _ui("Effective radius Reff: ", "有效半径 Reff：") + _format_parameter(params.get("Euler_Reff")),
            ])
    return "\n".join(lines)


def _show_results(title, message):
    """可滚动、可复制的只读结果，避免多选时弹窗内容超出屏幕。"""
    dialog = pya.QDialog(_main_window())
    dialog.setWindowTitle(title)
    font = pya.QFont(dialog.font)
    font.setPointSize(11)
    dialog.setFont(font)
    layout = pya.QVBoxLayout(dialog)
    output = pya.QTextEdit(dialog)
    output.setObjectName("waveguide_length_output")
    output.setReadOnly(True)
    output.setPlainText(message)
    layout.addWidget(output)
    close = pya.QPushButton(_ui("Close", "关闭"), dialog)
    close.clicked.connect(dialog.accept)
    layout.addWidget(close)
    exec_dialog_with_persisted_size(dialog, "calculate_waveguide_length", (800, 520))


def calculate_waveguide_length():
    """只统计显式选择的波导，保持版图与选择集不变。"""
    title = _ui("Calculate Waveguide Length", "计算波导长度")
    try:
        view, _layout, _cell = _active_context()
        details = describe_selected_waveguides(
            view.object_selection, _value(view, "active_cellview_index")
        )
    except WaveguideLengthError as error:
        messages = {
            "empty": _ui(
                "Select one or more Waveguide or Composite_Waveguide instances first.",
                "请先选中一个或多个单宽度或复合宽度 Waveguide 实例。",
            ),
            "unsupported": _ui(
                "Only Waveguide and Composite_Waveguide instances are supported.\n"
                "The selection contains another object, so no total was calculated.",
                "只支持单宽度和复合宽度 Waveguide 实例。\n"
                "选择中包含其他对象，已停止计算；请仅选中波导后重试。",
            ),
            "missing_length": _ui(
                "A selected Waveguide has missing or ambiguous length data.\n"
                "No total was calculated. Regenerate that Waveguide and try again.",
                "选中的 Waveguide 缺少有效长度数据或存在重复长度标注，已停止计算。\n"
                "请重新生成该波导后重试。",
            ),
            "missing_profile": _ui(
                "A composite Waveguide has incomplete or inconsistent path/width data.\n"
                "No total was calculated. Regenerate that Waveguide and try again.",
                "选中的复合波导缺少完整的路径／宽度数据，或数据不一致，已停止计算。\n"
                "请重新生成该波导后重试。",
            ),
        }
        pya.MessageBox.warning(title, messages[error.reason], pya.MessageBox.Ok)
        return
    except Exception as error:
        pya.MessageBox.warning(
            title,
            _ui("Unable to calculate waveguide length:\n", "无法计算波导长度：\n") + str(error),
            pya.MessageBox.Ok,
        )
        return

    _show_results(title, _result_message(details))
