# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-06

# JNU_MWP_PDK SBend connect 功能。
# 在两个选中的 cell instance 之间自动查找水平相向 pin，并插入可编辑 S_Bend PCell。

import os
import sys

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

JNULIB_NAME = "JNULib"
BLACKBOX_LIBRARY_NAME = "JNULib_BlackBox"
DEFAULT_SBEND_CONNECT_BEZIER = 0.3
DEFAULT_SBEND_CONNECT_RADIUS = 30.0


def _point_to_int(point):
    """把可能的 DPoint/Point 统一成整数数据库坐标。"""
    return pya.Point(int(round(point.x)), int(round(point.y)))


def _transform_pin(pin, trans):
    """把子 cell 坐标中的 pin 变换到当前父 cell 坐标。"""
    center = _point_to_int(trans * pin.center)
    direction_tip = _point_to_int(trans * (pin.center + _rotation_vector(pin.rotation)))
    delta = direction_tip - center
    if delta.x == 0 and delta.y == 0:
        rotation = pin.rotation
    else:
        rotation = _rotation_from_delta(delta)
    return _OpticalPin(center, rotation, pin.width)


def _pins_for_instance(inst, trans, layout):
    """读取一个 instance 内部的 PinRec，并转换到当前父 cell 坐标。"""
    if inst is None or inst.cell is None:
        return []
    return [_transform_pin(pin, trans) for pin in _find_pins_in_cell(inst.cell, layout)]


def _selected_cell_instance_objects(view):
    """返回当前 GUI 选中的 cell instance 对象。"""
    selected = []
    for obj in view.object_selection:
        if obj.is_cell_inst():
            selected.append(obj)
    return selected


def _instance_transform(obj):
    """读取 ObjectInstPath 到当前 cell 的完整变换，失败时退回 instance 自身变换。"""
    inst = obj.inst()
    try:
        return _value(obj, "trans")
    except Exception:
        return _value(inst, "trans")


def _pin_distance_sq(left, right):
    """计算两个 pin 中心点距离平方，用于选择最近的一对端口。"""
    dx = left.center.x - right.center.x
    dy = left.center.y - right.center.y
    return dx * dx + dy * dy


def _choose_sbend_pin_pair(pins_a, pins_b):
    """选择最近的相向 pin pair，同时支持水平和垂直方向。

    返回 (start_pin, end_pin, is_vertical)，其中：
    - 水平方向：start_pin 朝右(0°)，end_pin 朝左(180°)。
    - 垂直方向：start_pin 朝下(270°)，end_pin 朝上(90°)。

    若无合适 pair，返回 None。
    """
    best = None
    best_distance = None

    for pin_a in pins_a:
        for pin_b in pins_b:
            # ---------- 水平方向：0° ↔ 180° ----------
            h_candidates = []
            if pin_a.rotation == 0 and pin_b.rotation == 180:
                h_candidates.append((pin_a, pin_b, False))
            if pin_b.rotation == 0 and pin_a.rotation == 180:
                h_candidates.append((pin_b, pin_a, False))

            for start_pin, end_pin, is_vertical in h_candidates:
                if end_pin.center.x <= start_pin.center.x:
                    continue
                distance = _pin_distance_sq(start_pin, end_pin)
                if best is None or distance < best_distance:
                    best = (start_pin, end_pin, is_vertical)
                    best_distance = distance

            # ---------- 垂直方向：270° ↔ 90° ----------
            v_candidates = []
            if pin_a.rotation == 270 and pin_b.rotation == 90:
                v_candidates.append((pin_a, pin_b, True))
            if pin_b.rotation == 270 and pin_a.rotation == 90:
                v_candidates.append((pin_b, pin_a, True))

            for start_pin, end_pin, is_vertical in v_candidates:
                # 垂直方向：起始 pin（上，270°）的 y 应大于结束 pin（下，90°）的 y
                if end_pin.center.y >= start_pin.center.y:
                    continue
                distance = _pin_distance_sq(start_pin, end_pin)
                if best is None or distance < best_distance:
                    best = (start_pin, end_pin, is_vertical)
                    best_distance = distance

    return best


def _library_exists(library_name):
    """判断指定 PCell library 是否已经注册。"""
    try:
        return pya.Library.library_by_name(library_name) is not None
    except Exception:
        return False


def _ensure_jnu_libraries_registered():
    """确保 JNU 相关 PCell library 已注册，便于创建可编辑 S_Bend PCell。"""
    if _library_exists(JNULIB_NAME) or _library_exists(BLACKBOX_LIBRARY_NAME):
        return

    pymacros_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if pymacros_dir not in sys.path:
        sys.path.insert(0, pymacros_dir)
    try:
        import JNULib  # noqa: F401  # 导入白盒库入口，会注册 JNULib。
    except Exception:
        pass
    try:
        import JNULib_BlackBox  # noqa: F401  # 黑盒包中只会注册 JNULib_BlackBox。
    except Exception:
        pass


def _sbend_library_name():
    """优先使用白盒 PCell 库；黑盒包中没有白盒库时回退到黑盒库。"""
    _ensure_jnu_libraries_registered()
    if _library_exists(JNULIB_NAME):
        return JNULIB_NAME
    if _library_exists(BLACKBOX_LIBRARY_NAME):
        return BLACKBOX_LIBRARY_NAME
    return JNULIB_NAME


def _create_sbend_connect_pcell(layout, width_um, length_um, height_um):
    """创建 JNU 库中可编辑的 S_Bend PCell variant。"""
    pymacros_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if pymacros_dir not in sys.path:
        sys.path.insert(0, pymacros_dir)

    from JNU_MWP_pcells.s_bend_waveguide import DEFAULT_NPOINTS

    library_name = _sbend_library_name()

    params = {
        "width": width_um,
        "height": height_um,
        "length": length_um,
        "radius": DEFAULT_SBEND_CONNECT_RADIUS,
        "bend_type": "Bezier",
        "bezier": DEFAULT_SBEND_CONNECT_BEZIER,
        "npoints": DEFAULT_NPOINTS,
    }
    sbend_cell = layout.create_cell("S_Bend", library_name, params)
    if sbend_cell is None:
        _ensure_jnu_libraries_registered()
        library_name = _sbend_library_name()
        sbend_cell = layout.create_cell("S_Bend", library_name, params)
    return sbend_cell


def sbend_connect():
    """自动在两个选中的 cell instance 最近水平相向 pin 之间插入可编辑 S_Bend PCell。"""
    view = None
    transaction_started = False
    try:
        view, layout, cell = _active_context()

        selected_objects = _selected_cell_instance_objects(view)
        if len(selected_objects) != 2:
            _message("JNU_MWP_PDK", "请恰好选中两个 Cell Instance，再执行 SBend connect。")
            return

        pin_groups = []
        for obj in selected_objects:
            inst = obj.inst()
            if inst is None or inst.cell is None:
                _message("JNU_MWP_PDK", "选中的 instance 没有对应的 cell。")
                return
            if _is_array_instance(inst):
                _message("JNU_MWP_PDK", "SBend 自动连接暂不展开 array instance，请先解除阵列。")
                return

            pins = _pins_for_instance(inst, _instance_transform(obj), layout)
            if not pins:
                _message("JNU_MWP_PDK", "选中的 cell '%s' 中未找到 PinRec 光学端口。" % inst.cell.name)
                return
            pin_groups.append(pins)

        pin_pair = _choose_sbend_pin_pair(pin_groups[0], pin_groups[1])
        if pin_pair is None:
            _message(
                "JNU_MWP_PDK",
                "未找到可用的相向 optical pins。\n"
                "支持水平方向(0°↔180°)和垂直方向(270°↔90°)。",
            )
            return

        start_pin, end_pin, is_vertical = pin_pair

        if is_vertical:
            length_dbu = end_pin.center.y - start_pin.center.y
            height_dbu = end_pin.center.x - start_pin.center.x
        else:
            length_dbu = end_pin.center.x - start_pin.center.x
            height_dbu = end_pin.center.y - start_pin.center.y

        if abs(length_dbu) < 1:
            _message("JNU_MWP_PDK", "两个 pin 的轴向距离太小，无法生成 S 弯。")
            return

        width_dbu = min(start_pin.width, end_pin.width)
        if width_dbu <= 0:
            _message("JNU_MWP_PDK", "识别到的 pin 宽度无效，无法生成 S 弯。")
            return

        width_um = width_dbu * layout.dbu
        length_um = abs(length_dbu) * layout.dbu
        height_um = height_dbu * layout.dbu

        view.transaction("JNU SBend connect")
        transaction_started = True

        sbend_cell = _create_sbend_connect_pcell(layout, width_um, length_um, height_um)
        if sbend_cell is None:
            raise RuntimeError("无法生成可编辑 S_Bend PCell。")

        rotation = pya.Trans.R270 if is_vertical else pya.Trans.R0
        cell.insert(
            pya.CellInstArray(
                sbend_cell.cell_index(),
                pya.Trans(rotation, start_pin.center.x, start_pin.center.y),
            )
        )

        view.commit()
        transaction_started = False
        _main_window().redraw()
        _message(
            "JNU_MWP_PDK",
            "已生成可编辑 S_Bend：width=%.3fum, length=%.3fum, height=%.3fum。"
            % (width_um, length_um, height_um),
        )
    except Exception as error:
        if transaction_started and view is not None:
            try:
                view.cancel()
            except Exception:
                pass
        _message("JNU_MWP_PDK", "SBend connect 失败：\n%s" % error)


def sbend_connect_between_two_cells():
    """兼容旧入口：转调新的 SBend connect。"""
    return sbend_connect()

__all__ = [
    "sbend_connect",
    "sbend_connect_between_two_cells",
    "_create_sbend_connect_pcell",
    "_pins_for_instance",
    "_choose_sbend_pin_pair",
    "DEFAULT_SBEND_CONNECT_BEZIER",
    "DEFAULT_SBEND_CONNECT_RADIUS",
]
