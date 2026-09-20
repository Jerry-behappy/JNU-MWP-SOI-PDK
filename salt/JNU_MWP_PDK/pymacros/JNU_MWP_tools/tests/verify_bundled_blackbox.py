# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

"""验证仓库自带黑盒数据可独立加载，且没有泄露内部物理版图。"""

from pathlib import Path
import sys

import pya


PYMACROS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PYMACROS))
import JNU_MWP_blackbox as blackbox


def main():
    directory = PYMACROS / "JNU_MWP_blackbox_gds"
    files = sorted(directory.glob("*.gds"))
    assert files, "仓库未携带黑盒 GDS"
    assert Path(blackbox._active_gds_dir()).resolve() == directory.resolve()
    names = set()
    for path in files:
        layout = pya.Layout()
        layout.read(str(path))
        for top in layout.each_top_cell():
            cell = layout.cell(top) if isinstance(top, int) else top
            assert cell.name not in names, "器件名称重复：%s" % cell.name
            names.add(cell.name)
            # 物理版图必须只有单一矩形；PinRec 和标签不能携带内部结构。
            si = list(cell.shapes(layout.layer(1, 0)).each())
            assert len(si) == 1 and si[0].is_box(), cell.name
            assert not si[0].box.empty(), cell.name
            pins = list(cell.shapes(layout.layer(1, 10)).each())
            assert any(shape.is_path() for shape in pins), "缺少端口：%s" % cell.name
            assert any(shape.is_text() for shape in pins), "缺少端口名称：%s" % cell.name
            devrec = list(cell.shapes(layout.layer(68, 0)).each())
            assert len(devrec) == 1 and devrec[0].is_box(), cell.name
        for cell in layout.each_cell():
            for index in layout.layer_indices():
                info = layout.get_info(index)
                shapes = list(cell.shapes(index).each())
                if shapes:
                    assert (info.layer, info.datatype) in {(1, 0), (1, 10), (68, 0), (10, 0)}
                if cell.name not in names:
                    assert not shapes or (info.layer, info.datatype) == (10, 0)
    library = pya.Library.library_by_name("JNULib_BlackBox")
    assert library is not None
    assert not list(library.layout().pcell_names())
    for name in names:
        target = pya.Layout()
        instance_cell = target.create_cell(name, "JNULib_BlackBox")
        assert instance_cell is not None and not instance_cell.bbox().empty(), name
    print("PASS: %d bundled blackbox devices load and instantiate; physical geometry is rectangular." % len(names))


if __name__ == "__main__":
    main()
