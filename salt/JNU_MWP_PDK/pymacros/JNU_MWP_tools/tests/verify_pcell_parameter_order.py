# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""验证 JNU 全部 PCell 的可编辑/只读参数分区顺序。"""

from pathlib import Path
import sys

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

import JNULib  # noqa: E402,F401  注册 JNULib
from JNU_MWP_pcells import CompositeWaveguide, Waveguide  # noqa: E402


LIBRARY_NAME = "JNULib"


def _check_declaration(pcell_name, declaration):
    """检查一个 PCell 声明的可编辑/只读参数顺序。"""
    readonly_started = False
    readonly_count = 0
    for parameter in declaration.get_parameters():
        is_readonly = bool(parameter.readonly)
        if readonly_started and not is_readonly:
            raise RuntimeError(
                "%s: 可编辑参数 %s 位于只读参数之后。"
                % (pcell_name, parameter.name)
            )
        if is_readonly:
            readonly_started = True
            readonly_count += 1
            if not str(parameter.description).endswith(" [uneditable]"):
                raise RuntimeError(
                    "%s.%s 的界面名称未以 [uneditable] 结尾。"
                    % (pcell_name, parameter.name)
                )
    return readonly_count


def main():
    """检查只读参数位于末尾，且界面名称明确标注不可编辑。"""
    library = pya.Library.library_by_name(LIBRARY_NAME)
    if library is None:
        raise RuntimeError("未找到 %s。" % LIBRARY_NAME)

    layout = library.layout()
    checked = 0
    readonly_count = 0
    for pcell_name in sorted(layout.pcell_names()):
        declaration = layout.pcell_declaration(pcell_name)
        if declaration is None:
            raise RuntimeError("无法读取 PCell 声明: %s" % pcell_name)
        readonly_count += _check_declaration(pcell_name, declaration)
        checked += 1

    # 工具内部波导 PCell 不进入公开 JNULib，仍必须遵守同一参数顺序规则。
    for pcell_name, declaration in (
        ("Waveguide [internal]", Waveguide()),
        ("Composite_Waveguide [internal]", CompositeWaveguide()),
    ):
        readonly_count += _check_declaration(pcell_name, declaration)
        checked += 1

    print(
        "OK: PCell=%d, readonly=%d; editable parameters precede readonly parameters."
        % (checked, readonly_count)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
