# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""验证仓库自带黑盒数据可独立加载，且没有泄露内部物理版图。"""

from pathlib import Path
import sys

import pya


PYMACROS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PYMACROS))
import JNU_MWP_blackbox as blackbox


def verify_port_straights(cell, layout):
    """独立核对四向直段、原连接端面和黑盒主体，拒绝多余的内部 Si。"""
    bodies = list(cell.shapes(layout.layer(998, 0)).each())
    assert len(bodies) == 1 and bodies[0].is_box(), cell.name
    body = bodies[0].box
    assert not body.empty(), cell.name
    si = list(cell.shapes(layout.layer(1, 0)).each())
    paths = [s.path for s in cell.shapes(layout.layer(1, 10)).each() if s.is_path()]
    assert len(si) == len(paths) > 0 and all(s.is_box() for s in si), cell.name
    remaining = [s.box for s in si]
    for path in paths:
        a, b = list(path.each_point())
        x, y = (a.x + b.x) // 2, (a.y + b.y) // 2
        dx, dy = b.x - a.x, b.y - a.y
        half = path.width // 2
        other_half = path.width - half
        if dx > 0:
            match = next((s for s in remaining if s.right == x and s.bottom == y - half
                          and s.top == y + other_half and s.left == body.right), None)
        elif dx < 0:
            match = next((s for s in remaining if s.left == x and s.bottom == y - half
                          and s.top == y + other_half and s.right == body.left), None)
        elif dy > 0:
            match = next((s for s in remaining if s.top == y and s.left == x - half
                          and s.right == x + other_half and s.bottom == body.top), None)
        else:
            match = next((s for s in remaining if s.bottom == y and s.left == x - half
                          and s.right == x + other_half and s.top == body.bottom), None)
        assert match is not None, (cell.name, str(path))
        length = match.width() if dx else match.height()
        assert abs(length * layout.dbu - 0.2) < 1e-9, cell.name
        assert (pya.Region(match) & pya.Region(body)).is_empty(), cell.name
        remaining.remove(match)
    assert not remaining, cell.name


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
            verify_port_straights(cell, layout)
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
                    assert (info.layer, info.datatype) in {(1, 0), (1, 10), (68, 0), (10, 0), (998, 0)}
                if cell.name not in names:
                    assert not shapes or (info.layer, info.datatype) == (10, 0)
    assert len(names) == 31, "黑盒器件数应为 31 个：%d" % len(names)
    assert {
        "1550_crossing4", "1310_TE_Terminator", "1550_TE_Terminator",
        "1310_Ybranch", "1550_Ybranch",
    } <= names
    assert not any(name.startswith("Pcell_") for name in names)
    assert not {"ebeam_crossing4", "ebeam_terminator_te1310", "ebeam_terminator_te1550",
                "ebeam_y_1310", "ebeam_y_1550"} & names
    library = pya.Library.library_by_name("JNULib_BlackBox")
    assert library is not None
    assert not list(library.layout().pcell_names())
    for name in names:
        target = pya.Layout()
        instance_cell = target.create_cell(name, "JNULib_BlackBox")
        assert instance_cell is not None and not instance_cell.bbox().empty(), name
    print("PASS: %d blackboxes load and instantiate; Si contains only 0.2 um port straights touching the BlackBox body." % len(names))


if __name__ == "__main__":
    main()
