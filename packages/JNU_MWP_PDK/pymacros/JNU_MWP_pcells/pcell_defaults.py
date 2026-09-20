# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-06

"""JNU PCell 默认参数持久化工具。

默认值会写入用户 KLayout 根目录，保存后同时刷新当前 PCell 声明对象的默认值。
这样同一 KLayout 会话内再次从 Library 拖出器件时，也能看到上一次修改后的参数。
"""

import json
import os
from pathlib import Path

try:
    import pya
except Exception:  # pragma: no cover - 仅用于非 KLayout 环境语法检查
    pya = None


DEFAULTS_FILENAME = "jnu_pcell_defaults.json"
REGISTERED_LIBRARY_NAMES = ("JNULib", "JNULib_BlackBox")


def _user_klayout_root():
    """返回当前用户的 KLayout 根目录。"""

    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        return Path(userprofile) / "KLayout"
    return Path.home() / "KLayout"


def _defaults_path():
    """返回新的默认参数文件路径。"""

    return _user_klayout_root() / DEFAULTS_FILENAME


def _legacy_defaults_path():
    """返回旧版本默认参数文件路径，用于兼容读取。"""

    return Path(os.path.expanduser("~")) / ".klayout" / DEFAULTS_FILENAME


def _read_json(path):
    """读取 JSON 文件，失败时返回空字典。"""

    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _read_defaults():
    """读取所有 PCell 默认参数；新路径优先，旧路径作为兼容回退。"""

    data = _read_json(_defaults_path())
    if data:
        return data
    return _read_json(_legacy_defaults_path())


def _write_defaults(data):
    """原子写入默认参数 JSON。"""

    path = _defaults_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = Path(str(path) + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(str(temp_path), str(path))


def load_pcell_defaults(pcell_name):
    """兼容旧接口：始终返回空字典。"""
    return {}


def _raw_default(pcell_name, parameter_name, fallback):
    """兼容旧接口：始终返回 fallback。"""
    return fallback


def default_float(pcell_name, parameter_name, fallback):
    """始终返回内置默认值。PCell 参数持久化已取消。"""
    return float(fallback)


def default_int(pcell_name, parameter_name, fallback):
    """始终返回内置默认值。PCell 参数持久化已取消。"""
    return int(fallback)


def default_bool(pcell_name, parameter_name, fallback):
    """始终返回内置默认值。PCell 参数持久化已取消。"""
    return bool(fallback)


def default_choice(pcell_name, parameter_name, fallback, allowed_values):
    """始终返回内置默认值。PCell 参数持久化已取消。"""
    return str(fallback)


def _call_or_value(obj, attr_name, fallback=0):
    """兼容 KLayout 属性在不同版本中可能是方法或属性的情况。"""
    try:
        attr = getattr(obj, attr_name)
        return attr() if callable(attr) else attr
    except Exception:
        return fallback


def _layer_info_to_dict(value):
    """把 LayerInfo 序列化为 JSON 字典。"""
    if pya is None:
        return None
    try:
        return {
            "type": "LayerInfo",
            "layer": int(_call_or_value(value, "layer", 0)),
            "datatype": int(_call_or_value(value, "datatype", 0)),
        }
    except Exception:
        return None


def _layer_info_from_value(value, fallback):
    """从 JSON 值、字符串或 LayerInfo 还原图层信息。"""
    if pya is None:
        return fallback
    if isinstance(value, dict):
        try:
            return pya.LayerInfo(int(value.get("layer", 0)), int(value.get("datatype", 0)))
        except Exception:
            return fallback
    if hasattr(value, "layer") and hasattr(value, "datatype"):
        return value
    if isinstance(value, str) and "/" in value:
        try:
            layer, datatype = value.split("/", 1)
            return pya.LayerInfo(int(layer), int(datatype))
        except Exception:
            return fallback
    return fallback


def default_layer_info(pcell_name, parameter_name, fallback):
    """始终返回内置默认值。PCell 参数持久化已取消。"""
    return _layer_info_from_value(fallback, fallback)


def _serialize_value(value):
    """把 PCell 参数值转成 JSON 友好格式。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        return value
    if hasattr(value, "layer") and hasattr(value, "datatype"):
        return _layer_info_to_dict(value)
    return None


def _declaration_name(declaration):
    """读取 PCellParameterDeclaration 的参数名。"""

    try:
        name = declaration.name
        return name() if callable(name) else name
    except Exception:
        return ""


def _default_value_for_declaration(value):
    """把 JSON 存储值转换成 declaration.default 可接受的对象。"""

    if isinstance(value, dict) and value.get("type") == "LayerInfo":
        return _layer_info_from_value(value, None)
    return value


def _sync_declaration_defaults(pcell, pcell_defaults):
    """保存后同步刷新当前 PCell 声明默认值。"""

    try:
        declarations = pcell.get_parameters()
    except Exception:
        return

    for declaration in declarations:
        name = _declaration_name(declaration)
        if name not in pcell_defaults:
            continue
        value = _default_value_for_declaration(pcell_defaults[name])
        if value is None:
            continue
        try:
            declaration.default = value
        except Exception:
            pass


def _sync_one_declaration_defaults(declaration, pcell_defaults):
    """把一份 PCell declaration 的参数默认值同步到保存值。"""

    try:
        parameters = declaration.get_parameters()
    except Exception:
        return

    for parameter in parameters:
        name = _declaration_name(parameter)
        if name not in pcell_defaults:
            continue
        value = _default_value_for_declaration(pcell_defaults[name])
        if value is None:
            continue
        try:
            parameter.default = value
        except Exception:
            pass


def _sync_registered_library_defaults(pcell_name, pcell_defaults):
    """同步已注册 JNU 器件库，避免 Library 面板继续使用旧默认值。"""

    if pya is None:
        return

    for library_name in REGISTERED_LIBRARY_NAMES:
        try:
            library = pya.Library.library_by_name(library_name)
        except Exception:
            library = None
        if library is None:
            continue

        try:
            layout = library.layout()
            pcell_ids = list(layout.pcell_ids())
        except Exception:
            continue

        for pcell_id in pcell_ids:
            try:
                declaration = layout.pcell_declaration(pcell_id)
                name = declaration.name() if callable(declaration.name) else declaration.name
            except Exception:
                continue
            if name == pcell_name:
                _sync_one_declaration_defaults(declaration, pcell_defaults)


def save_pcell_defaults(pcell, pcell_name, parameter_names):
    """空操作。PCell 参数持久化已取消，新建实例始终使用代码内置默认值。"""
    pass


def _state_value(state):
    """读取 PCellParameterState 当前值，兼容属性和方法两种形式。"""

    try:
        value = state.value
        return value() if callable(value) else value
    except Exception:
        return state


def _set_state_value(state, value):
    """写入 PCellParameterState 的 value，不同 KLayout 版本失败时静默跳过。"""

    try:
        state.value = value
        return True
    except Exception:
        return False


def _values_match(left, right):
    """宽松比较 GUI state 当前值与内置默认值。"""

    if isinstance(left, (int, float)) or isinstance(right, (int, float)):
        try:
            return abs(float(left) - float(right)) <= 1e-12
        except Exception:
            return False
    return str(left) == str(right)


def _migrate_legacy_sample_default(parameter_name, saved_value, builtin_value):
    """把旧版采样点数默认 1000 迁移为 0=Auto。"""

    if parameter_name not in ("points_per_90", "npoints"):
        return saved_value
    try:
        if int(saved_value) == 1000 and int(builtin_value) == 0:
            return 0
    except Exception:
        pass
    return saved_value


def apply_saved_defaults_to_states(pcell, pcell_name, parameter_names, builtin_defaults):
    """空操作。PCell 参数持久化已取消，新建实例始终使用代码内置默认值。"""
    pass
