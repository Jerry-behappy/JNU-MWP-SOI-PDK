# -*- coding: utf-8 -*-
"""在完整 KLayout 环境中检查 GDS/OASIS、PCell 和可选 marker layer。"""

import collections
import hashlib
import json
import os

import pya


def file_hash(path):
    """计算输入文件的 SHA-256。"""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_layer(text):
    """解析 layer/datatype 字符串。"""
    normalized = str(text).strip().replace(",", "/")
    parts = [part.strip() for part in normalized.split("/")]
    if len(parts) != 2:
        raise RuntimeError("marker_layer 必须为 layer/datatype，例如 290/0")
    return pya.LayerInfo(int(parts[0]), int(parts[1]))


def cell_identity(cell):
    """返回适合统计的 cell 或 PCell 身份。"""
    if not cell.is_pcell_variant():
        return cell.name
    library = cell.pcell_library()
    library_name = library.name() if library is not None else "<unresolved>"
    params = cell.pcell_parameters_by_name()
    text_suffix = ""
    if "text" in params:
        text_suffix = ":text=%s" % params["text"]
    return "%s:%s%s" % (library_name, cell.name, text_suffix)


def direct_instance_counts(layout, top):
    """统计顶层直接实例，不把重复实例折叠。"""
    counter = collections.Counter()
    for instance in top.each_inst():
        counter[cell_identity(layout.cell(instance.cell_index))] += 1
    return dict(sorted(counter.items()))


def marker_report(layout, top, layer_info):
    """报告 marker 图形及 bbox 中心命中的直接实例。"""
    layer_index = layout.find_layer(layer_info)
    if layer_index is None or int(layer_index) < 0:
        return {"layer": layer_info.to_s(), "present": False}
    markers = [shape.bbox() for shape in top.shapes(layer_index).each()]
    reports = []
    for marker in markers:
        selected = collections.Counter()
        for instance in top.each_inst():
            cell = layout.cell(instance.cell_index)
            bbox = cell.bbox().transformed(instance.cplx_trans)
            if marker.contains(bbox.center()):
                selected[cell_identity(cell)] += 1
        reports.append({
            "bbox_dbu": marker.to_s(),
            "direct_instance_count": sum(selected.values()),
            "direct_instances": dict(sorted(selected.items())),
        })
    return {
        "layer": layer_info.to_s(),
        "present": True,
        "shape_count": len(markers),
        "markers": reports,
    }


def main():
    """读取版图并输出 JSON 检查报告。"""
    path = os.path.abspath(str(input_file))
    if not os.path.isfile(path):
        raise RuntimeError("输入版图不存在: %s" % path)

    layout = pya.Layout()
    layout.read(path)
    top_cells = list(layout.top_cells())
    layers = sorted(layout.get_info(index).to_s() for index in layout.layer_indices())

    pcell_counter = collections.Counter()
    for cell in layout.each_cell():
        if cell.is_pcell_variant():
            pcell_counter[cell_identity(cell)] += 1

    report = {
        "input_file": path,
        "size_bytes": os.path.getsize(path),
        "sha256": file_hash(path),
        "dbu_um": layout.dbu,
        "cell_count": layout.cells(),
        "top_cells": [
            {
                "name": cell.name,
                "bbox_dbu": cell.bbox().to_s(),
                "direct_instances": direct_instance_counts(layout, cell),
            }
            for cell in top_cells
        ],
        "layers": layers,
        "pcell_variants": dict(sorted(pcell_counter.items())),
    }

    marker_value = globals().get("marker_layer", "")
    if str(marker_value).strip():
        layer_info = parse_layer(marker_value)
        report["marker"] = {
            cell.name: marker_report(layout, cell, layer_info) for cell in top_cells
        }

    # KLayout 批处理 stdout 可能使用 GBK；ASCII 转义可避免 Unicode cell 名写出失败。
    print(json.dumps(report, ensure_ascii=True, indent=2))


main()
