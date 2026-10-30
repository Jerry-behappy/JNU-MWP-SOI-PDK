# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""恢复 PCell 前比较缓存几何，允许多边形起点或绕向不同。"""

from collections import Counter

import pya


def _properties(obj):
    return tuple(sorted((repr(key), repr(value)) for key, value in obj.properties().items()))


def _layer_geometry(cell, layer):
    areas, others = {}, Counter()
    for shape in cell.shapes(layer).each():
        props = _properties(shape)
        if shape.is_polygon() or shape.is_box():
            region = areas.setdefault(props, pya.Region())
            region.insert(shape.polygon if shape.is_polygon() else shape.box)
        elif shape.is_text():
            text = shape.text
            others[("text", text.string, text.trans.to_s(), text.size, text.font,
                    str(text.halign), str(text.valign), props)] += 1
        else:
            others[(shape.to_s(), props)] += 1
    return areas, others


def cell_geometry_equal(first, second, names=None):
    """比较所有层的图形、文字、端口路径与子实例，不要求 PCell 身份相同。"""
    if second is None or first.layout().dbu != second.layout().dbu:
        return False
    if not set(_properties(first)) <= set(_properties(second)):
        return False
    layouts = first.layout(), second.layout()
    layers = [{lo.get_info(li).to_s(): li for li in lo.layer_indices() if cell.shapes(li).size()}
              for lo, cell in zip(layouts, (first, second))]
    if set(layers[0]) != set(layers[1]):
        return False
    for spec in layers[0]:
        before, before_other = _layer_geometry(first, layers[0][spec])
        after, after_other = _layer_geometry(second, layers[1][spec])
        if before_other != after_other or set(before) != set(after):
            return False
        if any(not (before[key] ^ after[key]).is_empty() for key in before):
            return False

    def instances(cell, rename):
        return Counter((rename.get(inst.cell.name, inst.cell.name), inst.cplx_trans.to_s(),
                        inst.a.to_s(), inst.b.to_s(), inst.na, inst.nb, _properties(inst))
                       for inst in cell.each_inst())

    return instances(first, names or {}) == instances(second, {})


def layout_geometry_equal(first, second, names=None):
    """逐 cell 检查全部层级，避免恢复波导时连带改变其他器件。"""
    names = names or {}
    if not set(_properties(first)) <= set(_properties(second)):
        return False
    before_names = {names.get(cell.name, cell.name) for cell in first.each_cell()}
    if before_names != {cell.name for cell in second.each_cell()}:
        return False
    if {names.get(c.name, c.name) for c in first.top_cells()} != {c.name for c in second.top_cells()}:
        return False
    return all(cell_geometry_equal(cell, second.cell(names.get(cell.name, cell.name)), names)
               for cell in first.each_cell())
