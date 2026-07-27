# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-06

# JNU_MWP_PDK 菜单工具公共函数。
# 集中放置图层常量、GUI 上下文、Pin 扫描和通用 helper。

import os
import math

import pya


SI_LAYER = pya.LayerInfo(1, 0)          # Si 波导实体层。
SIN_LAYER = pya.LayerInfo(4, 0)         # SiN 波导实体层。
EBEAM_SIN_LAYER = pya.LayerInfo(1, 5)   # EBeam SiN 器件层。
RIB_LAYER = pya.LayerInfo(2, 0)         # Rib/浅刻蚀辅助层。
M1_LAYER = pya.LayerInfo(11, 0)         # M1 加热器与器件电极层。
WG_LAYER = pya.LayerInfo(1, 99)         # Waveguide 引导路径层。
PIN_LAYER = pya.LayerInfo(1, 10)        # PinRec 端口识别层。
DEVREC_LAYER = pya.LayerInfo(68, 0)     # DevRec 器件识别层。

RAW_PATH_PROPERTY = "JNU_MWP_raw_manhattan_path"
RAW_PATH_GDS_PROPERTY = 126
RAW_PATH_CELL_SUFFIX = "__JNU_RAW_PATH"
# Path to Waveguide 的内部标记同时写入命名属性和 GDS 数字属性，
# 使 PCell variant 展开为普通 GDS cell 后仍可被可靠识别。
WAVEGUIDE_KIND_PROPERTY = "JNU_MWP_waveguide_kind"
WAVEGUIDE_KIND_GDS_PROPERTY = 127
WAVEGUIDE_CONTAINER_PROPERTY = "JNU_MWP_path_to_waveguide_container"
WAVEGUIDE_CONTAINER_GDS_PROPERTY = 128
WAVEGUIDE_CONTAINER_PREFIX = "__JNU_P2W_"
# Make Pins for Cell 的器件边界兼容 JNU 和 EBeam 的 Verification 语义。
# M1 与 EBeam SiN 计入组件范围，但 M2 路由不属于单器件实体范围。
DEVICE_LAYERS = [SI_LAYER, SIN_LAYER, EBEAM_SIN_LAYER, RIB_LAYER, M1_LAYER]

# Pin 吸附用的最大距离（微米）。
_PIN_SNAP_DISTANCE_UM = 20.0


class _OpticalPin(object):
    """光学端口对象，用于 Path 端点吸附检测。"""
    __slots__ = ("center", "rotation", "width")

    def __init__(self, center, rotation, width):
        self.center = center
        self.rotation = rotation
        self.width = width


def _find_pins_in_cell(cell, layout):
    """递归扫描当前 cell 层级树，提取所有 PinRec 层的 pin 中心坐标和朝向。"""
    pin_layer_index = layout.layer(PIN_LAYER)
    if pin_layer_index is None:
        return []

    pins = []

    iterator = cell.begin_shapes_rec(pin_layer_index)
    while not iterator.at_end():
        shape = iterator.shape()
        if shape.is_path():
            path = shape.path
            if path.width > 0:
                npts = path.num_points() if callable(path.num_points) else path.num_points
                if npts >= 2:
                    pts = list(path.each_point())
                    if len(pts) >= 2:
                        itrans = iterator.itrans()
                        local_mid = pya.Point(
                            (pts[0].x + pts[-1].x) // 2,
                            (pts[0].y + pts[-1].y) // 2,
                        )
                        global_mid = itrans * local_mid
                        delta = itrans * pts[1] - itrans * pts[0]
                        if abs(delta.x) >= abs(delta.y):
                            rotation = 0 if delta.x > 0 else 180
                        else:
                            rotation = 90 if delta.y > 0 else 270
                        pins.append(_OpticalPin(global_mid, rotation, path.width))
        iterator.next()

    return pins


def _pymacros_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _main_window():
    app = pya.Application.instance()
    return app.main_window() if app else None


def _active_context():
    main_window = _main_window()
    if main_window is None:
        raise RuntimeError("当前不是 KLayout GUI 模式。")

    view = main_window.current_view()
    if view is None:
        raise RuntimeError("当前没有打开的版图视图。")

    cellview = view.active_cellview()
    layout = cellview.layout()
    cell = cellview.cell
    if layout is None or cell is None:
        raise RuntimeError("当前没有活动的 layout/cell。")

    return view, layout, cell


def _angle_vector(delta):
    return math.atan2(delta.y, delta.x) / math.pi * 180


def _rotation_vector(rotation, length=1000):
    """把 0/90/180/270 度端口方向转换为整数方向向量。"""
    rotation = int(round(rotation)) % 360
    if rotation == 0:
        return pya.Point(length, 0)
    if rotation == 90:
        return pya.Point(0, length)
    if rotation == 180:
        return pya.Point(-length, 0)
    return pya.Point(0, -length)


def _rotation_from_delta(delta):
    """根据变换后的 pin 路径方向恢复端口朝向。"""
    if abs(delta.x) >= abs(delta.y):
        return 0 if delta.x > 0 else 180
    return 90 if delta.y > 0 else 270


def _message(title, text):
    pya.MessageBox.warning(title, text, pya.MessageBox.Ok)


def _debug_log(text):
    try:
        log_path = os.path.join(os.path.dirname(_pymacros_dir()), "path_to_waveguide_debug.log")
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(str(text) + "\n")
    except Exception:
        pass


def _dedupe_path_points(points):
    clean = []
    for point in points:
        if not clean or clean[-1] != point:
            clean.append(point)
    return clean


def _value(obj, name):
    """兼容读取 KLayout 对象属性或方法。"""
    attr = getattr(obj, name)
    return attr() if callable(attr) else attr


def _is_array_instance(inst):
    """检测 instance 是否为规则阵列；本工具第一版不展开阵列实例。"""
    try:
        return bool(_value(inst, "is_regular_array"))
    except Exception:
        return False


def _raw_path_cell_name(waveguide_cell):
    """根据 waveguide cell 名称生成隐藏 raw path cell 名称。"""
    return "%s%s" % (_value(waveguide_cell, "name"), RAW_PATH_CELL_SUFFIX)


def _set_layer_visibility(view, layer_info, visible):
    """在当前视图的全部 layer list 中设置指定物理图层的可见性。"""
    target_layer = int(_value(layer_info, "layer"))
    target_datatype = int(_value(layer_info, "datatype"))
    changed = 0
    try:
        layer_list_count = int(_value(view, "num_layer_lists"))
    except Exception:
        return changed

    for layer_list_index in range(layer_list_count):
        try:
            iterator = view.begin_layers(layer_list_index)
            while not iterator.at_end():
                properties = iterator.current()
                if (
                    int(properties.source_layer) == target_layer
                    and int(properties.source_datatype) == target_datatype
                ):
                    replacement = properties.dup()
                    replacement.visible = bool(visible)
                    view.set_layer_properties(
                        layer_list_index,
                        iterator,
                        replacement,
                    )
                    changed += 1
                iterator.next()
        except Exception:
            continue
    return changed

__all__ = [
    "SI_LAYER",
    "SIN_LAYER",
    "EBEAM_SIN_LAYER",
    "RIB_LAYER",
    "M1_LAYER",
    "WG_LAYER",
    "PIN_LAYER",
    "DEVREC_LAYER",
    "RAW_PATH_PROPERTY",
    "RAW_PATH_GDS_PROPERTY",
    "RAW_PATH_CELL_SUFFIX",
    "WAVEGUIDE_KIND_PROPERTY",
    "WAVEGUIDE_KIND_GDS_PROPERTY",
    "WAVEGUIDE_CONTAINER_PROPERTY",
    "WAVEGUIDE_CONTAINER_GDS_PROPERTY",
    "WAVEGUIDE_CONTAINER_PREFIX",
    "DEVICE_LAYERS",
    "_PIN_SNAP_DISTANCE_UM",
    "_OpticalPin",
    "_find_pins_in_cell",
    "_pymacros_dir",
    "_main_window",
    "_active_context",
    "_angle_vector",
    "_rotation_vector",
    "_rotation_from_delta",
    "_message",
    "_debug_log",
    "_dedupe_path_points",
    "_value",
    "_is_array_instance",
    "_raw_path_cell_name",
    "_set_layer_visibility",
]
