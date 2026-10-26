# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""另存可跨 GDS 复制的版图，精确匹配后恢复 PCell，否则保留静态缓存。"""

import json
from pathlib import Path
import sys

import pya

PYMACROS = Path(__file__).resolve().parents[2]
if str(PYMACROS) not in sys.path:
    sys.path.insert(0, str(PYMACROS))

from JNU_MWP_tools.core.internal_waveguide_registry import ensure_internal_waveguide_pcells
from JNU_MWP_tools.core.pcell_geometry import cell_geometry_equal, layout_geometry_equal


def _replace(layout, old_index, new_index):
    """重连全部父级实例，不改变变换、阵列或实例属性。"""
    name = layout.cell(old_index).name
    for key, value in layout.cell(old_index).properties().items():
        layout.cell(new_index).set_property(key, value)
    for cell in list(layout.each_cell()):
        if cell.cell_index() == old_index:
            continue
        for instance in list(cell.each_inst()):
            if instance.cell_index == old_index:
                instance.cell_index = new_index
    layout.delete_cell(old_index)
    layout.cell(new_index).name = name


def _static_snapshot(layout):
    """仅解除代理身份，完整保留图形及共享子层级，不展平。"""
    frozen = layout.dup()
    proxies = [(cell.cell_index(), cell.name) for cell in frozen.each_cell() if cell.is_proxy()]
    converted = {index: frozen.convert_cell_to_static(index) for index, _ in proxies}
    for cell in list(frozen.each_cell()):
        if cell.cell_index() in converted:
            continue
        for instance in list(cell.each_inst()):
            if instance.cell_index in converted:
                instance.cell_index = converted[instance.cell_index]
    frozen.delete_cells(list(converted))
    for index, name in proxies:
        frozen.cell(converted[index]).name = name
    if not layout_geometry_equal(layout, frozen):
        raise RuntimeError("解除代理身份后图形或层级发生变化，已停止修复。")
    return frozen


def repair_file(source, output, report_path=None):
    """保留输入；修复文件先写临时路径，经原生重读验收后发布。"""
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or output.exists():
        raise RuntimeError("输出必须是不存在的新文件，禁止覆盖原文件或已有修复版。")
    stamp = source.stat()
    raw = pya.Layout()
    raw.read(str(source))
    frozen = _static_snapshot(raw)
    metadata = []
    for cell in raw.each_cell():
        if cell.is_proxy():
            metadata.append((cell.name, cell.basic_name(), dict(cell.pcell_parameters_by_name())))
    # 完成缓存快照后再加载当前库，避免缺失引用被当前库提前刷新而丢失旧几何。
    if pya.Library.library_by_name("JNULib") is None:
        import JNULib  # noqa: F401

    repaired = frozen.dup()
    ensure_internal_waveguide_pcells(repaired)
    report = {"source": str(source), "output": str(output), "restored": [], "static_fallback": []}
    for name, declaration, params in metadata:
        old = repaired.cell(name)
        candidate = None
        family = None
        if declaration in ("Waveguide", "Composite_Waveguide"):
            family = declaration
            candidate = repaired.create_cell(declaration, params)
        elif {"width1", "width2", "length", "wg_layer", "pin_layer"} <= set(params):
            family = "Pcell_Taper"
            candidate = repaired.create_cell(family, "JNULib", params)
        elif {"width", "length", "wg_layer", "pin_layer"} <= set(params):
            family = "Pcell_Straight_Waveguide"
            candidate = repaired.create_cell(family, "JNULib", params)
        elif not params and pya.Library.library_by_name("JNULib").layout().cell(declaration) is not None:
            family = declaration
            candidate = repaired.create_cell(declaration, "JNULib")
        if candidate is not None and not list(candidate.each_parent_inst()):
            for key, value in old.properties().items():
                candidate.set_property(key, value)
        if (candidate is not None and not list(candidate.each_parent_inst())
                and cell_geometry_equal(old, candidate)):
            _replace(repaired, old.cell_index(), candidate.cell_index())
            report["restored"].append({"cell": name, "declaration": family})
        else:
            if candidate is not None and not list(candidate.each_parent_inst()):
                repaired.delete_cell(candidate.cell_index())
            report["static_fallback"].append({"cell": name, "old_declaration": declaration})
    if not layout_geometry_equal(frozen, repaired):
        raise RuntimeError("修复后的完整图形或层级与原文件不一致，已停止。")
    if any(cell.is_cold_proxy() for cell in repaired.each_cell()):
        raise RuntimeError("修复后仍有失效代理，已停止。")
    options = pya.SaveLayoutOptions()
    options.set_format_from_filename(str(output))
    options.gds2_write_cell_properties = True
    options.gds2_write_file_properties = True
    options.write_context_info = True
    temporary = output.with_name(output.stem + ".验证中.gds")
    if temporary.exists():
        raise RuntimeError("临时验证文件已存在，请先检查此前任务状态。")
    try:
        repaired.write(str(temporary), options)
        reread = pya.Layout()
        ensure_internal_waveguide_pcells(reread)
        reread.read(str(temporary))
        if not layout_geometry_equal(frozen, reread) or any(c.is_cold_proxy() for c in reread.each_cell()):
            raise RuntimeError("保存重读后图形、层级或 PCell 身份验收失败。")
        after = source.stat()
        if (stamp.st_size, stamp.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError("检查期间原文件被其他程序修改，已停止发布。")
        report.update(cells=reread.cells(), restored_count=len(report["restored"]),
                      static_count=len(report["static_fallback"]), geometry_and_hierarchy_equal=True,
                      remaining_cold_proxies=0, source_unchanged=True)
        temporary.rename(output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    if report_path:
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = repair_file(str(input_file), str(output_file), globals().get("report_file"))
    print(json.dumps(result, ensure_ascii=True, indent=2))
