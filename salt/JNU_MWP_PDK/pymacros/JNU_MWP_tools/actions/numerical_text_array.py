# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""生成由 Basic.Text 实例组成的数字文本阵列，并进入交互式实例放置模式。"""

import re

import pya

from JNU_MWP_tools.core.common import _active_context, _main_window, _message, _value
from JNU_MWP_tools.core.gui_state import exec_dialog_with_persisted_size


TOOL_TITLE = "Numerical text array"
TEXT_LAYER = pya.LayerInfo(10, 0, "Text")
MAX_ITEMS = 10000
CONFIG_PREFIX = "jnu-numerical-text-array-"


def generate_number_sequence(start, end, step, max_items=MAX_ITEMS):
    """生成包含边界内所有整数的等差编号序列。"""
    start = int(start)
    end = int(end)
    step = int(step)
    if step == 0:
        raise ValueError("步长不能为 0。")
    if start == end:
        return [start]
    if start < end and step < 0:
        raise ValueError("递增编号必须使用正步长。")
    if start > end and step > 0:
        raise ValueError("递减编号必须使用负步长。")

    values = []
    current = start
    if start <= end:
        while current <= end:
            values.append(current)
            if len(values) > max_items:
                raise ValueError("编号数量不能超过 %d。" % max_items)
            current += step
    else:
        while current >= end:
            values.append(current)
            if len(values) > max_items:
                raise ValueError("编号数量不能超过 %d。" % max_items)
            current += step
    return values


def validate_magnification(magnification):
    """校验并返回 Basic.Text 的 magnification 参数。"""
    magnification = float(magnification)
    if magnification <= 0:
        raise ValueError("Basic.Text magnification 必须大于 0。")
    return magnification


def _layer_key(layer_info):
    return int(_value(layer_info, "layer")), int(_value(layer_info, "datatype"))


def _layer_name(layer_info):
    try:
        return str(_value(layer_info, "name") or "")
    except Exception:
        return ""


def _layer_label(layer_info):
    layer, datatype = _layer_key(layer_info)
    name = _layer_name(layer_info)
    return "%s (%d/%d)" % (name, layer, datatype) if name else "%d/%d" % (layer, datatype)


def collect_layer_choices(view, layout):
    """从当前视图和版图收集可用于 Basic.Text 的确定 Layer/Datatype。"""
    choices = {}

    def add(layer_info):
        try:
            layer, datatype = _layer_key(layer_info)
        except Exception:
            return
        if layer < 0 or datatype < 0:
            return
        key = (layer, datatype)
        old = choices.get(key)
        if old is None or (not _layer_name(old) and _layer_name(layer_info)):
            choices[key] = pya.LayerInfo(layer, datatype, _layer_name(layer_info))

    try:
        for layer_info in _value(layout, "layer_infos"):
            add(layer_info)
    except Exception:
        pass

    try:
        layer_list_count = int(_value(view, "num_layer_lists"))
    except Exception:
        layer_list_count = 0
    for layer_list_index in range(layer_list_count):
        try:
            iterator = view.begin_layers(layer_list_index)
            while not iterator.at_end():
                properties = iterator.current()
                layer = int(properties.source_layer)
                datatype = int(properties.source_datatype)
                name = str(getattr(properties, "name", "") or "")
                add(pya.LayerInfo(layer, datatype, name))
                iterator.next()
        except Exception:
            continue

    add(TEXT_LAYER)
    text_key = _layer_key(TEXT_LAYER)
    ordered_keys = [text_key] + sorted(key for key in choices if key != text_key)
    return [choices[key] for key in ordered_keys]


def _config_value(name, default):
    app = pya.Application.instance()
    if app is None:
        return str(default)
    try:
        value = app.get_config(CONFIG_PREFIX + name)
    except Exception:
        value = None
    return str(value) if value not in (None, "") else str(default)


def _save_config(params):
    app = pya.Application.instance()
    if app is None:
        return
    saved = {
        "start": params["start"],
        "end": params["end"],
        "step": params["step"],
        "direction": params["direction"],
        "layer": "%d/%d" % _layer_key(params["layer"]),
        "spacing": params["spacing"],
        "magnification": params["magnification"],
    }
    for name, value in saved.items():
        try:
            app.set_config(CONFIG_PREFIX + name, str(value))
        except Exception:
            pass


def _line_row(parent, label_text, value):
    row = pya.QHBoxLayout()
    label = pya.QLabel(label_text, parent)
    edit = pya.QLineEdit(parent)
    edit.setText(str(value))
    row.addWidget(label)
    row.addWidget(edit)
    return row, edit


def show_numerical_text_array_dialog(view, layout):
    """显示参数弹窗并返回已校验的生成参数。"""
    dialog = pya.QDialog(_main_window())
    dialog.setWindowTitle(TOOL_TITLE)
    form = pya.QVBoxLayout(dialog)
    dialog.setLayout(form)

    info = pya.QLabel(
        "生成 Basic.Text 编号序列，并把全部文字组合为一个可放置的 Cell。",
        dialog,
    )
    form.addWidget(info)

    row, start_edit = _line_row(dialog, "起始编号", _config_value("start", 1))
    form.addLayout(row)
    row, end_edit = _line_row(dialog, "结束编号", _config_value("end", 10))
    form.addLayout(row)
    row, step_edit = _line_row(dialog, "步长", _config_value("step", 1))
    form.addLayout(row)

    direction_row = pya.QHBoxLayout()
    direction_row.addWidget(pya.QLabel("排列方向", dialog))
    direction_combo = pya.QComboBox(dialog)
    direction_combo.addItem("Horizontal")
    direction_combo.addItem("Vertical")
    if _config_value("direction", "Horizontal").lower() == "vertical":
        direction_combo.setCurrentIndex(1)
    direction_row.addWidget(direction_combo)
    form.addLayout(direction_row)

    layer_choices = collect_layer_choices(view, layout)
    layer_row = pya.QHBoxLayout()
    layer_row.addWidget(pya.QLabel("目标层", dialog))
    layer_combo = pya.QComboBox(dialog)
    saved_layer = _config_value("layer", "10/0")
    selected_layer_index = 0
    for index, layer_info in enumerate(layer_choices):
        layer_combo.addItem(_layer_label(layer_info))
        if "%d/%d" % _layer_key(layer_info) == saved_layer:
            selected_layer_index = index
    layer_combo.setCurrentIndex(selected_layer_index)
    layer_row.addWidget(layer_combo)
    form.addLayout(layer_row)

    row, spacing_edit = _line_row(
        dialog,
        "文字中心距 (µm)",
        _config_value("spacing", 10.0),
    )
    form.addLayout(row)
    row, magnification_edit = _line_row(
        dialog,
        "Basic.Text magnification",
        _config_value("magnification", 10.0),
    )
    form.addLayout(row)

    buttons = pya.QHBoxLayout(dialog)
    ok = pya.QPushButton("OK", dialog)
    cancel = pya.QPushButton("Cancel", dialog)
    cancel.clicked(lambda _checked: dialog.reject())
    ok.clicked(lambda _checked: dialog.accept())
    buttons.addWidget(ok)
    buttons.addWidget(cancel)
    form.addLayout(buttons)

    if exec_dialog_with_persisted_size(dialog, "numerical_text_array") == 0:
        return None

    try:
        start = int(str(_value(start_edit, "text")).strip())
        end = int(str(_value(end_edit, "text")).strip())
        step = int(str(_value(step_edit, "text")).strip())
        values = generate_number_sequence(start, end, step)
        spacing = float(str(_value(spacing_edit, "text")).strip())
        magnification = float(str(_value(magnification_edit, "text")).strip())
        if spacing < 0:
            raise ValueError("文字中心距不能小于 0 µm。")
        validate_magnification(magnification)
    except Exception as error:
        _message(TOOL_TITLE, str(error))
        return None

    layer_index = int(_value(layer_combo, "currentIndex"))
    params = {
        "start": start,
        "end": end,
        "step": step,
        "values": values,
        "direction": str(_value(direction_combo, "currentText")),
        "layer": layer_choices[layer_index],
        "spacing": spacing,
        "magnification": magnification,
    }
    _save_config(params)
    return params


def _number_token(value):
    value = int(value)
    return "m%d" % abs(value) if value < 0 else str(value)


def _safe_cell_name(layout, base_name):
    clean = re.sub(r"[^A-Za-z0-9_]+", "_", str(base_name)).strip("_")
    clean = clean or "Numerical_Text_Array"
    name = clean
    suffix = 2
    while layout.cell(name) is not None:
        name = "%s_%d" % (clean, suffix)
        suffix += 1
    return name


def _default_cell_name(values, direction):
    axis = "H" if str(direction).lower().startswith("h") else "V"
    return "Numerical_Text_Array_%s_%s_%s" % (
        _number_token(values[0]),
        _number_token(values[-1]),
        axis,
    )


def _basic_text_cell(layout, text, layer_info, magnification):
    mag = validate_magnification(magnification)
    params = {
        "text": str(text),
        "layer": layer_info,
        "mag": mag,
        "font": 0,
        "font_name": "std_font",
        "inverse": False,
        "bias": 0.0,
        "cspacing": 0.0,
        "lspacing": 0.0,
    }
    cell = layout.create_cell("TEXT", "Basic", params)
    if cell is None:
        raise RuntimeError("无法创建 Basic.Text；请确认 KLayout Basic library 已加载。")
    try:
        actual_mag = float(cell.pcell_parameters_by_name().get("mag"))
    except Exception:
        actual_mag = mag
    if abs(actual_mag - mag) > 1e-9:
        raise RuntimeError(
            "Basic.Text magnification %.6f 与目标 %.6f 不一致。"
            % (actual_mag, mag)
        )
    return cell


def create_numerical_text_array_cell(
    layout,
    values,
    direction,
    layer_info,
    spacing_um,
    magnification,
    cell_name=None,
):
    """创建只含 Basic.Text 实例的普通容器 Cell。"""
    values = [int(value) for value in values]
    if not values:
        raise ValueError("编号序列不能为空。")
    if len(values) > MAX_ITEMS:
        raise ValueError("编号数量不能超过 %d。" % MAX_ITEMS)
    direction = str(direction)
    horizontal = direction.lower().startswith("h")
    if not horizontal and not direction.lower().startswith("v"):
        raise ValueError("排列方向必须为 Horizontal 或 Vertical。")
    spacing_um = float(spacing_um)
    if spacing_um < 0:
        raise ValueError("文字中心距不能小于 0 µm。")
    validate_magnification(magnification)

    children = [
        _basic_text_cell(layout, value, layer_info, magnification)
        for value in values
    ]
    base_name = cell_name or _default_cell_name(values, direction)
    container = layout.create_cell(_safe_cell_name(layout, base_name))
    if container is None:
        raise RuntimeError("无法创建数字文本阵列 Cell。")

    pitch = int(round(spacing_um / float(layout.dbu)))
    placements = []
    try:
        for index, child in enumerate(children):
            bbox = child.bbox()
            if bbox.empty():
                raise RuntimeError("Basic.Text '%s' 没有生成有效几何。" % child.name)
            center_x = 0.5 * (bbox.left + bbox.right)
            center_y = 0.5 * (bbox.bottom + bbox.top)
            if horizontal:
                dx = int(round(index * pitch - center_x))
                dy = int(round(-center_y))
            else:
                dx = int(round(-center_x))
                dy = int(round(index * pitch - center_y))
            placements.append((child, bbox, dx, dy))

        min_left = min(bbox.left + dx for _child, bbox, dx, _dy in placements)
        min_bottom = min(bbox.bottom + dy for _child, bbox, _dx, dy in placements)
        shift_x = -min_left
        shift_y = -min_bottom
        for child, _bbox, dx, dy in placements:
            container.insert(
                pya.CellInstArray(
                    child.cell_index(),
                    pya.Trans(0, False, int(dx + shift_x), int(dy + shift_y)),
                )
            )
    except Exception:
        try:
            layout.delete_cell(container.cell_index())
        except Exception:
            pass
        raise

    bbox = container.bbox()
    if bbox.empty() or bbox.left != 0 or bbox.bottom != 0:
        try:
            layout.delete_cell(container.cell_index())
        except Exception:
            pass
        raise RuntimeError("数字文本阵列 Cell 未正确归一化到坐标原点。")
    return container


def enter_instance_placement(cell):
    """把新 Cell 交给 KLayout 原生 Instance 工具进行鼠标跟随放置。"""
    app = pya.Application.instance()
    main_window = _main_window()
    if app is None or main_window is None or main_window.current_view() is None:
        return False

    try:
        main_window.cancel()
    except Exception:
        pass

    settings = {
        "edit-inst-angle": "0",
        "edit-inst-mirror": "false",
        "edit-inst-place-origin": "true",
        "edit-inst-scale": "1",
        "edit-inst-cell-name": str(cell.name),
        "edit-inst-lib-name": "",
        "edit-inst-cell-lib-name": "",
        "edit-inst-pcell-parameters": "",
        "edit-inst-array": "false",
    }
    for name, value in settings.items():
        app.set_config(name, value)

    action = main_window.menu().action("edit_menu.mode_menu.instance")
    if action is None:
        return False
    trigger = getattr(action, "trigger", None)
    if not callable(trigger):
        return False

    def accept_editor_options():
        for widget in pya.QApplication.topLevelWidgets():
            try:
                object_name = str(_value(widget, "objectName"))
                if object_name == "EditorOptionsDialog":
                    widget.accept()
                    return True
            except Exception:
                continue
        return False

    try:
        # Instance 参数页会进入自身事件循环；预先注册零延时回调，
        # 使参数页出现后立即确认，再把控制权交给鼠标放置模式。
        timer = pya.QTimer()
        timer.setSingleShot(True)
        timer.timeout(accept_editor_options)
        main_window._jnu_instance_dialog_timer = timer
        timer.start(0)
    except Exception:
        pass
    trigger()
    try:
        main_window._jnu_instance_dialog_timer = None
    except Exception:
        pass
    try:
        accept_editor_options()
    except Exception:
        # 若参数页无法自动关闭，保持其打开状态，用户仍可确认后继续放置。
        pass
    return True


def numerical_text_array():
    """菜单入口：创建数字文本阵列 Cell 并进入交互式放置。"""
    view = None
    transaction_started = False
    try:
        view, layout, _active_cell = _active_context()
        params = show_numerical_text_array_dialog(view, layout)
        if params is None:
            return

        view.transaction("JNU Numerical text array")
        transaction_started = True
        cell = create_numerical_text_array_cell(
            layout,
            params["values"],
            params["direction"],
            params["layer"],
            params["spacing"],
            params["magnification"],
        )
        view.commit()
        transaction_started = False

        try:
            _main_window().redraw()
        except Exception:
            pass
        if not enter_instance_placement(cell):
            _message(
                TOOL_TITLE,
                "已生成 Cell '%s'，但无法自动进入 Instance 放置模式。\n"
                "请从 Cells/Instance 界面手动放置该 Cell。" % cell.name,
            )
    except Exception as error:
        if transaction_started and view is not None:
            try:
                view.cancel()
            except Exception:
                try:
                    view.commit()
                except Exception:
                    pass
        _message(TOOL_TITLE, "生成失败：\n%s" % error)


__all__ = [
    "MAX_ITEMS",
    "generate_number_sequence",
    "validate_magnification",
    "collect_layer_choices",
    "create_numerical_text_array_cell",
    "enter_instance_placement",
    "numerical_text_array",
]
