# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""只读比较两个选中波导实例的长度，复合波导排除 taper。"""

import pya

from JNU_MWP_tools.actions.calculate_waveguide_length import (
    _format_parameter,
    _show_results,
    _taper_note,
    _ui,
    _waveguide_detail_lines,
)
from JNU_MWP_tools.core.common import _active_context, _value
from JNU_MWP_tools.core.waveguide_length import (
    WaveguideLengthError,
    compare_selected_waveguides,
)


def _result_message(details, difference_um):
    """总差取绝对值，各宽度分项分别比较，不把分项绝对差相加当作总差。"""
    lines = []
    for index, item in enumerate(details, 1):
        lines.append(_ui("Waveguide %d length L%d: %.3f µm (%.6f mm)",
                         "波导 %d 长度 L%d：%.3f µm（%.6f mm）") % (
            index, index, item["length_um"], item["length_um"] / 1000.0,
        ))
    lines.append(_ui("Absolute length difference |L1 − L2|: %.3f µm (%.6f mm)",
                     "绝对长度差 |L1 − L2|：%.3f µm（%.6f mm）") % (
        difference_um, difference_um / 1000.0,
    ))
    if any(item["kind"] == "composite" for item in details):
        lines.extend(["", _taper_note(), _ui(
            "The length difference also excludes tapers.",
            "长度差同样不包含 taper。",
        )])

    first, second = (item["length_by_width_um"] for item in details)
    widths = set(first) | set(second)
    # 历史数据缺少宽度时只能比较总长，不能把未知宽度与已知宽度当作不同分项。
    if None not in widths and (len(widths) > 1 or any(item["kind"] == "composite" for item in details)):
        lines.extend(["", _ui("Comparison by width (L1 / L2 / |difference|):",
                               "按宽度比较（L1 / L2 / |长度差|）：")])
        for width in sorted(widths):
            length1, length2 = first.get(width, 0.0), second.get(width, 0.0)
            lines.append(_ui("Width %s: %.3f / %.3f / %.3f µm",
                             "宽度 %s：%.3f / %.3f / %.3f µm") % (
                _format_parameter(width), length1, length2, abs(length1 - length2),
            ))
        lines.append(_ui("Width differences are separate comparisons; their sum is not the total difference.",
                         "各宽度的绝对差分别列出，不将其相加作为总长度差。"))
    lines.extend(_waveguide_detail_lines(details))
    return "\n".join(lines)


def calculate_waveguide_length_difference():
    """要求恰好两个独立波导实例；选择和版图均保持不变。"""
    title = _ui("Calculate Waveguide Length Difference", "计算波导长度差")
    try:
        view, _layout, _cell = _active_context()
        details, difference = compare_selected_waveguides(
            view.object_selection, _value(view, "active_cellview_index")
        )
    except WaveguideLengthError as error:
        count_message = _ui(
            "Select exactly two Waveguide or Composite_Waveguide instances.\n"
            "For arrays, select two individual members instead of a whole array.",
            "请恰好选中两个单宽度或复合宽度 Waveguide 实例。\n"
            "对于阵列，请选择两个单独成员，不要选择整个阵列。",
        )
        messages = {
            "empty": count_message,
            "not_two": count_message,
            "unsupported": _ui(
                "Only Waveguide and Composite_Waveguide instances are supported.\n"
                "The selection contains another object, so no difference was calculated.",
                "只支持单宽度和复合宽度 Waveguide 实例。\n"
                "选择中包含其他对象，已停止计算长度差。",
            ),
            "missing_length": _ui(
                "A selected Waveguide has missing or ambiguous length data.\n"
                "Regenerate that Waveguide and try again.",
                "选中的 Waveguide 缺少有效长度数据或存在重复长度标注。\n"
                "请重新生成该波导后重试。",
            ),
            "missing_profile": _ui(
                "A composite Waveguide has incomplete or inconsistent path/width data.\n"
                "Regenerate that Waveguide and try again.",
                "选中的复合波导缺少完整的路径／宽度数据，或数据不一致。\n"
                "请重新生成该波导后重试。",
            ),
        }
        pya.MessageBox.warning(title, messages[error.reason], pya.MessageBox.Ok)
        return
    except Exception as error:
        pya.MessageBox.warning(
            title,
            _ui("Unable to calculate waveguide length difference:\n", "无法计算波导长度差：\n") + str(error),
            pya.MessageBox.Ok,
        )
        return
    _show_results(title, _result_message(details, difference), "calculate_waveguide_length_difference")
