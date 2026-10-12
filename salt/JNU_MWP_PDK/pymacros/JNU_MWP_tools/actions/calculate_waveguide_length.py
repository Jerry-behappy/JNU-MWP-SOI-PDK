# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""计算选中的单宽度 Waveguide 总长度并显示双语结果。"""

import pya

from JNU_MWP_tools.core.common import _active_context, _value
from JNU_MWP_tools.core.ui_language import LANGUAGE_ZH, active_language
from JNU_MWP_tools.core.waveguide_length import (
    WaveguideLengthError,
    measure_selected_waveguides,
)


def _ui(english, chinese):
    return chinese if active_language() == LANGUAGE_ZH else english


def calculate_waveguide_length():
    """只统计显式选择的波导，保持版图与选择集不变。"""
    title = _ui("Calculate Waveguide Length", "计算波导长度")
    try:
        view, _layout, _cell = _active_context()
        count, length_um = measure_selected_waveguides(
            view.object_selection, _value(view, "active_cellview_index")
        )
    except WaveguideLengthError as error:
        messages = {
            "empty": _ui(
                "Select one or more single-width Waveguide instances first.",
                "请先选中一个或多个单宽度 Waveguide 实例。",
            ),
            "unsupported": _ui(
                "Only single-width Waveguide instances are supported.\n"
                "The selection contains a composite-width waveguide or another object.\n"
                "No total was calculated. Please select only single-width Waveguides.",
                "只支持单宽度 Waveguide 实例。\n"
                "选择中包含复合宽度波导或其他对象，已停止计算。\n"
                "请仅选中单宽度 Waveguide 后重试。",
            ),
            "missing_length": _ui(
                "A selected Waveguide has missing or ambiguous length data.\n"
                "No total was calculated. Regenerate that Waveguide and try again.",
                "选中的 Waveguide 缺少有效长度数据或存在重复长度标注，已停止计算。\n"
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

    message = _ui(
        "Single-width Waveguides: %d\nTotal length: %.3f µm (%.6f mm)",
        "单宽度波导数量：%d\n总波导长度：%.3f µm（%.6f mm）",
    ) % (count, length_um, length_um / 1000.0)
    pya.MessageBox.info(title, message, pya.MessageBox.Ok)
