# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

# JNU_MWP_tools 分类入口。
# core 保存公共计算与端口基础，actions 保存 KLayout 菜单功能，
# release 保存发布流程，tests 保存回归脚本。

import importlib
import sys


# 旧版脚本可能仍使用 JNU_MWP_tools.<module> 导入。模块实体已经迁入
# core/actions 子包，这里建立运行时别名，不在根目录保留重复包装文件。
_LEGACY_MODULE_TARGETS = {
    "bend_curvature": "JNU_MWP_tools.core.bend_curvature",
    "bend_sampling": "JNU_MWP_tools.core.bend_sampling",
    "common": "JNU_MWP_tools.core.common",
    "make_pin": "JNU_MWP_tools.core.make_pin",
    "layer_exclude": "JNU_MWP_tools.actions.layer_exclude",
    "make_pins_for_cell": "JNU_MWP_tools.actions.make_pins_for_cell",
    "numerical_text_array": "JNU_MWP_tools.actions.numerical_text_array",
    "path_to_waveguide": "JNU_MWP_tools.actions.path_to_waveguide",
    "sbend_connect": "JNU_MWP_tools.actions.sbend_connect",
    "snap_components": "JNU_MWP_tools.actions.snap_components",
    "waveguide_to_path": "JNU_MWP_tools.actions.waveguide_to_path",
    "waveguide_tools": "JNU_MWP_tools.actions.waveguide_tools",
}

for _legacy_name, _target_name in _LEGACY_MODULE_TARGETS.items():
    _qualified_name = "%s.%s" % (__name__, _legacy_name)
    if _qualified_name not in sys.modules:
        sys.modules[_qualified_name] = importlib.import_module(_target_name)

__all__ = []
