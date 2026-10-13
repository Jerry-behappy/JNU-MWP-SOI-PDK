# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""只读汇总选中单宽度 Waveguide 实例的中心线长度与弯曲参数。"""

import math
import re

import pya

from JNU_MWP_tools.core.bend_curvature import bezier_Rmax_Rmin, euler_Reff
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


def _stored_annotation(cell):
    """读取唯一有效的长度标注，同时保留其中的波导参数。"""
    layer = cell.layout().find_layer(pya.LayerInfo(10, 0))
    annotations = []
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
                    annotations.append((length, text))
    # 缺少或有多个长度标注时不猜测，避免把不完整总长显示为有效结果。
    if len(annotations) != 1:
        raise WaveguideLengthError("missing_length")
    return annotations[0]


def _number(value):
    """无效或缺失的参数保持未知，不用默认设置补写历史波导参数。"""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def _waveguide_parameters(cell, annotation, scale):
    """优先读取 PCell 参数；无上下文的 GDS 从标注和参数化名称恢复。"""
    params = dict(cell.pcell_parameters_by_name())
    for key in ("width", "radius"):
        if _number(params.get(key)) is None:
            match = re.search(r"\b%s=([0-9]+(?:\.[0-9]+)?)um\b" % key, annotation)
            params[key] = float(match.group(1)) if match else None
    if not params.get("bend_type"):
        match = re.search(r"\bbend=(Circular|Bezier|Euler)\b", annotation)
        params["bend_type"] = match.group(1) if match else None

    # 旧 GDS 的 Text 没有 B 和 Euler 半径，但参数化名称仍保存这些值。
    for key, token in (("bezier_k", "B"), ("Euler_Rmax", "Rmax"), ("Euler_Rmin", "Rmin")):
        if _number(params.get(key)) is None:
            match = re.search(r"_%s([0-9]+(?:\.[0-9]+)?)(?:_|$)" % token, cell.name)
            params[key] = float(match.group(1)) if match else None

    result = {"bend_type": params.get("bend_type")}
    for key in ("width", "radius", "bezier_k", "Euler_Rmax", "Euler_Rmin"):
        value = _number(params.get(key))
        result[key] = value * scale if value is not None and key != "bezier_k" else value
    if result["bend_type"] == "Bezier" and result["radius"] is not None and result["bezier_k"] is not None:
        result["Bezier_Rmax"], result["Bezier_Rmin"] = bezier_Rmax_Rmin(
            result["radius"], result["bezier_k"]
        )
    if result["bend_type"] == "Euler" and result["Euler_Rmax"] is not None and result["Euler_Rmin"] is not None:
        result["Euler_Reff"] = euler_Reff(result["Euler_Rmax"], result["Euler_Rmin"])
    return result


def describe_selected_waveguides(selection, cellview_index):
    """返回每个选中实例的长度、数量与参数；混入其他对象时整批报错。"""
    selected = []
    for obj in selection:
        if not any(obj == existing for existing in selected):
            selected.append(obj)
    if not selected:
        raise WaveguideLengthError("empty")

    details = []
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
        length, annotation = _stored_annotation(instance.cell)
        details.append({
            "cell_name": instance.cell.name,
            "copies": copies,
            "length_um": length * scale,
            "total_length_um": length * scale * copies,
            "parameters": _waveguide_parameters(instance.cell, annotation, scale),
        })
    return details


def measure_selected_waveguides(selection, cellview_index):
    """保持原接口，返回实例数量与总长（µm）。"""
    details = describe_selected_waveguides(selection, cellview_index)
    return sum(item["copies"] for item in details), math.fsum(
        item["total_length_um"] for item in details
    )
