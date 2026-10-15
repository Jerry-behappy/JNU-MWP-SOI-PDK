# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""只读汇总波导及普通 Spiral，按宽度计长并排除渐变段。"""

import json
import math
import re

import pya

from JNU_MWP_tools.core.bend_curvature import bezier_Rmax_Rmin, euler_Reff
from JNU_MWP_tools.core.common import (
    RAW_PATH_GDS_PROPERTY,
    RAW_PATH_PROPERTY,
    WAVEGUIDE_KIND_GDS_PROPERTY,
    WAVEGUIDE_KIND_PROPERTY,
    _value,
)
from JNU_MWP_tools.core.composite_profile import build_route_skeleton, profile_length_breakdown


class WaveguideLengthError(ValueError):
    """用稳定错误键让菜单按当前语言显示选择或长度数据错误。"""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _waveguide_kind(cell):
    """按 PCell 声明、恢复标记和旧版名称识别波导种类。"""
    declaration = cell.pcell_declaration()
    if declaration is not None:
        return {"Waveguide": "single", "Composite_Waveguide": "composite"}.get(declaration.name())
    for key in (WAVEGUIDE_KIND_PROPERTY, WAVEGUIDE_KIND_GDS_PROPERTY):
        kind = cell.property(key)
        if kind in ("single", "composite"):
            return kind
    if cell.name.startswith("Composite_Waveguide"):
        return "composite"
    if re.match(r"^(?:Waveguide(?:$|[_$])|JNU_WG_)", cell.name):
        return "single"
    return None


def _spiral_kind(cell):
    """识别普通及复合回形针，兼容公开 PCell 名和无上下文的旧 GDS。"""
    declaration = cell.pcell_declaration()
    name = declaration.name() if declaration is not None else cell.name
    name = re.sub(r"^(?:<defunct>)?(?:JNULib\.)?(?:Pcell_)?", "", name)
    if name.startswith(("Paperclip_Spiral_with_Composite_Waveguide", "CompPclip(")):
        return "composite_spiral"
    for prefix, kind in (("Paperclip_Spiral", "paperclip"), ("Archimedean_Spiral", "archimedean")):
        if re.match(r"^%s(?:$|[(_$])" % prefix, name):
            return kind
    return None


def _spiral_data(cell, kind):
    """使用实际 L 标注；绝不把 Paperclip 内直段或 Spiral 目标 length 当成总长。"""
    layer = cell.layout().find_layer(10, 0)
    texts = [shape.text.string for shape in cell.shapes(layer).each() if shape.is_text()] if layer is not None else []
    prefix = "Paperclip type=" if kind == "paperclip" else "L="
    lengths = []
    for text in texts:
        if text.startswith(prefix):
            match = re.search(r"\bL=([0-9]+(?:\.[0-9]+)?)um\b", text)
            if match and 0 < float(match.group(1)) < math.inf:
                lengths.append(float(match.group(1)))
    native = dict(cell.pcell_parameters_by_name())
    if len(lengths) > 1:
        raise WaveguideLengthError("missing_length")
    length = lengths[0] if lengths else _number(native.get("total_length"))
    if length is None or length <= 0:
        raise WaveguideLengthError("missing_length")

    annotation = "\n".join(texts)
    stored = annotation + "\n" + cell.name

    def parameter(key, token):
        value = _number(native.get(key))
        if value is None:
            match = re.search(r"\b%s=([0-9]+(?:\.[0-9]+)?)(?:um)?(?=[,\s|)]|$)" % token, stored)
            value = float(match.group(1)) if match else None
        return value

    bend = native.get("bend_type")
    if not bend:
        match = re.search(r"(?:\bbend=|,)(Circular|Bezier|Euler)(?=[,\s|)]|$)", stored)
        bend = match.group(1) if match else None
    width = parameter("wg_width", "w")
    if width is None:
        # 旧 Paperclip Text 没有宽度；同宽的两个光学端口可恢复实际波导宽度。
        pin_layer = cell.layout().find_layer(1, 10)
        widths = {shape.path.width for shape in cell.shapes(pin_layer).each() if shape.is_path()} if pin_layer is not None else set()
        if len(widths) == 1:
            width = next(iter(widths)) * cell.layout().dbu
    params = {
        "width": width,
        "radius": parameter("bend_radius" if kind == "paperclip" else "min_radius", "R"),
        "bend_type": bend,
        "bezier_k": parameter("bezier", "B"),
        "Euler_Rmax": parameter("Euler_Rmax", "Rmax") if bend == "Euler" else None,
        "Euler_Rmin": parameter("Euler_Rmin", "Rmin") if bend == "Euler" else None,
        "Bezier_Rmax": parameter("Bezier_Rmax", "Rmax") if bend == "Bezier" else None,
        "Bezier_Rmin": parameter("Bezier_Rmin", "Rmin") if bend == "Bezier" else None,
    }
    return length, annotation, params


def _stored_annotation(cell):
    """读取唯一有效的长度标注，同时保留其中的波导参数。"""
    layer = cell.layout().find_layer(pya.LayerInfo(10, 0))
    annotations = []
    if layer is not None:
        for shape in cell.shapes(layer).each():
            if not shape.is_text():
                continue
            text = shape.text.string
            if not text.startswith(("Waveguide width=", "Composite Waveguide ")):
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


def _waveguide_parameters(cell, annotation, scale, overrides=None):
    """优先读取 PCell 参数；无上下文的 GDS 从标注和参数化名称恢复。"""
    params = dict(cell.pcell_parameters_by_name())
    params.update(overrides or {})
    fields = {
        "width": "width", "radius": "radius", "straight_width": "ws",
        "bend_width": "wb", "start_width": "wstart", "end_width": "wend",
        "taper_length": "taper", "transition_length": "transition",
    }
    for key, token in fields.items():
        if _number(params.get(key)) is None:
            match = re.search(r"\b%s=([0-9]+(?:\.[0-9]+)?)um\b" % token, annotation)
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
    for key in (*fields, "bezier_k", "Euler_Rmax", "Euler_Rmin", "Bezier_Rmax", "Bezier_Rmin"):
        value = _number(params.get(key))
        result[key] = value * scale if value is not None and key != "bezier_k" else value
    if result["bend_type"] == "Bezier" and result["radius"] is not None and result["bezier_k"] is not None:
        result["Bezier_Rmax"], result["Bezier_Rmin"] = bezier_Rmax_Rmin(
            result["radius"], result["bezier_k"]
        )
    if result["bend_type"] == "Euler" and result["Euler_Rmax"] is not None and result["Euler_Rmin"] is not None:
        result["Euler_Reff"] = euler_Reff(result["Euler_Rmax"], result["Euler_Rmin"])
    return result


def _composite_length_data(cell, instance, annotation, total_length_um, params):
    """使用已保存的路径及实际宽度分段，不重生成或修改选中波导。"""
    dbu = cell.layout().dbu
    metadata = {}
    for target in (cell, instance):
        for key in (RAW_PATH_PROPERTY, RAW_PATH_GDS_PROPERTY):
            value = target.property(key)
            if value:
                try:
                    data = json.loads(str(value))
                except (ValueError, TypeError):
                    continue
                if isinstance(data, dict) and data.get("points_um"):
                    metadata = data
                    break
        if metadata:
            break
    native = cell.pcell_parameters_by_name()
    path = native.get("path")
    if isinstance(path, pya.DPath):
        points = [pya.Point(int(round(p.x / dbu)), int(round(p.y / dbu))) for p in path.each_point()]
    elif isinstance(path, pya.Path):
        points = list(path.each_point())
    else:
        points = [pya.Point(int(round(x / dbu)), int(round(y / dbu))) for x, y in metadata.get("points_um", [])]
    if len(points) < 2:
        raise WaveguideLengthError("missing_profile")
    keys = ("straight_width", "bend_width", "taper_length", "transition_length", "start_width", "end_width")
    for key in keys:
        if params.get(key) is None:
            params[key] = _number(metadata.get(key + "_um"))
        if params[key] is None:
            raise WaveguideLengthError("missing_profile")
    # 普通 GDS 的标注已经保存 Euler 有效半径，不能使用隐藏的普通 radius。
    if native and params["bend_type"] == "Euler":
        radius = params.get("Euler_Reff")
    else:
        match = re.search(r"\bradius=([0-9]+(?:\.[0-9]+)?)um\b", annotation)
        radius = float(match.group(1)) if match else params.get("radius")
    if radius is None:
        raise WaveguideLengthError("missing_profile")
    dimensions = {key: max(0 if "length" in key else 1, int(round(params[key] / dbu))) for key in keys}
    primitives, _ = build_route_skeleton(points, max(1, int(round(radius / dbu))))
    try:
        return profile_length_breakdown(
            primitives, total_length_um, dbu,
            *(dimensions[key] for key in keys),
        )
    except ValueError as error:
        raise WaveguideLengthError("missing_profile") from error


def describe_selected_waveguides(selection, cellview_index, include_spirals=False):
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
        kind = _waveguide_kind(instance.cell) if instance is not None and instance.cell is not None else None
        if kind is None and include_spirals and instance is not None and instance.cell is not None:
            kind = _spiral_kind(instance.cell)
        if kind is None or kind == "composite_spiral":
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
        overrides = None
        if kind in ("paperclip", "archimedean"):
            length, annotation, overrides = _spiral_data(instance.cell, kind)
        else:
            length, annotation = _stored_annotation(instance.cell)
        params = _waveguide_parameters(instance.cell, annotation, 1.0, overrides)
        if kind == "composite":
            lengths, excluded = _composite_length_data(instance.cell, instance, annotation, length, params)
        else:
            width = params["width"]
            if width is not None:
                dbu = instance.cell.layout().dbu
                width = max(1, int(round(width / dbu))) * dbu
            lengths, excluded = {width: length}, 0.0
        scaled_lengths = {
            round(width * scale, 12) if width is not None else None: value * scale
            for width, value in lengths.items()
        }
        counted_length = math.fsum(scaled_lengths.values())
        details.append({
            "cell_name": instance.cell.name,
            "kind": kind,
            "copies": copies,
            "length_um": counted_length,
            "total_length_um": counted_length * copies,
            "length_by_width_um": scaled_lengths,
            "excluded_taper_length_um": excluded * scale,
            "parameters": {
                key: value * scale if isinstance(value, (int, float)) and key != "bezier_k" else value
                for key, value in params.items()
            },
        })
    return details


def describe_selected_length_objects(selection, cellview_index):
    """预检全部选中项，含复合 Spiral 时整批拒绝，不返回部分统计。"""
    selected = list(selection)
    for obj in selected:
        if obj.is_cell_inst() and obj.cv_index == cellview_index:
            instance = obj.inst()
            if instance is not None and instance.cell is not None and _spiral_kind(instance.cell) == "composite_spiral":
                raise WaveguideLengthError("composite_spiral")
    return describe_selected_waveguides(selected, cellview_index, include_spirals=True)


def measure_selected_waveguides(selection, cellview_index):
    """保持原接口，返回实例数量与总长（µm）。"""
    details = describe_selected_waveguides(selection, cellview_index)
    return sum(item["copies"] for item in details), math.fsum(
        item["total_length_um"] for item in details
    )


def compare_selected_waveguides(selection, cellview_index):
    """比较两个独立实例，返回明细及绝对长度差；整组阵列不得代替单个波导。"""
    details = describe_selected_waveguides(selection, cellview_index)
    if len(details) != 2 or any(item["copies"] != 1 for item in details):
        raise WaveguideLengthError("not_two")
    return details, abs(details[0]["length_um"] - details[1]["length_um"])
