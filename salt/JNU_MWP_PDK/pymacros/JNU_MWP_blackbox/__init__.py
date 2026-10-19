# $autorun
# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

# JNULib_BlackBox 黑盒器件库初始化脚本。
# 直接加载已验收的黑盒 GDS，保留 BlackBox 主体、Si 端口直段及 PinRec。

import os
import sys

import pya


# KLayout 启动宏时不一定包含当前目录，这里显式加入黑盒目录和 pymacros 目录。
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
PYMACROS_DIR = os.path.dirname(SCRIPT_DIR)
for directory in (SCRIPT_DIR, PYMACROS_DIR):
    if directory not in sys.path:
        sys.path.insert(0, directory)

# 固定 GDS 器件和识别层定义。
LIBRARY_DBU = 0.001                  # JNU_MWP_PDK 的数据库单位，1 nm。
# 与白盒库相同：稳定注册名保证版本升级后已放置器件仍可识别。
LIBRARY_NAME = "JNULib_BlackBox"
LEGACY_LIBRARY_NAMES = ("JNULib_BlackBox_v1.1", "JNULib_BlackBox_v1.0")
BLACKBOX_GDS_DIR = os.path.join(PYMACROS_DIR, "JNU_MWP_blackbox_gds")
from JNU_MWP_tools.core.pdk_identity import TECHNOLOGY_NAME


def _directory_has_gds(directory):
    """判断目录中是否存在 GDS 文件。"""
    if not os.path.isdir(directory):
        return False
    return any(filename.lower().endswith(".gds") for filename in os.listdir(directory))


def _active_gds_dir():
    """只加载预生成黑盒，避免运行时从白盒误导出内部结构。"""
    return BLACKBOX_GDS_DIR if _directory_has_gds(BLACKBOX_GDS_DIR) else None



def _delete_existing_library(library_name):
    """删除同名旧库，避免 KLayout 热重载时保留旧的 PCell 或 cell 状态。"""
    for library_id in list(pya.Library.library_ids()):
        library = pya.Library.library_by_id(library_id)
        if library and library.name() == library_name:
            library.delete()


def _load_gds_blackbox(ly):
    """原样复制预生成黑盒的全部层级，不重新用 Si 包围盒生成实体块。"""
    gds_dir = _active_gds_dir()
    if gds_dir is None:
        print("%s: GDS directory not found: %s" % (LIBRARY_NAME, BLACKBOX_GDS_DIR))
        return

    names = set()
    for filename in sorted(os.listdir(gds_dir)):
        if not filename.lower().endswith(".gds") or filename.startswith("Pcell_"):
            continue
        temporary = pya.Layout()
        temporary.read(os.path.join(gds_dir, filename))
        for source in temporary.each_top_cell():
            source = temporary.cell(source) if isinstance(source, int) else source
            if source.name.startswith("Pcell_"):
                continue
            if source.name in names or source.bbox().empty():
                raise RuntimeError("黑盒名称重复或器件为空：%s" % source.name)
            names.add(source.name)
            target = ly.create_cell(source.name)
            # copy_tree 同时转换 dbu 并保留标签子单元、端口及非物理占位层。
            target.copy_tree(source)
            print("%s loaded: %s" % (LIBRARY_NAME, source.name))


class JNULibBlackBox(pya.Library):
    """JNU 微波光子黑盒器件库。"""

    def __init__(self):
        # 黑盒库同样保持稳定身份，并在 Library 面板说明栏显示发行版本。
        self.description = "v1.3, JNU MWP PDK black-box components [Technology %s]" % TECHNOLOGY_NAME

        ly = self.layout()

        # 显式固定黑盒库 dbu，避免 GUI 默认 dbu 造成固定 GDS 黑盒放大或缩小。
        ly.dbu = LIBRARY_DBU

        # 固定 GDS 已由发布流程生成，运行时保留其真实层级与图层。
        _load_gds_blackbox(ly)

        # 黑盒器件库只包含固定黑盒 cell，不注册任何 PCell。

        self.register(LIBRARY_NAME)


for legacy_library_name in LEGACY_LIBRARY_NAMES:
    _delete_existing_library(legacy_library_name)
_delete_existing_library(LIBRARY_NAME)
JNULibBlackBox()
