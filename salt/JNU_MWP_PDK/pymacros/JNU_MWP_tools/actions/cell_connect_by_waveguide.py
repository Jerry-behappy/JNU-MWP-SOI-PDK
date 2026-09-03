# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-08

"""在两个 Cell Instance 的最近相向光学端口之间自动插入连接波导。"""

import pya

from JNU_MWP_tools.actions.sbend_connect import (
    _choose_sbend_pin_pair,
    _create_sbend_connect_pcell,
    _instance_transform,
    _is_array_instance,
    _pins_for_instance,
    _selected_cell_instance_objects,
)
from JNU_MWP_tools.actions.path_to_waveguide import (
    TAB_SINGLE,
    _create_waveguide_cell,
    _load_waveguide_params,
    _mark_waveguide,
    _result_from_editable_params,
    _store_waveguide_recovery_property,
)
from JNU_MWP_tools.core.common import _active_context, _main_window, _message


def _create_aligned_waveguide_pcell(layout, width_um, length_um):
    """用 Path to Waveguide 的单宽度流程创建共线连接 PCell。"""
    settings = _load_waveguide_params()
    editable = dict(settings.get(TAB_SINGLE, {}))
    editable["width"] = float(width_um)
    params = _result_from_editable_params(TAB_SINGLE, editable, layout.dbu)
    dpath = pya.DPath(
        [pya.DPoint(0.0, 0.0), pya.DPoint(float(length_um), 0.0)],
        float(width_um),
    )
    waveguide_cell = _create_waveguide_cell(layout, dpath, params, 1)
    return waveguide_cell, dpath


def _connection_dimensions(layout, start_pin, end_pin, is_vertical):
    """把父 Cell 中的两个端口转换为连接 PCell 的局部长度、偏移和宽度。"""
    if is_vertical:
        axis_length_dbu = start_pin.center.y - end_pin.center.y
        lateral_offset_dbu = end_pin.center.x - start_pin.center.x
        rotation = pya.Trans.R270
    else:
        axis_length_dbu = end_pin.center.x - start_pin.center.x
        lateral_offset_dbu = end_pin.center.y - start_pin.center.y
        rotation = pya.Trans.R0

    if axis_length_dbu < 1:
        raise RuntimeError("两个端口的轴向距离太小，无法生成连接波导。")

    width_dbu = min(int(start_pin.width), int(end_pin.width))
    if width_dbu < 1:
        raise RuntimeError("识别到的端口宽度无效，无法生成连接波导。")

    return {
        "width_um": width_dbu * float(layout.dbu),
        "length_um": axis_length_dbu * float(layout.dbu),
        "height_um": lateral_offset_dbu * float(layout.dbu),
        "lateral_offset_dbu": lateral_offset_dbu,
        "rotation": rotation,
    }


def _prepare_connection(layout, start_pin, end_pin, is_vertical):
    """按端口是否共线选择内部 Waveguide 或公开 S_Bend PCell。"""
    result = _connection_dimensions(layout, start_pin, end_pin, is_vertical)
    if result["lateral_offset_dbu"] == 0:
        connection_cell, dpath = _create_aligned_waveguide_pcell(
            layout,
            result["width_um"],
            result["length_um"],
        )
        result["kind"] = "Waveguide"
        result["raw_dpath"] = dpath
    else:
        connection_cell = _create_sbend_connect_pcell(
            layout,
            result["width_um"],
            result["length_um"],
            result["height_um"],
        )
        result["kind"] = "S_Bend"

    if connection_cell is None:
        raise RuntimeError("无法创建可编辑的 %s PCell。" % result["kind"])
    result["cell"] = connection_cell
    result["trans"] = pya.Trans(
        result["rotation"],
        start_pin.center.x,
        start_pin.center.y,
    )
    return result


def _insert_prepared_connection(parent_cell, connection):
    """插入已预生成的连接 PCell，并写入内部 Waveguide 的恢复属性。"""
    connection_instance = parent_cell.insert(
        pya.CellInstArray(
            connection["cell"].cell_index(),
            connection["trans"],
        )
    )
    if connection["kind"] == "Waveguide":
        # 与 Path to Waveguide 保持一致：实例属性用于 GDS 展开后的原始 Path 恢复。
        _store_waveguide_recovery_property(
            connection_instance,
            connection["raw_dpath"],
        )
        _mark_waveguide(connection_instance, "single")
    return connection_instance


def cell_connect_by_waveguide():
    """连接两个选中 Cell Instance 的最近相向 PinRec 光学端口。"""
    view = None
    transaction_started = False
    try:
        view, layout, parent_cell = _active_context()
        selected_objects = _selected_cell_instance_objects(view)
        if len(selected_objects) != 2:
            _message(
                "JNU_MWP_PDK",
                "请恰好选中两个 Cell Instance，再执行 Cell Connect by Waveguide。",
            )
            return

        pin_groups = []
        for obj in selected_objects:
            inst = obj.inst()
            if inst is None or inst.cell is None:
                _message("JNU_MWP_PDK", "选中的 instance 没有对应的 cell。")
                return
            if _is_array_instance(inst):
                _message(
                    "JNU_MWP_PDK",
                    "Cell Connect by Waveguide 暂不展开 array instance，请先解除阵列。",
                )
                return
            pins = _pins_for_instance(inst, _instance_transform(obj), layout)
            if not pins:
                _message(
                    "JNU_MWP_PDK",
                    "选中的 cell '%s' 中未找到 PinRec 光学端口。" % inst.cell.name,
                )
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
        # 先完成 PCell variant 生产，再进入版图事务；事务中只插入实例。
        connection = _prepare_connection(layout, start_pin, end_pin, is_vertical)

        view.transaction("JNU Cell Connect by Waveguide")
        transaction_started = True
        _insert_prepared_connection(parent_cell, connection)
        view.commit()
        transaction_started = False

        main_window = _main_window()
        if main_window is not None:
            main_window.redraw()
        if connection["kind"] == "Waveguide":
            detail = "width=%.3fum, length=%.3fum" % (
                connection["width_um"],
                connection["length_um"],
            )
        else:
            detail = "width=%.3fum, length=%.3fum, height=%.3fum" % (
                connection["width_um"],
                connection["length_um"],
                connection["height_um"],
            )
        _message(
            "JNU_MWP_PDK",
            "已生成可编辑 %s：%s。" % (connection["kind"], detail),
        )
    except Exception as error:
        if transaction_started and view is not None:
            try:
                view.cancel()
            except Exception:
                pass
        _message("JNU_MWP_PDK", "Cell Connect by Waveguide 失败：\n%s" % error)


__all__ = [
    "cell_connect_by_waveguide",
    "_connection_dimensions",
    "_create_aligned_waveguide_pcell",
    "_insert_prepared_connection",
    "_prepare_connection",
]
