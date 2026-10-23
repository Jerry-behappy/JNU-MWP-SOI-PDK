# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""分两步选取波导组并比较总长，复合波导排除 taper。"""

import math

import pya

from JNU_MWP_tools.actions.calculate_waveguide_length import (
    _format_parameter,
    _show_results,
    _taper_note,
    _ui,
    _waveguide_detail_lines,
)
from JNU_MWP_tools.core.common import _active_context, _main_window, _value
from JNU_MWP_tools.core.waveguide_length import (
    WaveguideLengthError,
    describe_selected_length_objects,
)


_selection_session = None


def _group_length(details):
    return math.fsum(item["total_length_um"] for item in details)


def _width_totals(details):
    totals = {}
    for item in details:
        for width, length in item["length_by_width_um"].items():
            totals[width] = totals.get(width, 0.0) + length * item["copies"]
    return totals


def _result_message(groups):
    """总差取绝对值，各宽度分项分别比较，不把分项绝对差相加当作总差。"""
    lines = []
    for index, details in enumerate(groups, 1):
        length = _group_length(details)
        lines.append(_ui("Group %d total L%d: %.3f µm (%.6f mm); waveguides: %d",
                         "第 %d 组总长度 L%d：%.3f µm（%.6f mm）；波导数量：%d") % (
            index, index, length, length / 1000.0, sum(item["copies"] for item in details),
        ))
    difference_um = abs(_group_length(groups[0]) - _group_length(groups[1]))
    lines.append(_ui("Absolute length difference |L1 − L2|: %.3f µm (%.6f mm)",
                     "绝对长度差 |L1 − L2|：%.3f µm（%.6f mm）") % (
        difference_um, difference_um / 1000.0,
    ))
    has_composite = any(item["kind"] == "composite" for group in groups for item in group)
    if has_composite:
        lines.extend(["", _taper_note(), _ui(
            "The length difference also excludes tapers.",
            "长度差同样不包含 taper。",
        )])

    first, second = (_width_totals(group) for group in groups)
    widths = set(first) | set(second)
    # 历史数据缺少宽度时只能比较总长，不能把未知宽度与已知宽度当作不同分项。
    if None not in widths and (len(widths) > 1 or has_composite):
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
    for index, details in enumerate(groups, 1):
        lines.extend(["", _ui("Group %d details:", "第 %d 组明细：") % index])
        lines.extend(_waveguide_detail_lines(details))
    return "\n".join(lines)


def _warning(title, message):
    pya.MessageBox.warning(title, message, pya.MessageBox.Ok)


def _selection_error(error):
    if isinstance(error, WaveguideLengthError):
        messages = {
            "empty": _ui("Select at least one waveguide instance for this group, then click OK.",
                         "请为当前组选取至少一个波导实例，再按确定。"),
            "unsupported": _ui(
                "Only Waveguide, Composite_Waveguide, ordinary Paperclip_Spiral "
                "and Archimedean_Spiral instances are supported.\n"
                "The selection contains another object, so no difference was calculated.",
                "只支持单宽度和复合宽度 Waveguide、普通回形针 Paperclip_Spiral "
                "及阿基米德 Archimedean_Spiral 实例。\n"
                "选择中包含其他对象，已停止计算长度差。",
            ),
            "composite_spiral": _ui(
                "The selection contains a composite-width Spiral. The entire calculation was cancelled.\n"
                "No length difference was calculated. Deselect composite-width Spirals and try again.",
                "选择中包含复合宽度 Spiral，已取消整次计算，不显示长度差。\n"
                "请取消选中复合宽度 Spiral 后重试。",
            ),
            "missing_length": _ui(
                "A selected Waveguide or Spiral has missing or ambiguous length data.\n"
                "Regenerate that device and try again.",
                "选中的 Waveguide 或 Spiral 缺少有效长度数据或存在重复长度标注。\n"
                "请重新生成该器件后重试。",
            ),
            "missing_profile": _ui(
                "A composite Waveguide has incomplete or inconsistent path/width data.\n"
                "Regenerate that Waveguide and try again.",
                "选中的复合波导缺少完整的路径／宽度数据，或数据不一致。\n"
                "请重新生成该波导后重试。",
            ),
        }
        return messages.get(error.reason, str(error))
    return _ui("Unable to calculate waveguide length difference:\n", "无法计算波导长度差：\n") + str(error)


class _GroupSelection:
    """用非模态提示保留画布交互；第一组确认后只保存数值快照。"""

    def __init__(self):
        self.title = _ui("Calculate Waveguide Length Difference", "计算波导长度差")
        self.view, self.layout, cell = _active_context()
        self.cell_index = cell.cell_index()
        self.cv_index = _value(self.view, "active_cellview_index")
        self.groups = []
        if hasattr(self.view, "switch_mode"):
            self.view.switch_mode("select")
        self.dialog = pya.QDialog(_main_window())
        self.dialog.setWindowTitle(self.title)
        self.dialog.setModal(False)
        font = pya.QFont(self.dialog.font)
        font.setPointSize(11)
        self.dialog.setFont(font)
        layout = pya.QVBoxLayout(self.dialog)
        self.prompt = pya.QLabel(self.dialog)
        self.prompt.setWordWrap(True)
        layout.addWidget(self.prompt)
        buttons = pya.QHBoxLayout()
        self.confirm = pya.QPushButton(_ui("OK", "确定"), self.dialog)
        cancel = pya.QPushButton(_ui("Cancel", "取消"), self.dialog)
        buttons.addWidget(self.confirm)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)
        self.confirm.clicked.connect(self._confirm)
        cancel.clicked.connect(self.dialog.reject)
        self.dialog.finished.connect(self._finished)
        self.dialog.setFixedSize(600, 240)
        self._update_prompt()

    def _update_prompt(self):
        text = _ui(
            "Select the first group of waveguides in the layout (one or more cells), then click OK.",
            "请在版图中选取第一组波导（可选多个波导 cell），选取完后按确定。",
        ) if not self.groups else _ui(
            "Group 1 confirmed: %d waveguides, %.3f µm.\n\n"
            "The selection has been cleared. Select the second group (one or more cells), "
            "then click OK to calculate the length difference.",
            "第一组已确认：%d 个波导，%.3f µm。\n\n"
            "已清空选择。请选取第二组波导（可选多个波导 cell），选取完后按确定计算长度差。",
        ) % (sum(item["copies"] for item in self.groups[0]), _group_length(self.groups[0]))
        self.prompt.setText(text + "\n\n" + _ui(
            "You can select cells while this window is open. Do not edit or switch layouts during selection.",
            "此窗口打开时仍可操作版图选择器件。选取期间请勿编辑或切换版图。",
        ))

    def show(self):
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def _finished(self, _result):
        global _selection_session
        if _selection_session is self:
            _selection_session = None
        self.dialog.deleteLater()

    def _confirm(self):
        try:
            view, layout, cell = _active_context()
            if (view != self.view or layout != self.layout or cell.cell_index() != self.cell_index
                    or _value(view, "active_cellview_index") != self.cv_index):
                raise RuntimeError(_ui(
                    "The active layout or cell changed. Restart the group selection.",
                    "当前版图或编辑 cell 已切换，请重新开始分组选取。",
                ))
            details = describe_selected_length_objects(view.object_selection, self.cv_index)
        except Exception as error:
            # 空组允许原步骤补选；其他无效器件或上下文变化取消全部结果。
            if not isinstance(error, WaveguideLengthError) or error.reason != "empty":
                self.dialog.reject()
            _warning(self.title, _selection_error(error))
            return
        self.groups.append(details)
        if len(self.groups) == 1:
            self.view.object_selection = []
            self._update_prompt()
        else:
            self.confirm.setEnabled(False)
            self.dialog.accept()
            _show_results(self.title, _result_message(self.groups), "calculate_waveguide_length_difference")


def calculate_waveguide_length_difference():
    """菜单重复触发时复用正在选取的窗口，避免两组状态交叉。"""
    global _selection_session
    try:
        if _selection_session is None:
            _selection_session = _GroupSelection()
        _selection_session.show()
    except Exception as error:
        _warning(_ui("Calculate Waveguide Length Difference", "计算波导长度差"), _selection_error(error))
