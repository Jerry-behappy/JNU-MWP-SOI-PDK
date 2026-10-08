# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""把旧版 JNULib PCell 引用迁移为 Pcell_ 名称，保留原始 GDS。"""

import argparse
from collections import Counter
import importlib
import os
from pathlib import Path
import sys
import tempfile

try:
    import pya
except ImportError:
    import klayout.db as pya
    sys.modules["pya"] = pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

import JNULib  # noqa: E402  注册当前公开器件库


LEGACY_PCELL_FACTORIES = {
    "Bend_90deg": JNULib.Bend90deg,
    "Microring_DoubleBus": JNULib.MicroringDoubleBus,
    "Archimedean_Spiral": JNULib.ArchimedeanSpiral,
    "Paperclip_Spiral": JNULib.PaperclipSpiral,
    "Paperclip_Spiral_with_Composite_Waveguide": JNULib.PaperclipSpiralWithCompositeWaveguide,
    "Taper": JNULib.Taper,
    "S_Bend": JNULib.SBendWaveguide,
    "Straight_Waveguide": JNULib.StraightWaveguide,
}


def _legacy_name(cell):
    """仅识别由旧 JNULib 声明写出的失效 PCell。"""
    qualified = cell.qname()
    prefix = "<defunct>JNULib."
    if not qualified.startswith(prefix) or "(...)" not in qualified:
        return None
    return qualified[len(prefix):].split("(", 1)[0]


def _geometry(cell, layout):
    """记录掩膜区域以及必须保留类型、方向的 Path/Text。"""
    if list(cell.each_inst()):
        raise RuntimeError("不迁移含子实例的旧 PCell：%s" % cell.name)
    geometry = {}
    for index in layout.layer_indices():
        shapes = list(cell.shapes(index).each())
        if not shapes:
            continue
        layer = layout.get_info(index).to_s()
        region = pya.Region(cell.begin_shapes_rec(index))
        special = Counter(
            (shape.to_s(), shape.prop_id)
            for shape in shapes
            if shape.is_path() or shape.is_text() or shape.prop_id
        )
        geometry[layer] = (region, special)
    return geometry


def _assert_same_geometry(expected, actual, label):
    """拒绝任何实际区域、端口 Path 或文字发生变化的迁移。"""
    if set(expected) != set(actual):
        raise RuntimeError("%s 的图层集合发生变化。" % label)
    for layer in expected:
        old_region, old_special = expected[layer]
        new_region, new_special = actual[layer]
        if not (old_region ^ new_region).is_empty() or old_special != new_special:
            raise RuntimeError("%s 的 %s 图层几何或端口/文字发生变化。" % (label, layer))


def _register_legacy_declarations(names):
    """只在迁移进程临时注册旧声明，正常器件列表仍只有 Pcell_ 名称。"""
    library = pya.Library.library_by_name("JNULib")
    if library is None:
        raise RuntimeError("当前进程未加载 JNULib。")
    for name in sorted(names):
        factory = LEGACY_PCELL_FACTORIES[name]
        declaration = JNULib.localize_pcell_declaration(factory())
        library.layout().register_pcell(name, declaration)
    library.refresh()


def _migrate(source, output):
    """恢复旧参数，逐实例替换，验证临时 GDS 后发布新文件。"""
    source = Path(source).resolve()
    output = Path(output).resolve()
    if not source.is_file():
        raise RuntimeError("输入 GDS 不存在：%s" % source)
    if source == output or output.exists():
        raise RuntimeError("输出必须是尚不存在的另一份 GDS：%s" % output)
    if not output.parent.is_dir():
        raise RuntimeError("输出目录不存在：%s" % output.parent)

    original = pya.Layout()
    original.read(str(source))
    old_cells = [(cell.name, _legacy_name(cell)) for cell in original.each_cell()]
    old_cells = [(name, old_name) for name, old_name in old_cells if old_name]
    if not old_cells:
        raise RuntimeError("没有发现需要迁移的 JNULib 旧版 PCell。")
    unknown = sorted({old_name for _, old_name in old_cells if old_name not in LEGACY_PCELL_FACTORIES})
    if unknown:
        raise RuntimeError("发现不支持的旧版 PCell，已停止：%s" % ", ".join(unknown))
    baseline = {name: _geometry(original.cell(name), original) for name, _ in old_cells}
    top_names = sorted(cell.name for cell in original.top_cells())

    _register_legacy_declarations({old_name for _, old_name in old_cells})
    layout = pya.Layout()
    layout.read(str(source))
    replacements = {}
    for name, old_name in old_cells:
        old = layout.cell(name)
        if old is None or not old.is_pcell_variant():
            raise RuntimeError("旧 PCell 未能恢复可编辑参数：%s" % name)
        declaration = old.pcell_declaration()
        library = old.pcell_library()
        if declaration.name() != old_name or library is None or library.name() != "JNULib":
            raise RuntimeError("旧 PCell 身份与 GDS 不一致：%s" % name)
        new = layout.create_cell("Pcell_" + old_name, "JNULib", dict(old.pcell_parameters_by_name()))
        if new is None or not new.is_pcell_variant():
            raise RuntimeError("无法创建新版 PCell：%s" % name)
        _assert_same_geometry(baseline[name], _geometry(new, layout), name)
        replacements[old.cell_index()] = new.cell_index()

    placements = 0
    for parent in layout.each_cell():
        for instance in list(parent.each_inst()):
            new_index = replacements.get(instance.cell_index)
            if new_index is None:
                continue
            if parent.is_pcell_variant():
                raise RuntimeError("旧 PCell 嵌套于 PCell 中，无法安全替换：%s" % parent.name)
            instance.cell_index = new_index
            placements += 1
    for old_index in replacements:
        old = layout.cell(old_index)
        if list(old.each_parent_inst()):
            raise RuntimeError("旧 PCell 仍有实例引用：%s" % old.name)
        layout.delete_cell(old_index)
    expected_new_names = {layout.cell(index).name for index in replacements.values()}

    handle, temporary = tempfile.mkstemp(prefix=output.stem + "_tmp_", suffix=".gds", dir=str(output.parent))
    os.close(handle)
    try:
        layout.write(temporary)
        # 清除临时旧名声明，从干净的公开库重读，检验可编辑身份跨保存保留。
        importlib.reload(JNULib)
        check = pya.Layout()
        check.read(temporary)
        if sorted(cell.name for cell in check.top_cells()) != top_names:
            raise RuntimeError("保存重读后顶层 cell 发生变化。")
        defunct = [cell.qname() for cell in check.each_cell() if cell.qname().startswith("<defunct>JNULib.")]
        if defunct:
            raise RuntimeError("保存重读后仍有失效 JNU PCell：%s" % ", ".join(defunct))
        for name in expected_new_names:
            cell = check.cell(name)
            library = cell.pcell_library() if cell is not None and cell.is_pcell_variant() else None
            if library is None or library.name() != "JNULib":
                raise RuntimeError("保存重读后 PCell 身份未恢复：%s" % name)
        if output.exists():
            raise RuntimeError("输出文件在迁移期间已存在：%s" % output)
        os.replace(temporary, str(output))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return len(old_cells), placements


def main():
    parser = argparse.ArgumentParser(description="修复旧版 JNULib PCell 的 GDS 身份，原文件保持不变。")
    parser.add_argument("--input", required=True, help="原始 GDS")
    parser.add_argument("--output", required=True, help="新 GDS，不得与原文件相同")
    args = parser.parse_args()
    count, placements = _migrate(args.input, args.output)
    print("OK: 已迁移 %d 个旧 PCell 定义、%d 个实例；输出：%s" % (count, placements, args.output))


if __name__ == "__main__":
    main()
