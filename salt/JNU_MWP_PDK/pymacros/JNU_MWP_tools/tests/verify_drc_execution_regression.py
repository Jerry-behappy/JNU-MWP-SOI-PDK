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
    """写出含确定违规的最小 GDS，验证报告中确实产生 marker。"""
    layout = pya.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("DRC_EXECUTION_TOP")
    si_layer = layout.layer(pya.LayerInfo(1, 0))
    pin_layer = layout.layer(pya.LayerInfo(1, 10))
    # 40 nm 宽 Si 明确违反 60 nm 最小宽度；远离 Si 的 PinRec 明确违反端口相交规则。
    top.shapes(si_layer).insert(pya.Box(0, 0, 1000, 40))
    top.shapes(pin_layer).insert(
        pya.Path([pya.Point(2000, 0), pya.Point(2020, 0)], 500)
    )

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
            report_database = pya.ReportDatabase()
            report_database.load(report_path)
            if report_database.num_items() < 2:
                raise RuntimeError(
                    "DRC 报告未包含预期的 Si 宽度和 PinRec 违规：%d。"
                    % report_database.num_items()
                )
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
    active_pin = active_layout.layer(pya.LayerInfo(1, 10))
    active_top.shapes(active_si).insert(pya.Box(0, 0, 1000, 40))
    active_top.shapes(active_pin).insert(
        pya.Path([pya.Point(2000, 0), pya.Point(2020, 0)], 500)
    )
    cellview.cell = active_top

    # Macro Development 工具栏连续运行同一 .lydrc 时，每次都必须新增非空报告。
    view = main_window.current_view()
    for run_number in (1, 2):
        report_count_before = view.num_rdbs()
        try:
            pya.Macro(str(drc.drc_macro_path())).run()
        except Exception as error:
            raise RuntimeError(
                "原生 Macro Development DRC 第 %d 次执行失败：%s"
                % (run_number, error)
            )
        report_count_after = view.num_rdbs()
        if report_count_after <= report_count_before:
            raise RuntimeError(
                "原生 Macro Development DRC 第 %d 次没有创建 Marker Database。"
                % run_number
            )
        native_report = view.rdb(report_count_after - 1)
        if native_report is None or native_report.num_items() < 2:
            marker_count = 0 if native_report is None else native_report.num_items()
            raise RuntimeError(
                "原生 Macro Development DRC 第 %d 次未显示预期版图错误：%d。"
                % (run_number, marker_count)
            )

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
