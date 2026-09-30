# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

"""为布局本地波导 PCell variant 保留可读且不冲突的 cell 名称。"""

import re


INTERNAL_WAVEGUIDE_NAMES = ("Waveguide", "Composite_Waveguide")


def name_waveguide_variant(layout, cell, display_name):
    """在 PCell 生产时命名，覆盖复制实例后由 KLayout 新建 variant 的路径。"""
    base = str(display_name or "")
    if not base or base in INTERNAL_WAVEGUIDE_NAMES:
        return str(cell.name)

    current = str(cell.name)
    # GDS 读入期间 variant 尚未得到文件中的 cell 名；此时改名会产生 $N 冲突。
    if not current:
        return current
    if current == base or re.fullmatch(re.escape(base) + r"__[0-9]{3}", current):
        return current

    candidate = base
    index = 2
    while True:
        existing = layout.cell(candidate)
        if existing is None or existing.cell_index() == cell.cell_index():
            cell.name = candidate
            return str(cell.name)
        candidate = "%s__%03d" % (base, index)
        index += 1


def normalize_local_waveguide_names(layout):
    """文件重读后恢复旧版无参数后缀名称，保持已有实例和几何不变。"""
    renamed = []
    for cell in list(layout.each_cell()):
        if not cell.is_pcell_variant() or cell.pcell_library() is not None:
            continue
        declaration = cell.pcell_declaration()
        if declaration is None or declaration.name() not in INTERNAL_WAVEGUIDE_NAMES:
            continue
        original = str(cell.name)
        title = cell.display_title()
        result = name_waveguide_variant(layout, cell, title)
        if result != original:
            renamed.append((original, result))
    return renamed
