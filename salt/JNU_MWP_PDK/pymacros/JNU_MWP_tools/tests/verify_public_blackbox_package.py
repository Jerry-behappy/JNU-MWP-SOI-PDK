# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""构建一次隔离黑盒交付目录并重读全部器件与源码排除项。"""

import os
from pathlib import Path
import sys

import pya


PYMACROS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PYMACROS))
from JNU_MWP_tools.release.package_blackbox_pdk import package_blackbox_pdk


def main():
    output = Path(os.environ["JNU_BLACKBOX_TEST_OUTPUT"])
    assert not output.exists(), "测试包目录必须为新目录"
    count, package, _ = package_blackbox_pdk(output)
    assert count == 30, count
    macros = package / "pymacros"
    assert not (macros / "JNU_MWP_pcells").exists()
    assert not (macros / "JNU_MWP_ebeam_gds").exists()
    assert not (macros / "JNU_MWP_gds").exists()
    assert not (macros / "JNULib.py").exists()
    assert not (macros / "JNU_MWP_tools" / "release").exists()
    assert (package / "LICENSE.md").is_file()
    assert (macros / "JNU_MWP_blackbox_gds" / "NOTICE.md").is_file()
    names = set()
    for path in sorted((macros / "JNU_MWP_blackbox_gds").glob("*.gds")):
        layout = pya.Layout()
        layout.read(str(path))
        for top in layout.each_top_cell():
            cell = layout.cell(top) if isinstance(top, int) else top
            assert cell.name not in names, cell.name
            names.add(cell.name)
            si = list(cell.shapes(layout.layer(1, 0)).each())
            assert len(si) == 1 and si[0].is_box(), cell.name
    assert len(names) == 30, len(names)
    assert {"Crossing4", "1310_TE_Terminator", "1550_TE_Terminator",
            "1310_Ybranch", "1550_Ybranch", "Pcell_Waveguide_Bump"} <= names
    assert not {"ebeam_crossing4", "ebeam_terminator_te1310", "ebeam_terminator_te1550",
                "ebeam_y_1310", "ebeam_y_1550"} & names
    print("PASS: 30 blackbox cells in standalone package; no whitebox GDS or PCell source.")


if __name__ == "__main__":
    main()
