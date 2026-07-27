# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""Path to Waveguide 预设数据、持久化和用户参数页回归。"""

import json
import os
from pathlib import Path
import sys
import tempfile

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
if str(PYMACROS_DIR) not in sys.path:
    sys.path.insert(0, str(PYMACROS_DIR))

import JNU_MWP_tools.actions.path_to_waveguide as path_tool  # noqa: E402
import JNU_MWP_tools.core.gui_state as gui_state  # noqa: E402


def _assert(condition, message):
    if not condition:
        raise RuntimeError(message)


def _qt_value(obj, name):
    value = getattr(obj, name)
    return value() if callable(value) else value


def _check_defaults_and_result_conversion():
    settings = path_tool._default_waveguide_params()
    _assert(settings["schema_version"] == 3, "配置 schema 版本错误。")
    _assert(settings["active_tab"] == path_tool.TAB_SINGLE, "默认页签错误。")
    _assert(not settings["user_defined"]["presets"], "默认配置不应包含预设。")

    single = path_tool._result_from_editable_params(
        path_tool.TAB_SINGLE, settings["single"], 0.001,
    )
    _assert(single["mode"] == path_tool.TAB_SINGLE, "单宽度结果模式错误。")
    _assert(single["npoints"] > 0, "单宽度派生点数错误。")

    composite = path_tool._result_from_editable_params(
        path_tool.TAB_COMPOSITE, settings["composite"], 0.001,
    )
    _assert(composite["start_width"] == composite["straight_width"], "默认起始端宽度错误。")
    _assert(composite["end_width"] == composite["straight_width"], "默认终端宽度错误。")


def _check_preset_naming_deduplication_and_deletion():
    settings = path_tool._default_waveguide_params()
    settings, first, created = path_tool._add_user_preset(
        settings, path_tool.TAB_SINGLE, settings["single"],
    )
    _assert(created, "首次保存单宽度预设未创建。")
    _assert(first["name"] == "Single_W0.500_Circular_R20.000", "单宽度自动名称错误。")
    original_id = first["id"]
    settings, found = path_tool._update_user_preset_note(
        settings, original_id, "中文记录\n第二行",
    )
    _assert(found, "未找到需要更新 Note 的预设。")
    first = path_tool._selected_user_preset(settings, original_id)
    _assert(first["note"] == "中文记录\n第二行", "中文多行 Note 未保存到预设。")
    _assert(first["id"] == original_id, "修改 Note 改变了预设 ID。")

    settings, duplicate, created = path_tool._add_user_preset(
        settings, path_tool.TAB_SINGLE, settings["single"],
    )
    _assert(not created and duplicate["id"] == first["id"], "完全相同参数未去重。")
    _assert(duplicate["note"] == "中文记录\n第二行", "重复保存覆盖了已有 Note。")
    _assert(len(settings["user_defined"]["presets"]) == 1, "相同参数产生重复预设。")

    collision_values = dict(settings["single"])
    collision_values["Euler_Rmax"] = 31.0
    settings, collision, created = path_tool._add_user_preset(
        settings, path_tool.TAB_SINGLE, collision_values,
    )
    _assert(created and collision["name"].endswith("_2"), "同名不同参数未追加后缀。")

    settings, found = path_tool._update_user_preset_name(
        settings, original_id, "常用单模波导",
    )
    _assert(found, "未找到需要重命名的预设。")
    renamed = path_tool._selected_user_preset(settings, original_id)
    _assert(renamed["name"] == "常用单模波导", "Preset Name 未更新。")
    _assert(renamed["id"] == original_id, "修改 Preset Name 改变了预设 ID。")
    _assert(renamed["note"] == "中文记录\n第二行", "修改 Preset Name 改变了 Note。")
    settings, duplicate, created = path_tool._add_user_preset(
        settings, path_tool.TAB_SINGLE, settings["single"],
    )
    _assert(not created and duplicate["name"] == "常用单模波导", "重复保存覆盖了用户名称。")

    settings, composite, created = path_tool._add_user_preset(
        settings, path_tool.TAB_COMPOSITE, settings["composite"],
    )
    _assert(created and composite["name"].startswith("Composite_SW2.000_BW0.500"), "复合预设名称错误。")
    try:
        path_tool._update_user_preset_name(settings, composite["id"], "  ")
        raise RuntimeError("空 Preset Name 未被拒绝。")
    except ValueError:
        pass
    try:
        path_tool._update_user_preset_name(settings, composite["id"], "常用单模波导")
        raise RuntimeError("重复 Preset Name 未被拒绝。")
    except ValueError:
        pass
    euler_values = dict(settings["single"])
    euler_values.update({"bend_type": "Euler", "Euler_Rmax": 60.0, "Euler_Rmin": 20.0})
    settings, euler, created = path_tool._add_user_preset(
        settings, path_tool.TAB_SINGLE, euler_values,
    )
    _assert(created and euler["name"].endswith("Euler_Rmax60.000_Rmin20.000"), "Euler 预设名称错误。")
    settings, deleted = path_tool._delete_user_presets(
        settings, [first["id"], collision["id"], euler["id"]],
    )
    _assert(deleted == 3, "批量删除数量错误。")
    _assert(len(settings["user_defined"]["presets"]) == 1, "批量删除后列表错误。")
    _assert(settings["user_defined"]["selected_id"] == composite["id"], "删除后选中项迁移错误。")


def _check_json_migration_and_atomic_persistence():
    original_path = path_tool._waveguide_params_file
    with tempfile.TemporaryDirectory(prefix="jnu_waveguide_presets_") as directory:
        filepath = os.path.join(directory, "jnu_waveguide_params.json")
        path_tool._waveguide_params_file = lambda: filepath
        try:
            with open(filepath, "w", encoding="utf-8") as stream:
                json.dump({
                    "width": 1.25,
                    "radius": 45.0,
                    "bend_type": "Bezier",
                    "bezier": 0.31,
                    "Euler_Rmax": 50.0,
                    "Euler_Rmin": 20.0,
                }, stream)
            migrated = path_tool._load_waveguide_params()
            _assert(migrated["single"]["width"] == 1.25, "旧平铺 JSON 未迁移。")
            _assert(migrated["composite"]["straight_width"] == 2.0, "旧平铺 JSON 污染复合默认值。")

            legacy = path_tool._default_waveguide_params()
            legacy, legacy_preset, _created = path_tool._add_user_preset(
                legacy, path_tool.TAB_SINGLE, legacy["single"],
            )
            legacy["schema_version"] = 2
            legacy_preset.pop("note", None)
            with open(filepath, "w", encoding="utf-8") as stream:
                json.dump(legacy, stream, ensure_ascii=False)
            migrated_schema = path_tool._load_waveguide_params()
            _assert(migrated_schema["schema_version"] == 3, "schema 2 未迁移到 schema 3。")
            _assert(migrated_schema["user_defined"]["presets"][0]["note"] == "", "旧预设未补空 Note。")

            migrated = migrated_schema

            migrated, preset, _created = path_tool._add_user_preset(
                migrated, path_tool.TAB_SINGLE, migrated["single"],
            )
            migrated["active_tab"] = path_tool.TAB_USER_DEFINED
            path_tool._save_waveguide_params(migrated)
            reloaded = path_tool._load_waveguide_params()
            _assert(reloaded["active_tab"] == path_tool.TAB_USER_DEFINED, "用户页签未持久化。")
            _assert(reloaded["user_defined"]["selected_id"] == preset["id"], "预设选择未持久化。")
            _assert(len(reloaded["user_defined"]["presets"]) == 1, "预设未持久化。")
            leftovers = [name for name in os.listdir(directory) if name.endswith(".tmp")]
            _assert(not leftovers, "原子写入留下临时文件。")

            with open(filepath, "w", encoding="utf-8") as stream:
                stream.write("{invalid json")
            fallback = path_tool._load_waveguide_params()
            _assert(fallback["single"]["width"] == 0.5, "损坏 JSON 未回退默认值。")
        finally:
            path_tool._waveguide_params_file = original_path


def _check_qt_pages_when_available():
    if os.environ.get("JNU_RUN_QT_WIDGET_TESTS") != "1":
        return
    if not hasattr(pya, "QGroupBox") or not hasattr(pya, "QApplication"):
        return
    try:
        if pya.QApplication.instance() is None:
            return
    except Exception:
        return
    parent = pya.QWidget()
    settings = path_tool._default_waveguide_params()
    single = path_tool._build_waveguide_page(parent, settings["single"], False, 0.001)
    composite = path_tool._build_waveguide_page(parent, settings["composite"], True, 0.001)
    empty_user_page = path_tool._build_user_defined_page(parent)
    path_tool._refresh_user_defined_page(empty_user_page, settings, 0.001)
    _assert(not empty_user_page["note_edit"].isEnabled(), "无预设时 Note 仍可编辑。")
    _assert(empty_user_page["selection_group"].title == "Saved Types", "Saved Types 标题错误。")
    _assert(empty_user_page["preview_group"].title == "Selected Parameters", "Selected Parameters 标题错误。")
    _assert(single["editable_group"].title == "Editable Parameters", "单宽度可编辑栏标题错误。")
    _assert(single["calculated_group"].title == "Calculated Parameters", "单宽度计算栏标题错误。")
    _assert(single["editable_order"][0] == "bend_type", "单宽度 Bend Type 不是首个参数。")
    _assert(
        composite["editable_order"].index("bend_type")
        < composite["editable_order"].index("radius"),
        "复合波导 Bend Type 未位于 Bend Radius 前。",
    )
    for controls in (single, composite):
        for key in ("editable_group", "calculated_group"):
            style = str(controls[key].styleSheet).replace(" ", "").lower()
            _assert("font-size:16pt" in style and "font-weight:bold" in style, "参数分组标题样式不是16pt加粗。")
            _assert(controls[key].font.pointSize == 16, "参数分组标题字号未写入到Qt字体。")
            _assert(controls[key].font.bold, "参数分组标题未写入粗体Qt字体。")
    for key in ("selection_group", "preview_group"):
        style = str(empty_user_page[key].styleSheet).replace(" ", "").lower()
        _assert("font-size:16pt" in style and "font-weight:bold" in style, "用户页分组标题样式不是16pt加粗。")
        _assert(empty_user_page[key].font.pointSize == 16, "用户页分组标题字号未写入到Qt字体。")
        _assert(empty_user_page[key].font.bold, "用户页分组标题未写入粗体Qt字体。")
    default_edit = pya.QLineEdit(parent)
    default_label = pya.QLabel(parent)
    default_button = pya.QPushButton(parent)
    default_combo = pya.QComboBox(parent)
    default_plain_text = pya.QPlainTextEdit(parent)
    for controls, keys in (
        (single, ("bend_type_label", "width_label", "width", "radius_label", "radius", "npoints_label", "npoints", "save_button")),
        (composite, ("straight_width_label", "straight_width", "bend_width_label", "bend_width", "start_width_role_label", "end_width_role_label", "taper_length_label", "transition_length_label")),
    ):
        for key in keys:
            widget = controls[key]
            reference = default_button if key == "save_button" else default_edit if isinstance(widget, pya.QLineEdit) else default_label
            _assert(widget.font.pointSize == reference.font.pointSize, "%s 字号继承了分组标题。" % key)
            _assert(widget.font.bold == reference.font.bold, "%s 错误继承了分组粗体。" % key)
    for key, reference in (
        ("combo_label", default_label),
        ("combo", default_combo),
        ("manage_button", default_button),
        ("empty_label", default_label),
        ("preset_name_label", default_label),
        ("preset_name", default_edit),
        ("note_edit", default_plain_text),
    ):
        widget = empty_user_page[key]
        _assert(widget.font.pointSize == reference.font.pointSize, "%s 字号继承了用户页分组标题。" % key)
        _assert(widget.font.bold == reference.font.bold, "%s 错误继承了用户页分组粗体。" % key)
    _assert(empty_user_page["note_group"].font.pointSize != 16 or not empty_user_page["note_group"].font.bold, "Note 标题被错误设置为16pt加粗。")
    _assert(single["layout"].count() == 2 and composite["layout"].count() == 2, "基础页不是双栏布局。")
    _assert(single["npoints"].isReadOnly(), "单宽度派生参数仍可编辑。")
    _assert(composite["Bezier_Rmax"].isReadOnly(), "复合波导派生参数仍可编辑。")
    _assert(single["save_button"].text == "Save as User-Defined", "单宽度保存按钮文字错误。")
    _assert(composite["save_button"].text == "Save as User-Defined", "复合波导保存按钮文字错误。")
    _assert(path_tool.TAB_LABELS == {
        path_tool.TAB_SINGLE: "Single-Width Waveguide",
        path_tool.TAB_COMPOSITE: "Composite-Width Waveguide",
        path_tool.TAB_USER_DEFINED: "User-Defined",
    }, "英文页签名称错误。")

    settings, single_preset, _created = path_tool._add_user_preset(
        settings, path_tool.TAB_SINGLE, settings["single"],
    )
    user_page = path_tool._build_user_defined_page(parent)
    path_tool._refresh_user_defined_page(user_page, settings, 0.001)
    _assert(user_page["mode"].text == "Single-Width Waveguide", "用户页未显示单宽度模式。")
    _assert(user_page["width"].text == "0.500", "用户页未显示单宽度数值。")
    _assert(user_page["note_edit"].isEnabled(), "存在预设时 Note 未启用。")
    _assert(str(_qt_value(user_page["note_edit"], "toPlainText")) == "", "新预设 Note 默认值错误。")
    settings, found = path_tool._update_user_preset_note(
        settings, single_preset["id"], "GUI Note\nLine 2",
    )
    _assert(found, "GUI Note 测试未找到预设。")
    path_tool._refresh_user_defined_page(user_page, settings, 0.001)
    _assert(str(_qt_value(user_page["note_edit"], "toPlainText")) == "GUI Note\nLine 2", "User-Defined 未显示对应 Note。")

    euler_values = dict(settings["single"])
    euler_values.update({"bend_type": "Euler", "Euler_Rmax": 60.0, "Euler_Rmin": 20.0})
    settings, euler_preset, _created = path_tool._add_user_preset(
        settings, path_tool.TAB_SINGLE, euler_values,
    )
    settings["user_defined"]["selected_id"] = euler_preset["id"]
    path_tool._refresh_user_defined_page(user_page, settings, 0.001)
    _assert(user_page["Euler_Rmax"].text == "60.000", "用户页未显示 Euler Rmax。")
    _assert(not user_page["Euler_Reff"].isHidden(), "用户页未显示 Euler Reff。")
    _assert(user_page["radius"].isHidden(), "Euler 用户预设仍显示普通半径。")

    settings, composite_preset, _created = path_tool._add_user_preset(
        settings, path_tool.TAB_COMPOSITE, settings["composite"],
    )
    settings["user_defined"]["selected_id"] = composite_preset["id"]
    path_tool._refresh_user_defined_page(user_page, settings, 0.001)
    _assert(user_page["mode"].text == "Composite-Width Waveguide", "用户页未显示复合模式。")
    _assert(user_page["straight_width"].text == "2.000", "用户页未显示复合直宽。")
    _assert(not user_page["preset_name"].isReadOnly(), "Preset Name 仍不可编辑。")
    for key in (
        "mode", "straight_width", "bend_width", "start_width_role",
        "end_width_role", "taper_length", "transition_length", "bend_type", "radius",
        "bezier", "npoints", "Bezier_Rmax", "Bezier_Rmin",
    ):
        _assert(user_page[key].isReadOnly(), "用户页字段仍可编辑：%s" % key)

    def active_dialog():
        application = pya.QApplication.instance()
        widget = application.activeModalWidget
        if callable(widget):
            widget = widget()
        if widget is None:
            raise RuntimeError("未找到活动模态窗口。")
        return widget

    def close_active_dialog(accept):
        widget = active_dialog()
        widget.accept() if accept else widget.reject()

    def find_child(widget, child_type, name):
        child = widget.findChild(name)
        if child is None:
            raise RuntimeError("未找到 GUI 控件：%s" % name)
        return child

    original_path = path_tool._waveguide_params_file
    original_message = path_tool._message
    original_gui_state_file = gui_state._gui_state_file
    with tempfile.TemporaryDirectory(prefix="jnu_waveguide_dialog_") as directory:
        filepath = os.path.join(directory, "jnu_waveguide_params.json")
        gui_filepath = os.path.join(directory, "jnu_gui_state.json")
        path_tool._waveguide_params_file = lambda: filepath
        gui_state._gui_state_file = lambda: gui_filepath
        messages = []
        callback_errors = []
        try:
            path_tool._message = lambda title, text: messages.append((title, text))

            def save_single_and_close():
                dialog = active_dialog()
                try:
                    find_child(
                        dialog, pya.QPushButton, "jnu_save_single_preset",
                    ).click()
                except Exception as error:
                    callback_errors.append(str(error))
                finally:
                    dialog.reject()

            path_tool._save_waveguide_params(path_tool._default_waveguide_params())
            save_timer = pya.QTimer(parent)
            save_timer.setSingleShot(True)
            save_timer.timeout(save_single_and_close)
            save_timer.start(0)
            path_tool._show_waveguide_dialog(0.001)
            _assert(not callback_errors, "Save 按钮 GUI 回调失败：%s" % callback_errors)
            _assert(messages and "保存成功" in messages[-1][1], "新预设保存后未提示成功。")

            messages[:] = []
            duplicate_timer = pya.QTimer(parent)
            duplicate_timer.setSingleShot(True)
            duplicate_timer.timeout(save_single_and_close)
            duplicate_timer.start(0)
            path_tool._show_waveguide_dialog(0.001)
            _assert(messages and "已存在" in messages[-1][1], "重复预设保存后未提示已存在。")

            settings["active_tab"] = path_tool.TAB_USER_DEFINED
            path_tool._save_waveguide_params(settings)

            def rename_preset_and_close():
                dialog = active_dialog()
                try:
                    tabs_widget = find_child(
                        dialog, pya.QTabWidget, "jnu_path_to_waveguide_tabs",
                    )
                    _assert(tabs_widget.tabText(0) == "User-Defined", "User-Defined 不是第一个页签。")
                    name_edit = find_child(
                        dialog, pya.QLineEdit, "jnu_user_defined_preset_name",
                    )
                    combo = find_child(
                        dialog, pya.QComboBox, "jnu_user_defined_preset_combo",
                    )
                    name_edit.setText("常用复合波导")
                    _assert(
                        str(_qt_value(combo, "currentText")) == "常用复合波导",
                        "下拉框名称未随输入实时更新。",
                    )
                except Exception as error:
                    callback_errors.append(str(error))
                finally:
                    dialog.reject()

            rename_timer = pya.QTimer(parent)
            rename_timer.setSingleShot(True)
            rename_timer.timeout(rename_preset_and_close)
            rename_timer.start(0)
            _assert(path_tool._show_waveguide_dialog(0.001) is None, "Preset Name 编辑后未关闭。")
            reloaded = path_tool._load_waveguide_params()
            renamed = path_tool._selected_user_preset(reloaded)
            _assert(renamed["name"] == "常用复合波导", "Preset Name 未持久化。")

            def edit_note(text, close_after_edit=False):
                dialog = active_dialog()
                try:
                    find_child(
                        dialog, pya.QPlainTextEdit, "jnu_user_defined_note",
                    ).setPlainText(text)
                except Exception as error:
                    callback_errors.append(str(error))
                if close_after_edit:
                    dialog.reject()

            debounce_edit_timer = pya.QTimer(parent)
            debounce_edit_timer.setSingleShot(True)
            debounce_edit_timer.timeout(lambda: edit_note("防抖保存\n第二行"))
            debounce_close_timer = pya.QTimer(parent)
            debounce_close_timer.setSingleShot(True)
            debounce_close_timer.timeout(lambda: close_active_dialog(False))
            debounce_edit_timer.start(0)
            debounce_close_timer.start(700)
            _assert(path_tool._show_waveguide_dialog(0.001) is None, "主参数窗口 Cancel 未退出。")
            reloaded = path_tool._load_waveguide_params()
            selected = path_tool._selected_user_preset(reloaded)
            _assert(selected["note"] == "防抖保存\n第二行", "Note 500 ms 防抖未自动保存。")

            forced_timer = pya.QTimer(parent)
            forced_timer.setSingleShot(True)
            forced_timer.timeout(lambda: edit_note("关闭前强制保存", True))
            forced_timer.start(0)
            _assert(path_tool._show_waveguide_dialog(0.001) is None, "主参数窗口关闭失败。")
            reloaded = path_tool._load_waveguide_params()
            _assert(
                path_tool._selected_user_preset(reloaded)["note"] == "关闭前强制保存",
                "窗口关闭前未强制保存 Note。",
            )

            generate_timer = pya.QTimer(parent)
            generate_timer.setSingleShot(True)
            generate_timer.timeout(lambda: close_active_dialog(True))
            generate_timer.start(0)
            generated = path_tool._show_waveguide_dialog(0.001)
            _assert(generated is not None and generated["mode"] == path_tool.TAB_COMPOSITE, "用户预设 OK 未返回复合参数。")
            _assert(generated["straight_width"] == 2.0 and generated["bend_width"] == 0.5, "用户预设生成参数发生变化。")

            def edit_all_pages_and_close():
                dialog = active_dialog()
                try:
                    tabs_widget = find_child(
                        dialog, pya.QTabWidget, "jnu_path_to_waveguide_tabs",
                    )
                    find_child(dialog, pya.QLineEdit, "jnu_single_width").setText("0.610")
                    find_child(
                        dialog, pya.QLineEdit, "jnu_composite_straight_width",
                    ).setText("2.400")
                    tabs_widget.setCurrentIndex(2)
                    dialog.resize(1180, 700)
                except Exception as error:
                    callback_errors.append(str(error))
                finally:
                    dialog.reject()

            persist_timer = pya.QTimer(parent)
            persist_timer.setSingleShot(True)
            persist_timer.timeout(edit_all_pages_and_close)
            persist_timer.start(0)
            _assert(path_tool._show_waveguide_dialog(0.001) is None, "全页设置持久化窗口未关闭。")
            reloaded = path_tool._load_waveguide_params()
            _assert(reloaded["single"]["width"] == 0.61, "Single 页设置未持久化。")
            _assert(reloaded["composite"]["straight_width"] == 2.4, "Composite 页设置未持久化。")
            _assert(reloaded["active_tab"] == path_tool.TAB_COMPOSITE, "当前页签未持久化。")

            def verify_restored_tab_and_close():
                dialog = active_dialog()
                try:
                    tabs_widget = find_child(
                        dialog, pya.QTabWidget, "jnu_path_to_waveguide_tabs",
                    )
                    _assert(int(_qt_value(tabs_widget, "currentIndex")) == 2, "重开后未恢复 Composite 页签。")
                    actual_width = int(_qt_value(dialog, "width"))
                    actual_height = int(_qt_value(dialog, "height"))
                    _assert(actual_width == 1187, "Path to Waveguide 初始宽度错误：%d。" % actual_width)
                    _assert(actual_height == 541, "Path to Waveguide 初始高度错误：%d。" % actual_height)
                except Exception as error:
                    callback_errors.append(str(error))
                finally:
                    dialog.reject()

            restore_timer = pya.QTimer(parent)
            restore_timer.setSingleShot(True)
            restore_timer.timeout(verify_restored_tab_and_close)
            restore_timer.start(50)
            path_tool._show_waveguide_dialog(0.001)
            _assert(not callback_errors, "Note GUI 回调失败：%s" % callback_errors)
        finally:
            path_tool._waveguide_params_file = original_path
            path_tool._message = original_message
            gui_state._gui_state_file = original_gui_state_file

    accept_timer = pya.QTimer(parent)
    accept_timer.setSingleShot(True)
    accept_timer.timeout(lambda: close_active_dialog(True))
    accept_timer.start(0)
    staged = path_tool._show_manage_presets_dialog(parent, settings["user_defined"]["presets"])
    _assert(staged is not None and len(staged) == 3, "预设管理窗口未返回暂存列表。")


def main():
    _check_defaults_and_result_conversion()
    _check_preset_naming_deduplication_and_deletion()
    _check_json_migration_and_atomic_persistence()
    _check_qt_pages_when_available()
    print("Path to Waveguide presets regression: PASS")


if __name__ == "__main__":
    main()
