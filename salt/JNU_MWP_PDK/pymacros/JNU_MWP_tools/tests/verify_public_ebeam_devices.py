# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""隔离 KLayout 中核对独立白盒库的 EBeam GDS 和 JNU bump PCell。"""

from pathlib import Path
import math
import os
import sys
import tempfile

import pya


PYMACROS = Path(__file__).resolve().parents[2]
SOURCE_GDS = Path(os.environ.get("JNU_WHITEBOX_GDS_DIR", PYMACROS / "JNU_MWP_gds"))
sys.path.insert(0, str(PYMACROS))
import JNULib  # noqa: F401


FIXED = (
    ("ebeam_crossing4", "Crossing4", 7, 4),
    ("ebeam_terminator_te1310", "1310_TE_Terminator", 3, 1),
    ("ebeam_terminator_te1550", "1550_TE_Terminator", 4, 1),
    ("ebeam_y_1310", "1310_Ybranch", 6, 3),
    ("ebeam_y_1550", "1550_Ybranch", 6, 3),
)


def _shape_texts(cell, layout, layer_info):
    layer = layout.layer(layer_info)
    return sorted(
        (shape.text.string, str(shape.text.trans), shape.text.size,
         str(shape.text.bbox()))
        for shape in cell.shapes(layer).each() if shape.is_text()
    )


def _pins(cell, layout):
    layer = layout.layer(1, 10)
    return sorted(
        (tuple((point.x, point.y) for point in shape.path.each_point()),
         shape.path.width, shape.path.bgn_ext, shape.path.end_ext)
        for shape in cell.shapes(layer).each() if shape.is_path()
    )


def _region(cell, layout, info):
    return pya.Region(cell.shapes(layout.layer(info)))


def _port_signature(cell, layout):
    ports = []
    for points, width, _, _ in _pins(cell, layout):
        a, b = points[0], points[-1]
        ports.append((round((a[0] + b[0]) * layout.dbu / 2, 3),
                      round((a[1] + b[1]) * layout.dbu / 2, 3),
                      round(width * layout.dbu, 3),
                      (1 if b[0] > a[0] else -1 if b[0] < a[0] else 0,
                       1 if b[1] > a[1] else -1 if b[1] < a[1] else 0)))
    return sorted(ports)


def verify_fixed(library):
    for source_name, name, text_count, port_count in FIXED:
        assert library.layout().cell(source_name) is None, source_name
        source = pya.Layout()
        source.read(str(SOURCE_GDS / (source_name + ".gds")))
        original = source.cell(source_name)
        copied = library.layout().cell(name)
        assert original is not None and copied is not None, name
        assert abs(source.dbu - library.layout().dbu) < 1e-12, name
        assert original.bbox() == copied.bbox(), name
        for info in (pya.LayerInfo(1, 0), pya.LayerInfo(68, 0)):
            assert (_region(original, source, info) ^
                    _region(copied, library.layout(), info)).is_empty(), name
        assert _pins(original, source) == _pins(copied, library.layout()), name
        assert len(_pins(copied, library.layout())) == port_count, name
        all_original_text = []
        all_copied_text = []
        for info in (pya.LayerInfo(1, 10), pya.LayerInfo(10, 0), pya.LayerInfo(68, 0)):
            all_original_text.extend(_shape_texts(original, source, info))
            all_copied_text.extend(_shape_texts(copied, library.layout(), info))
        assert sorted(all_original_text) == sorted(all_copied_text), name
        assert len(all_copied_text) == text_count, name


def verify_bump(library):
    for delta in (0.2, 1.0):
        layout = pya.Layout()
        layout.dbu = 0.001
        cell = layout.create_cell("Pcell_Waveguide_Bump", "JNULib", {
            "delta_length": delta, "width": 0.5, "radius": 20.0, "max_theta": 149.0,
        })
        assert cell is not None and cell.is_pcell_variant(), delta
        assert len(_pins(cell, layout)) == 2, delta
        from JNU_MWP_pcells.waveguide_bump import bump_dimensions
        _, arc_length_x, _ = bump_dimensions(delta, 20.0, 149.0)
        from JNU_MWP_pcells.waveguide_bump import bump_centerline
        points, _, _ = bump_centerline(delta, 20.0, 149.0, layout.dbu)
        physical_length = sum(math.hypot(b.x - a.x, b.y - a.y) * layout.dbu
                              for a, b in zip(points, points[1:]))
        assert abs(physical_length - (points[-1].x - points[0].x) * layout.dbu - delta) < 0.01
        assert abs(cell.bbox(layout.layer(1, 0)).width() * layout.dbu - arc_length_x - 0.04) < 0.01, delta
        assert not _region(cell, layout, pya.LayerInfo(1, 0)).is_empty(), delta
        assert not _region(cell, layout, pya.LayerInfo(68, 0)).is_empty(), delta
        assert any("dL = " in value[0] for value in _shape_texts(
            cell, layout, pya.LayerInfo(10, 0))), delta
        top = layout.create_cell("TOP")
        top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans()))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bump.gds"
            layout.write(str(path))
            reopened = pya.Layout()
            reopened.read(str(path))
            variant = next(reopened.cell(child.cell_index) for child in
                           reopened.cell("TOP").each_inst())
            assert variant is not None and variant.is_pcell_variant(), delta
            assert abs(float(variant.pcell_parameters_by_name()["delta_length"]) - delta) < 1e-6


def verify_blackbox_ports(library):
    names = [name for _, name, _, _ in FIXED] + ["Pcell_Waveguide_Bump"]
    for name in names:
        layout = pya.Layout()
        layout.read(str(PYMACROS / "JNU_MWP_blackbox_gds" / (name + ".gds")))
        blackbox = layout.cell(name)
        assert blackbox is not None, name
        if name == "Pcell_Waveguide_Bump":
            source_layout = pya.Layout()
            original = source_layout.create_cell(name, "JNULib", {
                "delta_length": 0.2, "width": 0.5, "radius": 20.0, "max_theta": 149.0,
            })
        else:
            source_layout = library.layout()
            original = source_layout.cell(name)
        assert _port_signature(original, source_layout) == _port_signature(blackbox, layout), name
        assert not _shape_texts(blackbox, layout, pya.LayerInfo(68, 0)), name


def main():
    library = pya.Library.library_by_name("JNULib")
    assert library is not None
    verify_fixed(library)
    verify_bump(library)
    verify_blackbox_ports(library)
    print("PASS: five source GDS cells match JNULib; bump PCell survives GDS reopen; six blackboxes preserve ports.")


if __name__ == "__main__":
    main()
