# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""保存并恢复 JNU 自定义对话框的用户尺寸。"""

import json
import os
import tempfile

import pya


CONFIG_PREFIX = "jnu_mwp_pdk.dialog_size."
MIN_WIDTH = 100
MIN_HEIGHT = 80
MAX_DIMENSION = 32767
STATE_SCHEMA_VERSION = 1


def _value(obj, name):
    value = getattr(obj, name)
    return value() if callable(value) else value


def _application(app=None):
    if app is not None:
        return app
    return pya.Application.instance()


def _gui_state_file():
    directory = os.path.join(os.path.expanduser("~"), ".klayout")
    return os.path.join(directory, "jnu_gui_state.json")


def _load_file_sizes():
    try:
        with open(_gui_state_file(), "r", encoding="utf-8") as stream:
            data = json.load(stream)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    sizes = data.get("dialog_sizes", {})
    return sizes if isinstance(sizes, dict) else {}


def _save_file_sizes(sizes):
    filepath = _gui_state_file()
    directory = os.path.dirname(filepath)
    os.makedirs(directory, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False, dir=directory,
            prefix=".jnu_gui_state_", suffix=".tmp",
        ) as stream:
            temporary = stream.name
            json.dump(
                {"schema_version": STATE_SCHEMA_VERSION, "dialog_sizes": sizes},
                stream, indent=2, ensure_ascii=False,
            )
        os.replace(temporary, filepath)
        temporary = None
        return True
    finally:
        if temporary and os.path.exists(temporary):
            try:
                os.remove(temporary)
            except Exception:
                pass


def parse_dialog_size(value):
    """把配置字符串转换为经过边界校验的 ``(width, height)``。"""
    try:
        parts = value if isinstance(value, (list, tuple)) else str(value).strip().split(",")
        if len(parts) != 2:
            return None
        width, height = int(parts[0]), int(parts[1])
    except Exception:
        return None
    if not (MIN_WIDTH <= width <= MAX_DIMENSION):
        return None
    if not (MIN_HEIGHT <= height <= MAX_DIMENSION):
        return None
    return width, height


def restore_dialog_size(dialog, dialog_key, default_size=None, app=None):
    """优先恢复已保存尺寸；没有有效记录时应用功能自己的默认尺寸。"""
    key = str(dialog_key)
    size = parse_dialog_size(_load_file_sizes().get(key, ""))
    application = _application(app)
    if size is None and application is not None:
        try:
            size = parse_dialog_size(
                application.get_config(CONFIG_PREFIX + key)
            )
        except Exception:
            size = None
    if size is None and default_size is not None:
        size = parse_dialog_size("%s,%s" % tuple(default_size))
    if size is not None:
        dialog.resize(size[0], size[1])
    return size


def save_dialog_size(dialog, dialog_key, app=None):
    """保存对话框关闭前的实际尺寸，供下次打开和 KLayout 重启后恢复。"""
    try:
        size = parse_dialog_size(
            "%s,%s" % (_value(dialog, "width"), _value(dialog, "height"))
        )
    except Exception:
        size = None
    application = _application(app)
    if size is None:
        return False
    key = str(dialog_key)
    file_saved = False
    try:
        sizes = _load_file_sizes()
        sizes[key] = [size[0], size[1]]
        file_saved = _save_file_sizes(sizes)
    except Exception:
        file_saved = False
    config_saved = False
    if application is not None:
        try:
            application.set_config(CONFIG_PREFIX + key, "%d,%d" % size)
            config_saved = True
        except Exception:
            config_saved = False
    return file_saved or config_saved


def exec_dialog_with_persisted_size(
    dialog, dialog_key, default_size=None, app=None,
):
    """执行模态对话框，并在 OK、Cancel 或标题栏关闭后保存尺寸。"""
    restore_dialog_size(dialog, dialog_key, default_size, app)
    try:
        return dialog.exec_()
    finally:
        save_dialog_size(dialog, dialog_key, app)


__all__ = [
    "CONFIG_PREFIX",
    "_gui_state_file",
    "parse_dialog_size",
    "restore_dialog_size",
    "save_dialog_size",
    "exec_dialog_with_persisted_size",
]
