# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""选中待移动实例组，并吸附到鼠标悬停参考实例的最近相向 PinRec 端口。"""

import pya

from JNU_MWP_tools.core.common import (
    _OpticalPin,
    _active_context,
    _find_pins_in_cell,
    _is_array_instance,
    _main_window,
    _message,
    _rotation_from_delta,
    _rotation_vector,
    _value,
)


TOOL_TITLE = "JNU_MWP_PDK"
LEGACY_STATE_ATTR = "_jnu_snap_selected_components_state"


class _InstanceRecord(object):
    """记录一个被选中对象及其已变换到当前 active cell 坐标系的端口。"""

    __slots__ = ("obj", "inst", "key", "label", "pins", "is_instance")

    def __init__(self, obj, inst, key, label, pins, is_instance=True):
        self.obj = obj
        self.inst = inst
        self.key = key
        self.label = label
        self.pins = pins
        self.is_instance = bool(is_instance)


class _PinRecord(object):
    """把端口与所属实例绑定，便于最近距离排序和结果提示。"""

    __slots__ = ("instance", "center", "rotation", "width")

    def __init__(self, instance, pin):
        self.instance = instance
        self.center = pin.center
        self.rotation = pin.rotation
        self.width = pin.width


class _SnapPair(object):
    """保存最终用于吸附的一对相向端口。"""

    __slots__ = ("fixed_pin", "moving_pin", "distance_sq")

    def __init__(self, fixed_pin, moving_pin, distance_sq):
        self.fixed_pin = fixed_pin
        self.moving_pin = moving_pin
        self.distance_sq = distance_sq


def _point_to_int(point):
    """将 KLayout 浮点或整数点统一为 DBU 整数坐标。"""
    return pya.Point(int(round(point.x)), int(round(point.y)))


def _transform_pin(pin, trans):
    """把子 cell 内端口变换到当前 active cell 坐标系。"""
    center = _point_to_int(trans * pin.center)
    direction_tip = _point_to_int(trans * (pin.center + _rotation_vector(pin.rotation)))
    delta = direction_tip - center
    if delta.x == 0 and delta.y == 0:
        rotation = pin.rotation
    else:
        rotation = _rotation_from_delta(delta)
    return _OpticalPin(center, rotation, pin.width)


def _pins_for_instance(inst, trans, layout):
    """读取实例内部 PinRec，并转换到当前 active cell 坐标。"""
    if inst is None or inst.cell is None:
        return []
    return [_transform_pin(pin, trans) for pin in _find_pins_in_cell(inst.cell, layout)]


def _selected_objects(view):
    """返回当前选择中的全部对象；端口识别阶段再区分实例和 primitive。"""
    return list(view.object_selection)


def _transient_object(view):
    """返回鼠标悬停命中的第一个 transient object。"""
    try:
        has_transient = bool(view.has_transient_object_selection())
    except Exception:
        has_transient = False
    if not has_transient:
        raise RuntimeError(
            "未检测到鼠标悬停参考对象。\n"
            "请把鼠标放在不需要移动且含有 PinRec 端口的目标对象上，再执行 Snap components。"
        )

    try:
        iterator = view.each_object_selected_transient()
    except Exception:
        raise RuntimeError("当前 KLayout 视图无法读取 transient selection。")

    first = None
    for obj in iterator:
        first = obj
        break
    if first is None:
        raise RuntimeError("transient selection 为空，请重新把鼠标放在参考对象上。")
    return first


def _instance_transform(obj):
    """读取 ObjectInstPath 的完整变换，失败时退回实例自身变换。"""
    inst = obj.inst()
    try:
        return _value(obj, "trans")
    except Exception:
        return _value(inst, "trans")


def _instance_key(obj):
    """用 cell、变换和 bbox 生成一次会话内稳定的实例标识。"""
    inst = obj.inst()
    trans = _instance_transform(obj)
    try:
        bbox = inst.bbox()
    except Exception:
        bbox = None
    bbox_text = str(bbox) if bbox is not None else ""
    return "%s|%s|%s" % (int(_value(inst, "cell_index")), str(trans), bbox_text)


def _instance_label(inst, index):
    """生成面向用户提示的实例标签。"""
    try:
        name = _value(inst.cell, "name")
    except Exception:
        name = "Cell"
    return "%s#%d" % (name, index + 1)


def _object_shape(obj):
    """兼容读取被选中 primitive 的 shape 对象。"""
    try:
        return _value(obj, "shape")
    except Exception:
        return None


def _object_layer_index(obj):
    """兼容读取被选中 primitive 所在的 layout layer index。"""
    for name in ("layer", "layer_index"):
        try:
            value = _value(obj, name)
            if value is not None:
                return int(value)
        except Exception:
            continue
    return None


def _object_transform(obj):
    """读取被选对象到当前 active cell 的变换；失败时使用单位变换。"""
    try:
        return _value(obj, "trans")
    except Exception:
        return pya.Trans.R0


def _path_pin(path, trans):
    """从 PinRec path 的点序恢复中心、方向和宽度。"""
    if path is None or path.width <= 0:
        return None
    npts = path.num_points() if callable(path.num_points) else path.num_points
    if npts < 2:
        return None
    pts = list(path.each_point())
    if len(pts) < 2:
        return None

    center = _point_to_int(
        trans
        * pya.Point(
            (pts[0].x + pts[-1].x) // 2,
            (pts[0].y + pts[-1].y) // 2,
        )
    )
    start = _point_to_int(trans * pts[0])
    next_point = _point_to_int(trans * pts[1])
    delta = next_point - start
    if delta.x == 0 and delta.y == 0:
        return None
    return _OpticalPin(center, _rotation_from_delta(delta), path.width)


def _primitive_pins_for_object(obj, layout):
    """如果选中 primitive 是 PinRec path，则提取为端口；其它 primitive 不产生端口。"""
    layer_index = _object_layer_index(obj)
    if layer_index is None or layer_index != layout.layer(pya.LayerInfo(1, 10)):
        return []
    shape = _object_shape(obj)
    if shape is None or not shape.is_path():
        return []
    pin = _path_pin(shape.path, _object_transform(obj))
    return [pin] if pin is not None else []


def _primitive_label(obj, index):
    layer_index = _object_layer_index(obj)
    return "Primitive[%s]#%d" % ("?" if layer_index is None else str(layer_index), index + 1)


def _build_instance_record(obj, inst, trans, layout, key=None, label=None):
    """构造实例记录；测试可直接传入 inst/trans，GUI 入口传入 obj。"""
    pins = _pins_for_instance(inst, trans, layout)
    if key is None:
        key = _instance_key(obj) if obj is not None else "%s|%s" % (int(_value(inst, "cell_index")), str(trans))
    if label is None:
        try:
            label = _value(inst.cell, "name")
        except Exception:
            label = "Cell"
    return _InstanceRecord(obj, inst, key, label, [_PinRecord(None, pin) for pin in pins], is_instance=True)


def _primitive_key(obj, index):
    shape = _object_shape(obj)
    bbox_text = ""
    if shape is not None:
        try:
            bbox_text = str(shape.bbox())
        except Exception:
            bbox_text = ""
    return "primitive|%s|%s|%s" % (_object_layer_index(obj), str(_object_transform(obj)), bbox_text)


def _build_primitive_record(obj, layout, index):
    """构造 primitive 记录；PinRec path 产生端口，其它 primitive 只作为移动对象。"""
    pins = _primitive_pins_for_object(obj, layout)
    label = _primitive_label(obj, index)
    return _InstanceRecord(
        obj,
        None,
        _primitive_key(obj, index),
        label,
        [_PinRecord(None, pin) for pin in pins],
        is_instance=False,
    )


def _records_from_objects(objects, layout, role):
    """从任意选中对象生成移动记录；只要求整组至少含有一个 PinRec 端口。"""
    records = []

    for index, obj in enumerate(objects):
        if obj.is_cell_inst():
            inst = obj.inst()
            if inst is None or inst.cell is None:
                record = _build_primitive_record(obj, layout, index)
            else:
                if _is_array_instance(inst):
                    raise RuntimeError("Snap components 暂不展开 array instance，请先解除阵列。")
                record = _build_instance_record(
                    obj,
                    inst,
                    _instance_transform(obj),
                    layout,
                    key=_instance_key(obj),
                    label=_instance_label(inst, index),
                )
        else:
            record = _build_primitive_record(obj, layout, index)
        for pin in record.pins:
            pin.instance = record
        records.append(record)

    if not _all_pins(records):
        raise RuntimeError("%s中未找到 PinRec 光学端口。" % role)
    return records


def _all_pins(records):
    pins = []
    for record in records:
        for pin in record.pins:
            if pin.instance is None:
                pin.instance = record
            pins.append(pin)
    return pins


def _pin_distance_sq(left, right):
    dx = left.center.x - right.center.x
    dy = left.center.y - right.center.y
    return dx * dx + dy * dy


def _is_opposite_rotation(left, right):
    """端口点序方向相差 180° 时才允许吸附。"""
    return int(round(left.rotation - right.rotation)) % 360 == 180


def choose_snap_pin_pair(fixed_records, moving_records):
    """在固定参考实例和移动组的所有端口中选择最近的相向端口对。"""
    best = None
    for fixed_pin in _all_pins(fixed_records):
        for moving_pin in _all_pins(moving_records):
            if not _is_opposite_rotation(fixed_pin, moving_pin):
                continue
            distance = _pin_distance_sq(fixed_pin, moving_pin)
            if best is None or distance < best.distance_sq:
                best = _SnapPair(fixed_pin, moving_pin, distance)
    return best


def snap_translation(pair):
    """返回把 moving_pin 平移到 fixed_pin 所需的整数 DBU 位移。"""
    return pair.fixed_pin.center - pair.moving_pin.center


def _clear_legacy_state(main_window):
    """清除旧两次框选模式遗留的临时状态。"""
    if main_window is None or not hasattr(main_window, LEGACY_STATE_ATTR):
        return
    try:
        delattr(main_window, LEGACY_STATE_ATTR)
    except Exception:
        setattr(main_window, LEGACY_STATE_ATTR, None)


def _move_records(records, translation):
    """把移动组的所有选中对象做同一个平移，保持组内相对位置。"""
    trans = pya.Trans(pya.Trans.R0, translation.x, translation.y)
    moved = 0
    for record in records:
        if record.is_instance and record.inst is not None:
            record.inst.transform(trans)
            moved += 1
            continue
        shape = _object_shape(record.obj)
        if shape is not None:
            shape.transform(trans)
            moved += 1
    return moved


def _moving_records_from_selection(view, layout):
    objects = _selected_objects(view)
    if not objects:
        raise RuntimeError("请先单击或框选至少一个含有 PinRec 端口的对象。")
    return _records_from_objects(objects, layout, "移动组")


def _fixed_record_from_transient(view, layout):
    transient_obj = _transient_object(view)
    records = _records_from_objects([transient_obj], layout, "鼠标悬停参考对象")
    return records[0]


def perform_snap(layout, moving_records, fixed_records):
    """纯逻辑入口：返回端口对、平移量和移动数量。"""
    moving_keys = set(record.key for record in moving_records)
    fixed_keys = set(record.key for record in fixed_records)
    if moving_keys.intersection(fixed_keys):
        raise RuntimeError("移动组中包含鼠标悬停的参考对象；请让参考对象保持未选中。")

    pair = choose_snap_pin_pair(fixed_records, moving_records)
    if pair is None:
        raise RuntimeError("移动组与参考对象之间没有方向相差 180° 的 PinRec 光学端口。")

    translation = snap_translation(pair)
    if translation.x == 0 and translation.y == 0:
        return pair, translation, 0

    moved = _move_records(moving_records, translation)
    return pair, translation, moved


def _perform_snap_in_view(view, layout, moving_records, fixed_records):
    """GUI 入口：在一个 Undo transaction 中移动选中实例组。"""
    moving_keys = set(record.key for record in moving_records)
    fixed_keys = set(record.key for record in fixed_records)
    if moving_keys.intersection(fixed_keys):
        raise RuntimeError("移动组中包含鼠标悬停的参考对象；请让参考对象保持未选中。")

    pair = choose_snap_pin_pair(fixed_records, moving_records)
    if pair is None:
        raise RuntimeError("移动组与参考对象之间没有方向相差 180° 的 PinRec 光学端口。")

    translation = snap_translation(pair)
    if translation.x == 0 and translation.y == 0:
        return pair, translation, 0

    view.transaction("JNU Snap components")
    try:
        moved = _move_records(moving_records, translation)
        view.commit()
    except Exception:
        try:
            view.cancel()
        except Exception:
            pass
        raise
    return pair, translation, moved


def snap_components():
    """JNU_MWP_PDK 菜单入口：把选中移动组吸附到鼠标悬停参考对象。"""
    main_window = _main_window()
    _clear_legacy_state(main_window)
    try:
        view, layout, cell = _active_context()
        moving_records = _moving_records_from_selection(view, layout)
        fixed_record = _fixed_record_from_transient(view, layout)

        pair, translation, moved = _perform_snap_in_view(view, layout, moving_records, [fixed_record])

        if moved == 0:
            return

        try:
            main_window.redraw()
        except Exception:
            pass
    except Exception as error:
        _message(TOOL_TITLE, "Snap components 失败：\n%s" % error)


__all__ = [
    "snap_components",
    "perform_snap",
    "choose_snap_pin_pair",
    "snap_translation",
    "_build_instance_record",
    "_move_records",
    "_pins_for_instance",
]
