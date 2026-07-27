# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""Snap components 的端口匹配和平移逻辑回归。"""

import os
import sys

import pya


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PYMACROS_DIR = os.path.dirname(os.path.dirname(THIS_DIR))
if PYMACROS_DIR not in sys.path:
    sys.path.insert(0, PYMACROS_DIR)

from JNU_MWP_tools.core.common import PIN_LAYER, _value
from JNU_MWP_tools.core.make_pin import make_pin
import JNU_MWP_tools.actions.snap_components as snap_tool
from JNU_MWP_tools.actions.snap_components import (
    _build_instance_record,
    _move_records,
    _moving_records_from_selection,
    _pins_for_instance,
    choose_snap_pin_pair,
    perform_snap,
    snap_translation,
)


def _layout():
    layout = pya.Layout()
    layout.dbu = 0.001
    layout.layer(PIN_LAYER)
    return layout


def _pin_cell(layout, name, rotation):
    cell = layout.create_cell(name)
    pin_layer = layout.layer(PIN_LAYER)
    make_pin(cell, "opt1", pya.Point(0, 0), 500, pin_layer, rotation)
    return cell


def _pin_path_shape(cell, layout, center, rotation, width=500):
    pin_layer = layout.layer(PIN_LAYER)
    if rotation % 360 == 0:
        pts = [pya.Point(center.x - 10, center.y), pya.Point(center.x + 10, center.y)]
    elif rotation % 360 == 180:
        pts = [pya.Point(center.x + 10, center.y), pya.Point(center.x - 10, center.y)]
    elif rotation % 360 == 90:
        pts = [pya.Point(center.x, center.y - 10), pya.Point(center.x, center.y + 10)]
    else:
        pts = [pya.Point(center.x, center.y + 10), pya.Point(center.x, center.y - 10)]
    shape = cell.shapes(pin_layer).insert(pya.Path(pts, width))
    return shape, pin_layer


def _non_pin_shape(cell, layout):
    layer = layout.layer(pya.LayerInfo(1, 0))
    shape = cell.shapes(layer).insert(pya.Box(0, 0, 1000, 1000))
    return shape, layer


def _insert(top, cell, x, y):
    return top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans(pya.Trans.R0, x, y)))


def _record(inst, layout, label):
    return _build_instance_record(None, inst, _value(inst, "trans"), layout, key=label, label=label)


def _pin_center(inst, layout):
    pins = _pins_for_instance(inst, _value(inst, "trans"), layout)
    if len(pins) != 1:
        raise RuntimeError("测试 pin 数量错误。")
    return pins[0].center


def _assert_point(point, x, y, message):
    if point.x != x or point.y != y:
        raise RuntimeError("%s：得到 (%d,%d)，期望 (%d,%d)。" % (message, point.x, point.y, x, y))


class _FakeSelectionObject(object):
    def __init__(self, inst=None, shape=None, layer=None):
        self._inst = inst
        self._shape = shape
        self._layer = layer

    def is_cell_inst(self):
        return self._inst is not None

    def inst(self):
        return self._inst

    def shape(self):
        return self._shape

    def layer(self):
        return self._layer

    def trans(self):
        return pya.Trans.R0


class _FakeView(object):
    def __init__(self, objects):
        self.object_selection = objects


def _test_single_selected_instance_to_transient_reference():
    layout = _layout()
    top = layout.create_cell("TOP_SINGLE")
    fixed_cell = _pin_cell(layout, "FIXED_RIGHT", 0)
    moving_cell = _pin_cell(layout, "MOVING_LEFT", 180)

    fixed = _insert(top, fixed_cell, 0, 0)
    moving = _insert(top, moving_cell, 20000, 5000)

    pair, trans, moved = perform_snap(
        layout,
        [_record(moving, layout, "moving")],
        [_record(fixed, layout, "fixed")],
    )
    if pair is None or moved != 1:
        raise RuntimeError("单实例吸附未移动。")
    _assert_point(trans, -20000, -5000, "单实例平移量错误")
    _assert_point(_pin_center(moving, layout), 0, 0, "单实例吸附后端口未重合")


def _test_nearest_pair_among_moving_group_and_fixed_reference():
    layout = _layout()
    top = layout.create_cell("TOP_GROUPS")
    fixed_cell = _pin_cell(layout, "FIXED_RIGHT_GROUP", 0)
    moving_cell = _pin_cell(layout, "MOVING_LEFT_GROUP", 180)

    fixed = _insert(top, fixed_cell, 100000, 0)
    moving_near = _insert(top, moving_cell, 98000, 0)
    moving_far = _insert(top, moving_cell, 12000, 1000)

    moving_records = [_record(moving_far, layout, "moving_far"), _record(moving_near, layout, "moving_near")]
    pair = choose_snap_pin_pair([_record(fixed, layout, "fixed")], moving_records)
    if pair is None:
        raise RuntimeError("多实例移动组相向端口未被识别。")
    if pair.fixed_pin.instance.label != "fixed" or pair.moving_pin.instance.label != "moving_near":
        raise RuntimeError("未选择距离悬停参考实例最近的移动组端口。")


def _test_no_opposite_rotation():
    layout = _layout()
    top = layout.create_cell("TOP_NO_MATCH")
    fixed_cell = _pin_cell(layout, "FIXED_RIGHT_NO_MATCH", 0)
    moving_cell = _pin_cell(layout, "MOVING_RIGHT_NO_MATCH", 0)

    fixed = _insert(top, fixed_cell, 0, 0)
    moving = _insert(top, moving_cell, 10000, 0)
    if choose_snap_pin_pair([_record(fixed, layout, "fixed")], [_record(moving, layout, "moving")]) is not None:
        raise RuntimeError("同向端口被错误识别为可吸附。")


def _test_group_translation_keeps_relative_offset():
    layout = _layout()
    top = layout.create_cell("TOP_MOVE_GROUP")
    fixed_cell = _pin_cell(layout, "FIXED_RIGHT_MOVE", 0)
    moving_cell = _pin_cell(layout, "MOVING_LEFT_MOVE", 180)

    fixed = _insert(top, fixed_cell, 0, 0)
    moving_a = _insert(top, moving_cell, 20000, 0)
    moving_b = _insert(top, moving_cell, 30000, 7000)

    pair = choose_snap_pin_pair(
        [_record(fixed, layout, "fixed")],
        [_record(moving_a, layout, "moving_a"), _record(moving_b, layout, "moving_b")],
    )
    trans = snap_translation(pair)
    before_delta = _pin_center(moving_b, layout) - _pin_center(moving_a, layout)
    _move_records([_record(moving_a, layout, "moving_a"), _record(moving_b, layout, "moving_b")], trans)
    after_delta = _pin_center(moving_b, layout) - _pin_center(moving_a, layout)
    _assert_point(after_delta, before_delta.x, before_delta.y, "组内相对位置发生变化")
    _assert_point(_pin_center(moving_a, layout), 0, 0, "移动组主端口未吸附到固定端口")


def _test_duplicate_reference_rejected():
    layout = _layout()
    top = layout.create_cell("TOP_DUPLICATE")
    cell = _pin_cell(layout, "DUPLICATE_CELL", 0)
    inst = _insert(top, cell, 0, 0)
    record = _record(inst, layout, "same")
    try:
        perform_snap(layout, [record], [record])
    except RuntimeError as error:
        if "参考对象" not in str(error):
            raise
        return
    raise RuntimeError("移动组包含参考对象时未拒绝。")


def _test_primitive_mixed_selection_moves_all_selected_objects():
    layout = _layout()
    top = layout.create_cell("TOP_PRIMITIVE_MIXED")
    moving_cell = _pin_cell(layout, "MOVING_WITH_PRIMITIVE", 180)
    moving = _insert(top, moving_cell, 20000, 0)
    shape, layer = _non_pin_shape(top, layout)
    before_bbox = shape.bbox()

    view = _FakeView([_FakeSelectionObject(shape=shape, layer=layer), _FakeSelectionObject(moving)])
    records = _moving_records_from_selection(view, layout)
    if len(records) != 2:
        raise RuntimeError("混选 primitive 时未保留全部移动对象。")
    _move_records(records, pya.Point(1000, 0))
    after_bbox = shape.bbox()
    if after_bbox.left != before_bbox.left + 1000:
        raise RuntimeError("混选 primitive 未随移动组一起平移。")


def _test_pinrec_primitive_selection_is_accepted():
    layout = _layout()
    top = layout.create_cell("TOP_PINREC_PRIMITIVE")
    shape, layer = _pin_path_shape(top, layout, pya.Point(20000, 0), 180)
    fixed_cell = _pin_cell(layout, "FIXED_FOR_PRIMITIVE", 0)
    fixed = _insert(top, fixed_cell, 0, 0)

    records = _moving_records_from_selection(_FakeView([_FakeSelectionObject(shape=shape, layer=layer)]), layout)
    pair, trans, moved = perform_snap(layout, records, [_record(fixed, layout, "fixed")])
    if moved != 1:
        raise RuntimeError("只选中 PinRec primitive 时未移动。")
    _assert_point(trans, -20000, 0, "PinRec primitive 平移量错误")


def _test_only_non_pin_primitive_selection_rejected():
    layout = _layout()
    top = layout.create_cell("TOP_NON_PIN_PRIMITIVE")
    shape, layer = _non_pin_shape(top, layout)
    view = _FakeView([_FakeSelectionObject(shape=shape, layer=layer)])
    try:
        _moving_records_from_selection(view, layout)
    except RuntimeError as error:
        if "未找到 PinRec 光学端口" not in str(error):
            raise
        return
    raise RuntimeError("只有非 PinRec primitive 选择时未拒绝。")


def _test_gui_success_is_silent_and_failure_is_reported():
    """成功和已重合均静默，只有失败调用消息弹窗。"""
    class _FakeMainWindow(object):
        def __init__(self):
            self.redraw_count = 0

        def redraw(self):
            self.redraw_count += 1

    class _FakeLayout(object):
        dbu = 0.001

    main_window = _FakeMainWindow()
    messages = []
    originals = {
        "_main_window": snap_tool._main_window,
        "_active_context": snap_tool._active_context,
        "_moving_records_from_selection": snap_tool._moving_records_from_selection,
        "_fixed_record_from_transient": snap_tool._fixed_record_from_transient,
        "_perform_snap_in_view": snap_tool._perform_snap_in_view,
        "_message": snap_tool._message,
    }
    try:
        snap_tool._main_window = lambda: main_window
        snap_tool._active_context = lambda: (object(), _FakeLayout(), object())
        snap_tool._moving_records_from_selection = lambda _view, _layout: [object()]
        snap_tool._fixed_record_from_transient = lambda _view, _layout: object()
        snap_tool._message = lambda title, text: messages.append((title, text))

        snap_tool._perform_snap_in_view = lambda *_args: (object(), pya.Point(100, 0), 1)
        snap_tool.snap_components()
        if messages or main_window.redraw_count != 1:
            raise RuntimeError("Snap 成功后仍提示，或未刷新版图。")

        snap_tool._perform_snap_in_view = lambda *_args: (object(), pya.Point(0, 0), 0)
        snap_tool.snap_components()
        if messages or main_window.redraw_count != 1:
            raise RuntimeError("端口已重合时仍提示或发生多余刷新。")

        snap_tool._active_context = lambda: (_ for _ in ()).throw(RuntimeError("测试失败"))
        snap_tool.snap_components()
        if len(messages) != 1 or "测试失败" not in messages[0][1]:
            raise RuntimeError("Snap 失败时未保留错误提示。")
    finally:
        for name, value in originals.items():
            setattr(snap_tool, name, value)


def main():
    _test_single_selected_instance_to_transient_reference()
    _test_nearest_pair_among_moving_group_and_fixed_reference()
    _test_no_opposite_rotation()
    _test_group_translation_keeps_relative_offset()
    _test_duplicate_reference_rejected()
    _test_primitive_mixed_selection_moves_all_selected_objects()
    _test_pinrec_primitive_selection_is_accepted()
    _test_only_non_pin_primitive_selection_rejected()
    _test_gui_success_is_silent_and_failure_is_reported()
    print("Snap components regression: PASS")


if __name__ == "__main__":
    main()
