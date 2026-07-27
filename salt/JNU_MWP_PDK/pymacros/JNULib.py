# $autorun
# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

# JNULib KLayout 器件库加载器。
# 从指定 GDS 目录加载固定版图单元（fixed_gds 器件），
# 并注册供用户直接放置的参数化 PCell。工具内部使用的波导 PCell
# 由 Path to Waveguide 在当前版图中按需注册，不进入公开器件列表。

import os        # 路径和文件操作
import sys       # 模块搜索路径管理

import pya       # KLayout Python API


# KLayout 启动宏时不一定把当前文件夹加入 sys.path，
# 因此手动加入路径，保证可以导入同目录下的 PCell 文件。
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
# 库注册名是布局中 PCell 身份的一部分，因此必须保持稳定，不能随发行版本变化。
# 发行版本可记录在发布包和变更记录中，但不得写入 Library 面板的识别名称。
LIBRARY_NAME = "JNULib"
LEGACY_LIBRARY_NAMES = ("JNULib_v1.1", "JNULib_v1.0")
# 固定的版图库目录：这里存放已经画好的 GDS 顶层单元。
GDS_DIR = os.path.join(SCRIPT_DIR, "JNU_MWP_gds")

if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from JNU_MWP_pcells import (
    Bend90deg,
    MicroringDoubleBus,
    PaperclipSpiral,
    PaperclipSpiralWithCompositeWaveguide,
    SBendWaveguide,
    StraightWaveguide,
    ArchimedeanSpiral,
    Taper,
)
from JNU_MWP_tools.core.ebeam_library_bridge import register_ebeam_libraries_for_jnu


def _delete_existing_library(library_name):
    """删除同名旧库，避免 KLayout 热重载时保留旧的 PCell 注册状态。"""
    for library_id in list(pya.Library.library_ids()):
        library = pya.Library.library_by_id(library_id)
        if library and library.name() == library_name:
            library.delete()


class JNULib(pya.Library):
    """JNU 微波光子器件库：加载固定 GDS 单元并注册本地 PCell。"""

    def __init__(self):
        # 库名保持稳定用于 PCell 识别；发行版本放在说明栏，供 Library 面板显示。
        self.description = "v1.1, JNU MWP PDK components [Technology JNU_MWP_PDK]"
        # 器件库保持全局可见，不绑定到 JNU_MWP_PDK technology，
        # 这样切换到其他 technology 时仍可同时调用 JNU 和 EBeam 等器件库。

        ly = self.layout()

        # 先把外部 GDS 中已有的器件加载进库，再注册参数化器件。
        self._load_gds_cells(ly)
        self._register_pcells(ly)

        self.register(LIBRARY_NAME)

    def _load_gds_cells(self, ly):
        """把 GDS_DIR 目录里的每个 GDS 顶层 cell 复制到 JNULib。"""

        if not os.path.isdir(GDS_DIR):
            print("%s: GDS directory not found: %s" % (LIBRARY_NAME, GDS_DIR))
            return

        for filename in sorted(os.listdir(GDS_DIR)):
            if not filename.lower().endswith(".gds"):
                continue

            fullpath = os.path.join(GDS_DIR, filename)
            temp = pya.Layout()
            temp.read(fullpath)

            for top_cell in temp.each_top_cell():
                # KLayout 不同版本的 each_top_cell 可能返回 cell index 或 cell 对象。
                cell = temp.cell(top_cell) if isinstance(top_cell, int) else top_cell
                print("%s loading: %s" % (LIBRARY_NAME, cell.name))

                new_cell = ly.create_cell(cell.name)
                new_cell.copy_tree(cell)

    def _register_pcells(self, ly):
        """注册需要出现在 Library 面板中的 PCell。"""

        ly.register_pcell("Bend_90deg", Bend90deg())
        ly.register_pcell("Microring_DoubleBus", MicroringDoubleBus())
        ly.register_pcell("Archimedean_Spiral", ArchimedeanSpiral())
        ly.register_pcell("Paperclip_Spiral", PaperclipSpiral())
        ly.register_pcell("Paperclip_Spiral_with_Composite_Waveguide", PaperclipSpiralWithCompositeWaveguide())
        ly.register_pcell("Taper", Taper())
        ly.register_pcell("S_Bend", SBendWaveguide())
        ly.register_pcell("Straight_Waveguide", StraightWaveguide())


for legacy_library_name in LEGACY_LIBRARY_NAMES:
    _delete_existing_library(legacy_library_name)
_delete_existing_library(LIBRARY_NAME)
JNULib()

# EBeam PDK 已加载时，为 JNU Technology 注册同名器件库视图。该视图只改变
# Library 面板按 Technology 的筛选结果，不会修改 EBeam 的原库、PCell 或图层定义。
try:
    register_ebeam_libraries_for_jnu()
except Exception as error:
    print("%s: EBeam library bridge skipped: %s" % (LIBRARY_NAME, error))
