# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-08

"""在 KLayout DRC 解释器中验证 JNU 当前 Cell DRC 临时宏能够实际执行。"""

import os
from pathlib import Path
import sys
import tempfile

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

from JNU_MWP_tools.actions import drc  # noqa: E402


def main():
    """写出最小 GDS，验证临时宏与当前 LayoutView 的完整执行流程。"""
    layout = pya.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("DRC_EXECUTION_TOP")
    si_layer = layout.layer(pya.LayerInfo(1, 0))
    top.shapes(si_layer).insert(pya.Box(0, 0, 1000, 500))

    with tempfile.TemporaryDirectory(prefix="jnu_mwp_drc_execution_") as directory:
        input_path = os.path.join(directory, "input.gds")
        report_path = os.path.join(directory, "result.lyrdb")
        layout.write(input_path)
        macro_path = drc.write_temporary_drc_macro(
            drc.build_drc_text(
                drc.load_persisted_drc_code(), input_path, top.name, report_path,
            )
        )
        try:
            pya.Macro(macro_path).run()
            if not os.path.isfile(report_path):
                raise RuntimeError("DRC 没有生成报告文件。")
        finally:
            if os.path.isfile(macro_path):
                os.remove(macro_path)

    app = pya.Application.instance()
    main_window = app.main_window() if app is not None else None
    if main_window is None:
        raise RuntimeError("该测试需要 KLayout GUI 或隐藏 GUI 模式。")
    cellview = main_window.create_layout(1)
    active_layout = cellview.layout()
    active_layout.dbu = 0.001
    active_top = active_layout.create_cell("DRC_ACTIVE_CELL")
    active_si = active_layout.layer(pya.LayerInfo(1, 0))
    active_top.shapes(active_si).insert(pya.Box(0, 0, 1000, 500))
    cellview.cell = active_top

    # Macro Development 工具栏直接运行同一 .lydrc 时也必须不抛出类型错误。
    try:
        pya.Macro(str(drc.drc_macro_path())).run()
    except Exception as error:
        raise RuntimeError("原生 Macro Development DRC 执行失败：%s" % error)

    errors = []
    original_show_error = drc._show_error
    try:
        # 隐藏 GUI 中禁止弹出阻塞 MessageBox，保留原始错误文本供断言输出。
        drc._show_error = lambda message: errors.append(str(message))
        if not drc.run_current_cell_drc():
            raise RuntimeError("当前 Cell DRC 执行失败：%s" % "\n".join(errors))
    finally:
        drc._show_error = original_show_error
    print("OK: JNU current-cell DRC temporary macro executed successfully")


if __name__ == "__main__":
    main()
