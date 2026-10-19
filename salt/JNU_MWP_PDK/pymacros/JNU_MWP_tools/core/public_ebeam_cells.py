# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""EBeam 来源器件的统一名称，以及旧白盒文件的读取兼容映射。"""


PUBLIC_EBEAM_CELLS = (
    ("ebeam_crossing4", "1550_crossing4"),
    ("ebeam_terminator_te1310", "1310_TE_Terminator"),
    ("ebeam_terminator_te1550", "1550_TE_Terminator"),
    ("ebeam_y_1310", "1310_Ybranch"),
    ("ebeam_y_1550", "1550_Ybranch"),
)


# 新白盒文件名、顶层 cell 名与器件库名称一致；旧名称仅用于兼容读取。
PUBLIC_EBEAM_CELL_NAMES = tuple(name for _, name in PUBLIC_EBEAM_CELLS)


__all__ = ["PUBLIC_EBEAM_CELLS", "PUBLIC_EBEAM_CELL_NAMES"]
