# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

# JNU_MWP_PDK Make Pins for Cell 功能。
# 从选中的 cell instance 器件边界生成 DevRec 与 PinRec。

import pya


# GUI 中的端口方向按用户在版图视图中的全局方向选择；生成前需要把该方向
# 反映射到实例所属 cell 的本地坐标，否则旋转后的实例会把 T 生成到右侧。
_PORT_VECTORS = {
    "L": (-1, 0),
    "R": (1, 0),
    "T": (0, 1),
    "B": (0, -1),
}

from JNU_MWP_tools.core.common import (
    DEVICE_LAYERS,
    DEVREC_LAYER,
    PIN_LAYER,
    _active_context,
    _main_window,
    _message,
)
from JNU_MWP_tools.core.gui_state import exec_dialog_with_persisted_size


# DevRec 在无端口的边外扩 0.5 µm，使器件识别范围与 SiEPIC 的
# create_device_DevRec 规则一致，同时保留端口边与物理器件边界对齐。
DEVREC_NON_PORT_OFFSET_UM = 0.5


def _show_make_pins_dialog():
    dialog = pya.QDialog(_main_window())
    dialog.setWindowTitle("JNU Make Pins for Cell")

    layout = pya.QVBoxLayout(dialog)
    dialog.setLayout(layout)

    info = pya.QLabel("选择需要在当前 cell 边界上生成 pin 的方向。", dialog)
    layout.addWidget(info)

    boxes = []
    for label, checked in (("L", True), ("R", True), ("T", False), ("B", False)):
        box = pya.QCheckBox(label, dialog)
        box.setChecked(checked)
        layout.addWidget(box)
        boxes.append((label, box))

    buttons = pya.QHBoxLayout(dialog)
    cancel = pya.QPushButton("Cancel", dialog)
    ok = pya.QPushButton("OK", dialog)
    cancel.clicked(lambda _checked: dialog.reject())
    ok.clicked(lambda _checked: dialog.accept())
    buttons.addWidget(cancel)
    buttons.addWidget(ok)
    layout.addLayout(buttons)

    if exec_dialog_with_persisted_size(dialog, "make_pins_for_cell") == 0:
        return None

    ports = [label for label, box in boxes if box.isChecked()]
    if not ports:
        _message("JNU_MWP_PDK", "至少需要选择一个端口方向。")
        return None
    return ports


def _layer_bbox_rec(cell, layer_index):
    bbox = pya.Box()
    iterator = cell.begin_shapes_rec(layer_index)
    while not iterator.at_end():
        bbox += iterator.shape().bbox().transformed(iterator.itrans())
        iterator.next()
    return bbox


def _device_layers(layout):
    return [layout.layer(layer_info) for layer_info in DEVICE_LAYERS]


def _device_region(cell, layer_indices):
    region = pya.Region()
    if not layer_indices:
        return region
    iterator = pya.RecursiveShapeIterator(cell.layout(), cell, layer_indices)
    while not iterator.at_end():
        region += pya.Region(iterator)
        iterator.next()
    return region.merged()


def _device_bbox(cell, layer_indices):
    bbox = pya.Box()
    for layer_index in layer_indices:
        bbox += _layer_bbox_rec(cell, layer_index)
    return bbox


def _expanded_devrec_bbox(device_bbox, ports, dbu):
    """按端口边保持对齐、非端口边外扩的规则计算矩形 DevRec。"""

    offset = max(1, int(round(DEVREC_NON_PORT_OFFSET_UM / dbu)))
    bbox = pya.Box(
        device_bbox.left,
        device_bbox.bottom,
        device_bbox.right,
        device_bbox.top,
    )
    if "T" not in ports:
        bbox.top += offset
    if "B" not in ports:
        bbox.bottom -= offset
    if "L" not in ports:
        bbox.left -= offset
    if "R" not in ports:
        bbox.right += offset
    return bbox


def _needs_expansion(existing_bbox, expected_bbox):
    """判断现有 DevRec 是否小于本次按端口规则应得到的边界。"""

    return (
        existing_bbox.left > expected_bbox.left
        or existing_bbox.right < expected_bbox.right
        or existing_bbox.bottom > expected_bbox.bottom
        or existing_bbox.top < expected_bbox.top
    )


def _existing_or_device_devrec(cell, device_bbox, ports):
    layout = cell.layout()
    devrec_layer = layout.layer(DEVREC_LAYER)
    devrec_bbox = _layer_bbox_rec(cell, devrec_layer)
    expected_bbox = _expanded_devrec_bbox(device_bbox, ports, layout.dbu)
    if devrec_bbox.empty():
        devrec_bbox = expected_bbox
        cell.shapes(devrec_layer).insert(devrec_bbox)
        return devrec_bbox

    # 旧版 JNU 工具只写入一个与器件 bbox 相同的直接 Box。遇到该类无标签
    # DevRec 时安全升级为带非端口净空的矩形；含文字或其他图形的自定义 DevRec
    # 不会被覆盖。
    local_shapes = list(cell.shapes(devrec_layer).each())
    if (
        len(local_shapes) == 1
        and local_shapes[0].is_box()
        and _needs_expansion(local_shapes[0].box, expected_bbox)
    ):
        cell.shapes(devrec_layer).clear()
        cell.shapes(devrec_layer).insert(expected_bbox)
        return expected_bbox
    return devrec_bbox


def _instance_local_ports(ports, instance_transform):
    """把全局端口方向映射为实例所属 cell 的本地端口方向。"""

    if instance_transform is None:
        return list(ports)

    local_ports = []
    for global_side in ports:
        global_vector = _PORT_VECTORS[global_side]

        def score(local_side):
            local_vector = _PORT_VECTORS[local_side]
            transformed = instance_transform * pya.Vector(local_vector[0], local_vector[1])
            return transformed.x * global_vector[0] + transformed.y * global_vector[1]

        local_ports.append(max(_PORT_VECTORS, key=score))
    return local_ports


def make_pins_for_cell_impl(cell, ports=None, instance_transform=None):
    from JNU_MWP_tools.core.make_pin import make_pin

    ports = ports or ["L", "R"]
    ports = _instance_local_ports(ports, instance_transform)
    layout = cell.layout()
    device_layers = _device_layers(layout)
    region = _device_region(cell, device_layers)
    device_bbox = _device_bbox(cell, device_layers)
    if region.is_empty() or device_bbox.empty():
        return 0

    pin_layer = layout.layer(PIN_LAYER)
    _existing_or_device_devrec(cell, device_bbox, ports)

    def make_from_bbox(bbox):
        pin_count = 0
        edge_specs = [
            ("L", pya.Edge(bbox.left, bbox.top, bbox.left, bbox.bottom), 180),
            ("R", pya.Edge(bbox.right, bbox.top, bbox.right, bbox.bottom), 0),
            ("T", pya.Edge(bbox.left, bbox.top, bbox.right, bbox.top), 90),
            ("B", pya.Edge(bbox.left, bbox.bottom, bbox.right, bbox.bottom), 270),
        ]
        for side, edge, direction in edge_specs:
            if side not in ports:
                continue
            port_edges = pya.Edges(edge) & region
            if side in ("L", "R"):
                port_edges = sorted(port_edges, key=lambda item: -item.y1)
            else:
                port_edges = sorted(port_edges, key=lambda item: item.x1)
            for port_edge in port_edges:
                w = abs(port_edge.y1 - port_edge.y2) if side in ("L", "R") else abs(port_edge.x1 - port_edge.x2)
                if w <= 0:
                    continue
                pin_count += 1
                if side in ("L", "R"):
                    center = [port_edge.x1, int(round((port_edge.y1 + port_edge.y2) / 2))]
                else:
                    center = [int(round((port_edge.x1 + port_edge.x2) / 2)), port_edge.y1]
                make_pin(cell, "opt%d" % pin_count, center, w, pin_layer, direction)
        return pin_count

    # DevRec 只用于器件识别，已有框的偏移或净空不得改变实体端面上的端口。
    return make_from_bbox(device_bbox)


def make_pins_for_cell():
    """为选中的 Cell Instance 生成器件识别边界和带方向的光学端口标记。"""
    try:
        view, layout, _ = _active_context()

        selected_instances = []
        for obj in view.object_selection:
            if obj.is_cell_inst():
                selected_instances.append(obj)

        if not selected_instances:
            _message("JNU_MWP_PDK", "请先选中一个 Cell Instance，再执行 Make Pins for Cell。")
            return

        if len(selected_instances) > 1:
            _message("JNU_MWP_PDK", "请只选中一个 Cell Instance。")
            return

        obj = selected_instances[0]
        inst = obj.inst()
        target_cell = inst.cell
        if target_cell is None:
            _message("JNU_MWP_PDK", "选中的 instance 没有对应的 cell。")
            return

        ports = _show_make_pins_dialog()
        if ports is None:
            return

        view.transaction("JNU Make Pins for Cell")
        count = make_pins_for_cell_impl(
            target_cell,
            ports=ports,
            instance_transform=inst.trans,
        )
        view.commit()
        _main_window().redraw()
        if count == 0:
            _message("JNU_MWP_PDK", "没有找到可用于生成 pin 的器件层边界。")
        else:
            _message("JNU_MWP_PDK", "已在 cell '%s' 中生成 %d 个 PinRec pin。" % (target_cell.name, count))
    except Exception as error:
        try:
            view.commit()
        except Exception:
            pass
        _message("JNU_MWP_PDK", "Make Pins for Cell 失败：\n%s" % error)

__all__ = [
    "DEVREC_NON_PORT_OFFSET_UM",
    "_expanded_devrec_bbox",
    "_instance_local_ports",
    "make_pins_for_cell",
    "make_pins_for_cell_impl",
]
