# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

"""保存 JNU 界面语言选择并提示重启 KLayout。"""

import pya

from JNU_MWP_tools.core.ui_language import LANGUAGE_ZH, active_language, set_next_language


def choose_language(language):
    try:
        set_next_language(language)
    except (OSError, ValueError) as error:
        if active_language() == LANGUAGE_ZH:
            message = "保存语言设置失败：%s" % error
        else:
            message = "Could not save language preference: %s" % error
        pya.MessageBox.critical("JNU_MWP_PDK", message, pya.MessageBox.Ok)
        return

    if active_language() == LANGUAGE_ZH:
        message = "语言设置已保存。请重启 KLayout，使菜单和 PCell 参数界面更新。"
    else:
        message = "Language preference saved. Restart KLayout to update menus and PCell parameters."
    pya.MessageBox.info("JNU_MWP_PDK", message, pya.MessageBox.Ok)
