# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

"""验证复制并修改波导 PCell 后，删掉原 cell 不会使副本退化为 Waveguide。"""

from pathlib import Path
import sys
import tempfile

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

from JNU_MWP_tools.core.internal_waveguide_registry import ensure_internal_waveguide_pcells  # noqa: E402


def _write(layout, path):
    options = pya.SaveLayoutOptions()
    options.set_format_from_filename(str(path))
    options.gds2_write_cell_properties = True
    options.write_context_info = True
    layout.write(str(path), options)


def main():
    layout = pya.Layout()
    layout.dbu = 0.001
    ensure_internal_waveguide_pcells(layout)
    declaration = layout.pcell_declaration("Waveguide")
    parameters = list(declaration.get_parameters())
    values = [parameter.default for parameter in parameters]
    overrides = {
        "path": pya.DPath([
            pya.DPoint(0, 0), pya.DPoint(80, 0), pya.DPoint(80, 60),
        ], 0.5),
        "width": 0.5,
        "radius": 20.0,
        "bend_type": "Bezier",
        "bezier_k": 0.35,
    }
    for index, parameter in enumerate(parameters):
        if parameter.name in overrides:
            values[index] = overrides[parameter.name]

    source_index = layout.add_pcell_variant(layout.pcell_id("Waveguide"), values)
    source = layout.cell(source_index)
    source_title = source.display_title()
    assert source.name == source_title and source.name.startswith("Waveguide_w"), source.name

    top = layout.create_cell("COPY_VARIANT_TOP")
    top.insert(pya.CellInstArray(source_index, pya.Trans()))
    copied = top.insert(pya.CellInstArray(source_index, pya.Trans(100000, 0)))
    copied.change_pcell_parameter("path", pya.DPath([
        pya.DPoint(0, 0), pya.DPoint(0, 80), pya.DPoint(-60, 80),
    ], 0.5))
    copied_name = copied.cell.name
    assert copied.cell_index != source_index, "编辑副本没有产生独立 PCell variant"
    assert copied.cell.display_title() == source_title, "同长度路径未形成命名冲突场景"
    assert copied_name == source_title + "__002", copied_name

    layout.delete_cell(source_index)
    remaining = list(top.each_inst())
    assert len(remaining) == 1 and remaining[0].cell.name == copied_name
    layout.refresh()
    assert list(top.each_inst())[0].cell.name == copied_name

    with tempfile.TemporaryDirectory(prefix="jnu_waveguide_copy_") as directory:
        result = Path(directory) / "copy.gds"
        _write(layout, result)
        reread = pya.Layout()
        ensure_internal_waveguide_pcells(reread)
        reread.read(str(result))
        reread_top = reread.cell("COPY_VARIANT_TOP")
        reread_instances = list(reread_top.each_inst())
        assert len(reread_instances) == 1
        assert reread_instances[0].cell.name == copied_name
        assert reread_instances[0].cell.is_pcell_variant()
        ensure_internal_waveguide_pcells(reread, replace=True)
        assert list(reread_top.each_inst())[0].cell.name == copied_name

        # 旧文件可能把已参数化的副本保存为普通 Waveguide 名；读入后恢复名称。
        list(reread_top.each_inst())[0].cell.name = "Waveguide"
        legacy = Path(directory) / "legacy.gds"
        _write(reread, legacy)
        restored = pya.Layout()
        ensure_internal_waveguide_pcells(restored)
        restored.read(str(legacy))
        restored_top = restored.cell("COPY_VARIANT_TOP")
        original_bbox = restored_top.bbox().to_s()
        ensure_internal_waveguide_pcells(restored)
        restored_instances = list(restored_top.each_inst())
        assert len(restored_instances) == 1
        assert restored_instances[0].cell.name == source_title
        assert restored.cell("Waveguide") is None
        assert restored_top.bbox().to_s() == original_bbox

    print("OK: copied Waveguide variant keeps parameterized name after deletion and GDS reload")


if __name__ == "__main__":
    main()
