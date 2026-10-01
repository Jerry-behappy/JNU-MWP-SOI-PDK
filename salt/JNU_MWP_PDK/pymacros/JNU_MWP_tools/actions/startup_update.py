# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""KLayout 启动后异步检查公开 PDK 的 main 更新。"""

import builtins
import queue
import threading

import pya

from JNU_MWP_tools.actions.install_pdk import probe_main_update, show_installer
from JNU_MWP_tools.core.ui_language import LANGUAGE_ZH, active_language


_SESSION_KEY = "_jnu_mwp_pdk_startup_update_scheduled"
_ACTIVE_CHECK = None


def _confirm_update(main_window, revisions):
    """只在 GUI 主线程询问；确认后直接启动现有安全更新流程。"""
    chinese = active_language() == LANGUAGE_ZH
    message = pya.QMessageBox(main_window)
    message.setIcon(pya.QMessageBox.Information)
    message.setWindowTitle("JNU PDK 更新" if chinese else "JNU PDK Update")
    message.setText(
        "当前 JNU PDK 与 GitHub main 版本不同，是否立即更新？"
        if chinese else "Your JNU PDK differs from GitHub main. Update now?"
    )
    message.setInformativeText(
        ("当前：%s；远端 main：%s。仅当本地 main 干净且可以快进时才会更新；完成后请重启 KLayout。"
         if chinese else
         "Installed: %s; GitHub main: %s. The update requires a clean main branch that can fast-forward. Restart KLayout when it finishes.")
        % (revisions[0][:8], revisions[1][:8])
    )
    message.setStandardButtons(pya.QMessageBox.Yes | pya.QMessageBox.No)
    message.button(pya.QMessageBox.Yes).setText("立即更新" if chinese else "Update now")
    message.button(pya.QMessageBox.No).setText("稍后" if chinese else "Later")
    message.setDefaultButton(pya.QMessageBox.No)
    if pya.QMessageBox_StandardButton(message.exec_()) == pya.QMessageBox.Yes:
        show_installer("update", auto_start=True)


def schedule_startup_update_check():
    """每个 KLayout 进程检查一次；网络和 Git 操作不阻塞界面。"""
    global _ACTIVE_CHECK
    if getattr(builtins, _SESSION_KEY, False):
        return False
    app = pya.Application.instance()
    main_window = app.main_window() if app is not None else None
    if main_window is None:
        return False

    home = str(app.application_data_path())
    events = queue.Queue()
    timer = pya.QTimer(main_window)
    timer.setInterval(100)

    def worker():
        try:
            revisions = probe_main_update(home)
        except Exception:
            revisions = None
        events.put(revisions)

    def poll():
        global _ACTIVE_CHECK
        try:
            revisions = events.get_nowait()
        except queue.Empty:
            return
        timer.stop()
        _ACTIVE_CHECK = None
        if revisions is not None:
            _confirm_update(main_window, revisions)

    timer.timeout(poll)
    _ACTIVE_CHECK = (timer, poll)
    setattr(builtins, _SESSION_KEY, True)
    threading.Thread(target=worker, daemon=True).start()
    timer.start()
    return True
