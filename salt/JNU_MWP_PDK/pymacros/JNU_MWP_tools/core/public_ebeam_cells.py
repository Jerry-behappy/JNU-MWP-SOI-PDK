# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""EBeam 来源器件的统一名称，以及旧白盒文件的读取兼容映射。"""


PUBLIC_EBEAM_CELLS = (
    ("ebeam_crossing4", "1550_crossing4"),
    ("ebeam_terminator_te1310", "1310_500nm_TE_terminator"),
    ("ebeam_terminator_te1550", "1550_500nm_TE_terminator"),
    ("ebeam_y_1310", "1310_Ybranch"),
    ("ebeam_y_1550", "1550_Ybranch"),
)


# 新白盒文件名、顶层 cell 名与器件库名称一致；旧名称仅用于兼容读取。
PUBLIC_EBEAM_CELL_NAMES = tuple(name for _, name in PUBLIC_EBEAM_CELLS)

FIXED_CELL_ALIASES = dict(PUBLIC_EBEAM_CELLS)
FIXED_CELL_ALIASES.update({
    "1310_TE_Terminator": "1310_500nm_TE_terminator",
    "1550_TE_Terminator": "1550_500nm_TE_terminator",
    "1550_2um_terminator": "1550_2um_TE_terminator",
})

# 旧 MMI 名称只用于读取旧白盒，新资源统一采用 ASCII x。
FIXED_CELL_ALIASES.update({
    "1310_4*4_MMI": "1310_4x4_MMI",
    "1550_1*2_MMI": "1550_1x2_MMI",
    "1550_1*4_MMI": "1550_1x4_MMI",
    "1550_2*2_MMI_2um-InputPort_for_TE0": "1550_2x2_MMI_2um-InputPort_for_TE0",
    "1550_4*4_MMI": "1550_4x4_MMI",
})
FIXED_CELL_ALIASES.update({name.replace("*", "×"): target
                           for name, target in tuple(FIXED_CELL_ALIASES.items()) if "*" in name})

__all__ = ["PUBLIC_EBEAM_CELLS", "PUBLIC_EBEAM_CELL_NAMES", "FIXED_CELL_ALIASES"]
