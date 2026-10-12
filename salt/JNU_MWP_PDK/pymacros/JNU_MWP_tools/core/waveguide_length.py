# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""只读汇总选中单宽度 Waveguide 实例的中心线长度。"""

import math
import re

import pya

from JNU_MWP_tools.core.common import (
    WAVEGUIDE_KIND_GDS_PROPERTY,
    WAVEGUIDE_KIND_PROPERTY,
    _value,
)


class WaveguideLengthError(ValueError):
    """用稳定错误键让菜单按当前语言显示选择或长度数据错误。"""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _is_single_waveguide(cell):
    """按 PCell 声明、恢复标记和旧版名称识别单宽度波导。"""
    declaration = cell.pcell_declaration()
    if declaration is not None:
        return declaration.name() == "Waveguide"
    for key in (WAVEGUIDE_KIND_PROPERTY, WAVEGUIDE_KIND_GDS_PROPERTY):
        kind = cell.property(key)
        if kind in ("single", "composite"):
            return kind == "single"
    return bool(re.match(r"^(?:Waveguide(?:$|[_$])|JNU_WG_)", cell.name))


def _stored_length_um(cell):
    """读取生产几何时保存的圆滑中心线长度，不用原始直角 Path 代替。"""
    layer = cell.layout().find_layer(pya.LayerInfo(10, 0))
    lengths = []
    if layer is not None:
        for shape in cell.shapes(layer).each():
            if not shape.is_text():
                continue
            text = shape.text.string
            if not text.startswith("Waveguide width="):
                continue
            match = re.search(r"\blength=([0-9]+(?:\.[0-9]+)?)um\b", text)
            if match:
                length = float(match.group(1))
                if math.isfinite(length) and length > 0:
                    lengths.append(length)
    # 缺少或有多个长度标注时不猜测，避免把不完整总长显示为有效结果。
    if len(lengths) != 1:
        raise WaveguideLengthError("missing_length")
    return lengths[0]


def measure_selected_waveguides(selection, cellview_index):
    """返回实例数量与总长（µm）；混入其他对象时整批报错。"""
    selected = []
    for obj in selection:
        if not any(obj == existing for existing in selected):
            selected.append(obj)
    if not selected:
        raise WaveguideLengthError("empty")

    count = 0
    lengths = []
    for obj in selected:
        if not obj.is_cell_inst() or obj.cv_index != cellview_index:
            raise WaveguideLengthError("unsupported")
        instance = obj.inst()
        if instance is None or instance.cell is None or not _is_single_waveguide(instance.cell):
            raise WaveguideLengthError("unsupported")

        # 完整层级变换中的缩放影响物理长度，旋转、镜像和平移不影响。
        scale = 1.0
        copies = 1
        for element in obj.each_inst():
            scale *= abs(float(_value(element, "specific_cplx_trans").mag))
            parent_instance = _value(element, "inst")
            if (
                parent_instance.is_regular_array()
                and _value(element, "ia") < 0
                and _value(element, "ib") < 0
            ):
                copies *= int(parent_instance.na) * int(parent_instance.nb)
        lengths.append(_stored_length_um(instance.cell) * scale * copies)
        count += copies
    return count, math.fsum(lengths)
