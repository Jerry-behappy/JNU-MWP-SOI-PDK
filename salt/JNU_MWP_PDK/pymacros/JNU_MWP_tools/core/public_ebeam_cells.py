# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""独立白盒库 EBeam 原始 cell 与 JNU 器件库名称的固定映射。"""


PUBLIC_EBEAM_CELLS = (
    ("ebeam_crossing4", "Crossing4"),
    ("ebeam_terminator_te1310", "1310_TE_Terminator"),
    ("ebeam_terminator_te1550", "1550_TE_Terminator"),
    ("ebeam_y_1310", "1310_Ybranch"),
    ("ebeam_y_1550", "1550_Ybranch"),
)


__all__ = ["PUBLIC_EBEAM_CELLS"]
