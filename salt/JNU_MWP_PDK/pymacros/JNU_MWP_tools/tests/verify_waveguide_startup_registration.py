# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-08

"""验证 KLayout 启动入口会在 GDS 读取前注册内部 Waveguide PCell。"""

import os
from pathlib import Path
import runpy
import sys
import tempfile

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

from JNU_MWP_tools.actions.path_to_waveguide import _create_waveguide_cell  # noqa: E402
from JNU_MWP_tools.core import internal_waveguide_registry  # noqa: E402
from JNU_MWP_tools.core.internal_waveguide_registry import ensure_internal_waveguide_pcells  # noqa: E402


def _waveguide_params():
    """提供生成一条最小内部 Waveguide PCell 所需的完整参数。"""
    return {
        "mode": "single",
        "width": 0.5,
        "radius": 20.0,
        "bend_type": "Bezier",
        "bezier": 0.35,
        "Euler_Rmax": 30.0,
        "Euler_Rmin": 10.0,
    }


def _write_source_gds(filename):
    """创建含真实本地 Waveguide PCell variant 的源 GDS。"""
    layout = pya.Layout()
    layout.dbu = 0.001
    ensure_internal_waveguide_pcells(layout)
    top = layout.create_cell("WAVEGUIDE_STARTUP_TOP")
    dpath = pya.DPath(
        [pya.DPoint(0, 0), pya.DPoint(80, 0), pya.DPoint(80, 60)], 0.5,
    )
    waveguide = _create_waveguide_cell(layout, dpath, _waveguide_params(), 1)
    top.insert(pya.CellInstArray(waveguide.cell_index(), pya.Trans()))
    layout.write(filename)


def _flush_gui_events():
    """进入一次短暂 Qt 事件循环，确保 View 创建回调已经执行。"""
    dialog = pya.QDialog()
    timer = pya.QTimer(dialog)
    timer.setSingleShot(True)
    timer.timeout(dialog.accept)
    timer.start(350)
    dialog.exec_()


def _run_view_file_open_hook(view):
    """调用已安装的 KLayout 文件读入回调，模拟 File/Open 完成时序。"""
    for owner, callback in internal_waveguide_registry._REGISTRATION_STATE["view_file_open_hooks"]:
        try:
            matches = owner == view
        except Exception:
            matches = id(owner) == id(view)
        if matches:
            callback()
            return
    raise RuntimeError("新建 LayoutView 未安装 on_file_open Waveguide 恢复回调。")


def main():
    """模拟独立 autorun 启动后创建 LayoutView 并读取已有 Waveguide GDS。"""
    with tempfile.TemporaryDirectory(prefix="jnu_waveguide_startup_") as directory:
        gds_path = os.path.join(directory, "waveguide_restart.gds")
        _write_source_gds(gds_path)

        # run_path 模拟 KLayout 将 pymacros/__init__.py 作为独立 autorun 宏执行。
        # 若实际 KLayout 已经自动加载完成，则避免第二次运行 autorun 覆盖事件状态。
        if not internal_waveguide_registry._REGISTRATION_STATE["main_window_hooks"]:
            runpy.run_path(str(PYMACROS_DIR / "__init__.py"), run_name="__jnu_autorun_test__")

        app = pya.Application.instance()
        main_window = app.main_window() if app is not None else None
        if main_window is None:
            raise RuntimeError("该测试需要 KLayout GUI 或隐藏 GUI 模式。")
        cellview = main_window.create_layout(1)
        _flush_gui_events()
        layout = cellview.layout()
        layout.read(gds_path)
        _run_view_file_open_hook(main_window.current_view())
        if layout.pcell_declaration("Waveguide") is None:
            raise RuntimeError("文件读入回调未注册 Waveguide PCell。")
        if layout.pcell_declaration("Composite_Waveguide") is None:
            raise RuntimeError("文件读入回调未注册 Composite_Waveguide PCell。")
        top = layout.cell("WAVEGUIDE_STARTUP_TOP")
        if top is None:
            raise RuntimeError("重读 GDS 后缺少顶层 cell。")
        instances = list(top.each_inst())
        if len(instances) != 1:
            raise RuntimeError("重读 GDS 后 Waveguide 实例数量错误。")
        waveguide = instances[0].cell
        if not waveguide.is_pcell_variant():
            raise RuntimeError("GDS 重读后 Waveguide 未恢复为 PCell variant。")
        if "$" in waveguide.name or waveguide.name == "Waveguide":
            raise RuntimeError("GDS 重读后 Waveguide cell 名称退化：%s" % waveguide.name)

        # 原始 Layout 读入同样必须在 read() 前预注册；GDS 解析后再补注册无法可靠
        # 恢复为 PCell variant，因此启动路径必须始终先完成本地声明注册。
        pre_registered_layout = pya.Layout()
        ensure_internal_waveguide_pcells(pre_registered_layout)
        pre_registered_layout.read(gds_path)
        pre_registered_top = pre_registered_layout.cell("WAVEGUIDE_STARTUP_TOP")
        pre_registered_instance = list(pre_registered_top.each_inst())[0]
        if not pre_registered_instance.cell.is_pcell_variant():
            raise RuntimeError("预注册后原始 Layout 读入未恢复 Waveguide PCell。")
        if "$" in pre_registered_instance.cell.name:
            raise RuntimeError(
                "预注册后原始 Layout 读入的 Waveguide 名称退化：%s" %
                pre_registered_instance.cell.name
            )

    print("OK: autorun startup registered internal Waveguide PCells before GDS read")


if __name__ == "__main__":
    main()
