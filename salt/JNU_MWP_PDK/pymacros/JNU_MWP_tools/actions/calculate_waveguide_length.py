# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""显示波导及普通 Spiral 的总长与参数；复合波导排除 taper，复合 Spiral 整批拒绝。"""

import math

import pya

from JNU_MWP_tools.core.common import _active_context, _main_window, _value
from JNU_MWP_tools.core.gui_state import exec_dialog_with_persisted_size
from JNU_MWP_tools.core.ui_language import LANGUAGE_ZH, active_language
from JNU_MWP_tools.core.waveguide_length import (
    WaveguideLengthError,
    describe_selected_length_objects,
)


def _ui(english, chinese):
    return chinese if active_language() == LANGUAGE_ZH else english


def _format_parameter(value, unit=" µm"):
    """缺少历史参数时明确显示未知，长度统计仍可正常显示。"""
    return _ui("Not stored", "未保存") if value is None else "%.3f%s" % (value, unit)


def _taper_note():
    """总长与长度差共用同一渐变段排除说明。"""
    return _ui(
        "Note: taper lengths are excluded from every width subtotal and the total.\n"
        "Constant-width transition sections are included at their actual width.",
        "说明：taper（宽度渐变段）长度不计入各宽度小计及总长度。\n"
        "恒宽 transition 段计入对应宽度的长度。",
    )


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
        lines.extend(["", _taper_note()])
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
    lines.extend(_waveguide_detail_lines(details))
    return "\n".join(lines)


def _waveguide_detail_lines(details, include_bends=False):
    """共用实例参数明细，确保总长与长度差界面显示相同参数。"""
    lines = []
    for index, item in enumerate(details, 1):
        params = item["parameters"]
        lines.extend(["", "%d. %s" % (index, item["cell_name"])])
        composite = item["kind"] == "composite"
        lines.append((
            _ui("Length (excluding tapers): ", "长度（不含 taper）：") if composite else _ui("Length: ", "长度：")
        ) + _format_parameter(item["length_um"]))
        if include_bends:
            bends = item.get("bend_count")
            lines.append(_ui("90° bends per copy: ", "单个副本的 90° 弯曲数：") + (
                str(bends) if bends is not None else _ui("Unknown (route data not stored)", "未知（未保存路径数据）")
            ))
            if item.get("continuous_spiral_segments"):
                lines.append(_ui("Continuous spiral arms per copy: %d", "单个副本的连续螺旋臂数：%d") % item["continuous_spiral_segments"])
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
        if item["kind"] in ("paperclip", "archimedean"):
            lines.append(_ui("Device type: ", "器件类型：") + {
                "paperclip": _ui("Paperclip Spiral", "回形针 Spiral"),
                "archimedean": _ui("Archimedean Spiral", "阿基米德 Spiral"),
            }[item["kind"]])
        bend = params["bend_type"]
        bend_label = {
            "Circular": _ui("Circular", "圆弧（Circular）"),
            "Bezier": _ui("Bezier", "贝塞尔（Bezier）"),
            "Euler": _ui("Euler", "欧拉（Euler）"),
        }.get(bend, _ui("Not stored", "未保存"))
        bend_title = _ui("Center bend type: ", "中心弯曲类型：") if item["kind"] == "archimedean" else _ui("Bend type: ", "弯曲类型：")
        lines.append(bend_title + bend_label)
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
    return lines


def _show_results(title, message, dialog_key="calculate_waveguide_length"):
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
    close.setObjectName("waveguide_length_close")
    # clicked 携带 checked 参数，原生 accept 不接受该参数。
    close.clicked.connect(lambda _checked=False: dialog.accept())
    layout.addWidget(close)
    exec_dialog_with_persisted_size(dialog, dialog_key, (800, 520), center_right=True)


def calculate_waveguide_length():
    """只统计显式选择的波导，保持版图与选择集不变。"""
    title = _ui("Calculate Waveguide Length", "计算波导长度")
    try:
        view, _layout, _cell = _active_context()
        details = describe_selected_length_objects(
            view.object_selection, _value(view, "active_cellview_index")
        )
    except WaveguideLengthError as error:
        messages = {
            "composite_spiral": _ui(
                "The selection contains a composite-width Spiral. The entire calculation was cancelled.\n"
                "No partial total was calculated. Deselect composite-width Spirals and try again.",
                "选择中包含复合宽度 Spiral，已取消整次计算，不显示部分总长。\n"
                "请取消选中复合宽度 Spiral 后重试。",
            ),
            "empty": _ui(
                "Select Waveguide, Composite_Waveguide, Paperclip Spiral or Archimedean Spiral instances first.",
                "请先选中 Waveguide、复合宽度 Waveguide、普通回形针或阿基米德 Spiral 实例。",
            ),
            "unsupported": _ui(
                "Only Waveguide, Composite_Waveguide, Paperclip Spiral and Archimedean Spiral instances are supported.\n"
                "The selection contains another object, so no total was calculated.",
                "只支持 Waveguide、复合宽度 Waveguide、普通回形针和阿基米德 Spiral 实例。\n"
                "选择中包含其他对象，已停止计算；请仅选中波导后重试。",
            ),
            "missing_length": _ui(
                "A selected waveguide or Spiral has missing or ambiguous actual length data.\n"
                "No total was calculated. Regenerate that device and try again.",
                "选中的波导或 Spiral 缺少有效的实际长度数据或存在重复长度标注，已停止计算。\n"
                "请重新生成该器件后重试。",
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
