# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

# JNU_MWP_PDK Path to Waveguide 功能。
# 读取选中的 Si/Waveguide 层 Path，完成参数设置、端点吸附和波导 cell 创建。

import os
import sys
import json
import math
import copy
import hashlib
import tempfile

import pya

try:
    from JNU_MWP_tools.core.bend_sampling import points_per_90
except Exception:
    points_per_90 = None

try:
    from JNU_MWP_tools.core.bend_curvature import bezier_Rmax_Rmin, euler_Reff
except Exception:
    bezier_Rmax_Rmin = None
    euler_Reff = None

from JNU_MWP_tools.core.common import (
    RAW_PATH_GDS_PROPERTY,
    RAW_PATH_PROPERTY,
    SI_LAYER,
    WG_LAYER,
    WAVEGUIDE_CONTAINER_GDS_PROPERTY,
    WAVEGUIDE_CONTAINER_PREFIX,
    WAVEGUIDE_CONTAINER_PROPERTY,
    WAVEGUIDE_KIND_GDS_PROPERTY,
    WAVEGUIDE_KIND_PROPERTY,
    _PIN_SNAP_DISTANCE_UM,
    _active_context,
    _angle_vector,
    _debug_log,
    _dedupe_path_points,
    _find_pins_in_cell,
    _main_window,
    _message,
    _value,
)
from JNU_MWP_tools.core.gui_state import (
    exec_dialog_with_persisted_size,
)


JNULIB_NAME = "JNULib"
INTERNAL_WAVEGUIDE_PCELL_NAMES = ("Waveguide", "Composite_Waveguide")
PARAM_SCHEMA_VERSION = 3
TAB_SINGLE = "single"
TAB_COMPOSITE = "composite"
TAB_USER_DEFINED = "user_defined"
TAB_LABELS = {
    TAB_SINGLE: "Single-Width Waveguide",
    TAB_COMPOSITE: "Composite-Width Waveguide",
    TAB_USER_DEFINED: "User-Defined",
}
SINGLE_EDITABLE_KEYS = (
    "width", "radius", "bend_type", "bezier", "Euler_Rmax", "Euler_Rmin",
)
COMPOSITE_EDITABLE_KEYS = (
    "straight_width", "bend_width", "start_width_role", "end_width_role",
    "taper_length", "transition_length", "radius", "bend_type", "bezier",
    "Euler_Rmax", "Euler_Rmin",
)


def _dpath_extension_um(dpath, attribute):
    """读取 DPath 的端部延伸；未设置时返回零。"""
    try:
        value = getattr(dpath, attribute)
        return float(value() if callable(value) else value)
    except Exception:
        return 0.0


def _store_waveguide_recovery_property(cell, dpath, extra=None):
    """在 PCell variant 上保存 GDS 展平后的无图形恢复数据。"""
    data = {
        "width_um": float(dpath.width),
        "points_um": [[float(point.x), float(point.y)] for point in dpath.each_point()],
        "bgn_ext_um": _dpath_extension_um(dpath, "bgn_ext"),
        "end_ext_um": _dpath_extension_um(dpath, "end_ext"),
    }
    if isinstance(extra, dict):
        data.update(extra)
    value = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    cell.set_property(RAW_PATH_PROPERTY, value)
    # GDSII 的 PROPATTR 只接受数字属性号；该镜像保证命名属性可跨 GDS 重读。
    cell.set_property(RAW_PATH_GDS_PROPERTY, value)


def _set_gds_mirrored_property(target, property_name, gds_property, value):
    """写入命名属性及其 GDS 数字镜像，保证重开文件后仍可读取。"""
    target.set_property(property_name, value)
    target.set_property(gds_property, value)


def _mark_waveguide(target, waveguide_kind):
    """标记单宽度或复合宽度内部波导，不依赖 cell 名称识别。"""
    _set_gds_mirrored_property(
        target, WAVEGUIDE_KIND_PROPERTY, WAVEGUIDE_KIND_GDS_PROPERTY,
        str(waveguide_kind),
    )


def _mark_waveguide_container(cell):
    """标记仅用于收纳 Path to Waveguide 实例的层级容器。"""
    _set_gds_mirrored_property(
        cell, WAVEGUIDE_CONTAINER_PROPERTY, WAVEGUIDE_CONTAINER_GDS_PROPERTY,
        "v1",
    )


def _normalize_dpath_to_origin(dpath, dbu):
    """将输入 DPath 平移到首点原点，并返回恢复原位置的整数平移。"""
    points = list(dpath.each_point())
    if len(points) < 2:
        return None, None

    origin = points[0]
    local_points = [pya.DPoint(point.x - origin.x, point.y - origin.y) for point in points]
    local_dpath = pya.DPath(
        local_points,
        float(dpath.width),
        _dpath_extension_um(dpath, "bgn_ext"),
        _dpath_extension_um(dpath, "end_ext"),
    )
    placement = pya.Trans(
        pya.Trans.R0,
        int(round(origin.x / dbu)),
        int(round(origin.y / dbu)),
    )
    return local_dpath, placement


def _signature_number(value):
    """把数值规范化为跨会话稳定的签名字符串。"""
    return format(float(value), ".12g")


def _waveguide_variant_signature(dpath, params, dbu):
    """以局部路径和实际 PCell 参数生成稳定的内部 variant 身份。"""
    points = [
        [int(round(point.x / dbu)), int(round(point.y / dbu))]
        for point in dpath.each_point()
    ]
    if params.get("mode") == "composite":
        parameter_keys = (
            "straight_width", "start_width", "end_width", "bend_width",
            "taper_length", "transition_length", "radius", "bezier",
            "Euler_Rmax", "Euler_Rmin",
        )
        kind = "composite"
    else:
        parameter_keys = ("width", "radius", "bezier", "Euler_Rmax", "Euler_Rmin")
        kind = "single"
    payload = {
        "kind": kind,
        "bend_type": str(params["bend_type"]),
        "path": points,
        "path_width_dbu": int(round(float(dpath.width) / dbu)),
        "bgn_ext_dbu": int(round(_dpath_extension_um(dpath, "bgn_ext") / dbu)),
        "end_ext_dbu": int(round(_dpath_extension_um(dpath, "end_ext") / dbu)),
        "parameters": {
            key: _signature_number(params.get(key, 0.0))
            for key in parameter_keys
        },
    }
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return kind, hashlib.sha256(encoded.encode("ascii")).hexdigest()[:20]


def _stable_waveguide_cell_name(layout, waveguide_cell, waveguide_kind, signature):
    """返回不会依赖 KLayout 自动 $ 序号的 GDS-safe 内部 cell 名称。"""
    mode = "C" if waveguide_kind == "composite" else "S"
    base_name = "JNU_WG_%s_%s" % (mode, signature)
    existing = layout.cell(base_name)
    if existing is None or existing.cell_index() == waveguide_cell.cell_index():
        return base_name
    return _safe_cell_name(layout, base_name, waveguide_cell)


def _container_base_name(parent_cell):
    """为每个父 cell 生成稳定、短小且可折叠的内部容器名称。"""
    source = "%s:%d" % (parent_cell.name, parent_cell.cell_index())
    return WAVEGUIDE_CONTAINER_PREFIX + hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def _property_equals(target, property_name, gds_property, expected):
    """读取命名属性或 GDS 数字镜像并比较标记值。"""
    for key in (property_name, gds_property):
        try:
            value = target.property(key)
        except Exception:
            value = None
        if str(value) == str(expected):
            return True
    return False


def _is_waveguide_container_cell(cell):
    """判断 cell 是否为本工具创建的波导容器。"""
    if cell is None:
        return False
    if _property_equals(
        cell, WAVEGUIDE_CONTAINER_PROPERTY,
        WAVEGUIDE_CONTAINER_GDS_PROPERTY, "v1",
    ):
        return True
    try:
        return str(cell.name).startswith(WAVEGUIDE_CONTAINER_PREFIX)
    except Exception:
        return False


def _find_waveguide_container(parent_cell):
    """在父 cell 的直接实例中查找已存在的内部波导容器。"""
    for instance in parent_cell.each_inst():
        try:
            if _is_waveguide_container_cell(instance.cell):
                return instance, instance.cell
        except Exception:
            continue
    return None, None


def _get_or_create_waveguide_container(layout, parent_cell):
    """复用父 cell 的容器；首次转换时建立一个空容器。"""
    instance, container = _find_waveguide_container(parent_cell)
    if container is not None:
        return container, instance, False

    container = layout.create_cell(_safe_cell_name(layout, _container_base_name(parent_cell)))
    _mark_waveguide_container(container)
    return container, None, True


def _delete_empty_new_waveguide_container(layout, container, was_created):
    """失败或无转换结果时清理由本轮新建且未被引用的容器。"""
    if not was_created or container is None:
        return
    try:
        if any(True for _instance in container.each_parent_inst()):
            return
        if any(True for _instance in container.each_inst()):
            return
        if not container.bbox().empty():
            return
        layout.delete_cell(container.cell_index())
    except Exception:
        pass


def _path_to_dpath(path, dbu, width_um):
    clean_points = []
    for point in path.each_point():
        if not clean_points or clean_points[-1] != point:
            clean_points.append(point)
    if len(clean_points) < 2:
        return None
    dpoints = [pya.DPoint(point.x * dbu, point.y * dbu) for point in clean_points]
    return pya.DPath(
        dpoints,
        width_um,
        float(path.bgn_ext) * dbu,
        float(path.end_ext) * dbu,
    )


def _snap_path_to_pins(path, pins, dbu):
    if not pins:
        return False

    points = _dedupe_path_points(list(path.each_point()))
    if len(points) < 2:
        return False

    snap_distance = int(round(_PIN_SNAP_DISTANCE_UM / dbu))
    snapped = False

    def snap_one_endpoint(endpoint_index, neighbor_index):
        nonlocal snapped
        endpoint = points[endpoint_index]
        neighbor = points[neighbor_index]
        angle = _angle_vector(endpoint - neighbor)

        candidates = [
            pin
            for pin in pins
            if round((angle - pin.rotation) % 360) == 180
        ]
        if not candidates:
            return

        pin = min(candidates, key=lambda item: item.center.distance(endpoint))
        delta = pin.center - endpoint
        if delta.abs() > snap_distance:
            return

        points[endpoint_index] = endpoint + delta
        if round(angle % 180) == 0:
            points[neighbor_index] = pya.Point(
                points[neighbor_index].x,
                points[neighbor_index].y + delta.y,
            )
        else:
            points[neighbor_index] = pya.Point(
                points[neighbor_index].x + delta.x,
                points[neighbor_index].y,
            )
        snapped = True

    snap_one_endpoint(0, 1)
    snap_one_endpoint(-1, -2)

    if snapped:
        path.points = _dedupe_path_points(points)

    return snapped


def _waveguide_params_file():
    home = os.path.expanduser("~")
    klayout_dir = os.path.join(home, ".klayout")
    if not os.path.isdir(klayout_dir):
        os.makedirs(klayout_dir, exist_ok=True)
    return os.path.join(klayout_dir, "jnu_waveguide_params.json")


def _normalize_bend_type(value):
    """把旧版 normal 名称迁移为 Circular，同时保留 Bezier/Euler。"""

    text = str(value).strip().lower()
    if text == "bezier":
        return "Bezier"
    if text == "euler":
        return "Euler"
    return "Circular"


def _normalize_width_role(role, width_value, straight_width, bend_width):
    """把端部宽度迁移为下拉角色；旧数值按离直宽/弯宽更近者归类。"""
    text = str(role).strip().lower()
    if text in ("straight", "bend"):
        return text
    try:
        width = float(width_value)
        straight = float(straight_width)
        bend = float(bend_width)
    except Exception:
        return "straight"
    if abs(width - bend) < abs(width - straight):
        return "bend"
    return "straight"


def _adaptive_npoints(radius_um, dbu=0.001):
    """按当前弯曲半径计算 GUI 中显示的自适应采样点数。"""

    if points_per_90 is not None:
        return points_per_90(radius_um, dbu)
    return 112


def _calculate_waveguide_derived(radius, bend_type, bezier, euler_rmax, euler_rmin, dbu=0.001):
    """纯计算 GUI 派生值，供实时刷新、OK 校验和命名共同使用。"""
    bend_type = _normalize_bend_type(bend_type)
    result = {
        "Bezier_Rmax": None,
        "Bezier_Rmin": None,
        "Euler_Reff": None,
        "effective_radius": None,
        "npoints": None,
    }
    if bend_type in ("Circular", "Bezier"):
        radius = float(radius)
        if radius <= 0.010:
            raise ValueError("弯曲半径必须大于 0.010 um。")
        result["effective_radius"] = radius
        if bend_type == "Bezier":
            bezier = float(bezier)
            if bezier <= 0:
                raise ValueError("Bezier 值必须大于 0。")
            result["Bezier_Rmax"], result["Bezier_Rmin"] = bezier_Rmax_Rmin(radius, bezier)
    else:
        euler_rmax = float(euler_rmax)
        euler_rmin = float(euler_rmin)
        if not (euler_rmax > euler_rmin > 0.0):
            raise ValueError("Euler Rmin 必须大于 0 且小于 Euler Rmax。")
        result["Euler_Reff"] = euler_Reff(euler_rmax, euler_rmin)
        result["effective_radius"] = result["Euler_Reff"]

    result["npoints"] = int(_adaptive_npoints(result["effective_radius"], dbu))
    return result


def _build_waveguide_cell_base_name(params):
    """根据最终校验参数构造 Waveguide cell 基础名称，不包含长度和重名后缀。"""
    width_nm = int(round(float(params["width"]) * 1000.0))
    bend_type = _normalize_bend_type(params["bend_type"])
    if bend_type == "Bezier":
        return (
            "Waveguide_width(%d)_Bezier_R%.3f_B%.3f_Rmax%.3f_Rmin%.3f"
            % (
                width_nm,
                float(params["radius"]),
                float(params["bezier"]),
                float(params["Bezier_Rmax"]),
                float(params["Bezier_Rmin"]),
            )
        )
    if bend_type == "Euler":
        return (
            "Waveguide_width(%d)_Euler_Rmax%.3f_Rmin%.3f_Reff%.3f"
            % (
                width_nm,
                float(params["Euler_Rmax"]),
                float(params["Euler_Rmin"]),
                float(params["Euler_Reff"]),
            )
        )
    return "Waveguide_width(%d)_Circular_R%.3f" % (
        width_nm,
        float(params["radius"]),
    )


def _default_waveguide_params():
    """返回独立配置副本，避免 GUI 和测试共享可变默认值。"""
    return {
        "schema_version": PARAM_SCHEMA_VERSION,
        "active_tab": TAB_SINGLE,
        "single": {
            "width": 0.5, "radius": 20.0, "bend_type": "Circular",
            "bezier": 0.35, "Euler_Rmax": 30.0, "Euler_Rmin": 10.0,
        },
        "composite": {
            "straight_width": 2.0, "bend_width": 0.5,
            "start_width_role": "straight", "end_width_role": "straight",
            "taper_length": 20.0, "transition_length": 2.0,
            "radius": 30.0, "bend_type": "Bezier", "bezier": 0.3,
            "Euler_Rmax": 30.0, "Euler_Rmin": 10.0,
        },
        "user_defined": {"selected_id": "", "presets": []},
    }


def _normalize_editable_params(mode, values, validate=False):
    """规范化可持久化参数；派生值和复合端部实际宽度均不进入预设。"""
    defaults = _default_waveguide_params()[mode]
    keys = COMPOSITE_EDITABLE_KEYS if mode == TAB_COMPOSITE else SINGLE_EDITABLE_KEYS
    source = values if isinstance(values, dict) else {}
    result = {}
    numeric_keys = set(keys) - {"bend_type", "start_width_role", "end_width_role"}
    for key in keys:
        value = source.get(key, defaults[key])
        if key in numeric_keys:
            try:
                value = float(value)
            except Exception:
                if validate:
                    raise ValueError("%s 必须是有效数字。" % key)
                value = float(defaults[key])
        result[key] = value
    result["bend_type"] = _normalize_bend_type(result["bend_type"])
    if mode == TAB_COMPOSITE:
        straight = result["straight_width"]
        bend = result["bend_width"]
        result["start_width_role"] = _normalize_width_role(
            source.get("start_width_role"), source.get("start_width"), straight, bend,
        )
        result["end_width_role"] = _normalize_width_role(
            source.get("end_width_role"), source.get("end_width"), straight, bend,
        )
    if validate:
        if mode == TAB_SINGLE and result["width"] <= 0:
            raise ValueError("波导宽度必须大于0。")
        if mode == TAB_COMPOSITE:
            if result["straight_width"] <= 0 or result["bend_width"] <= 0:
                raise ValueError("直波导和弯曲波导宽度必须大于0。")
            if result["taper_length"] < 0 or result["transition_length"] < 0:
                raise ValueError("taper和transition长度不得小于0。")
    return result


def _result_from_editable_params(mode, values, dbu=0.001):
    """把持久化参数转换为几何生成入口需要的完整参数。"""
    editable = _normalize_editable_params(mode, values, validate=True)
    result = dict(editable)
    result["mode"] = mode
    if mode == TAB_COMPOSITE:
        result["start_width"] = (
            result["bend_width"] if result["start_width_role"] == "bend"
            else result["straight_width"]
        )
        result["end_width"] = (
            result["bend_width"] if result["end_width_role"] == "bend"
            else result["straight_width"]
        )
    result.update(_calculate_waveguide_derived(
        result["radius"], result["bend_type"], result["bezier"],
        result["Euler_Rmax"], result["Euler_Rmin"], dbu,
    ))
    return result


def _editable_params_from_result(result):
    mode = TAB_COMPOSITE if result.get("mode") == TAB_COMPOSITE else TAB_SINGLE
    return _normalize_editable_params(mode, result, validate=True)


def _preset_id(mode, params):
    payload = json.dumps(
        {"mode": mode, "params": params}, sort_keys=True,
        separators=(",", ":"), ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _bend_preset_name(params):
    bend_type = params["bend_type"]
    if bend_type == "Bezier":
        return "Bezier_R%.3f_B%.3f" % (params["radius"], params["bezier"])
    if bend_type == "Euler":
        return "Euler_Rmax%.3f_Rmin%.3f" % (
            params["Euler_Rmax"], params["Euler_Rmin"],
        )
    return "Circular_R%.3f" % params["radius"]


def _preset_base_name(mode, params):
    """生成只含英文、数字和下划线的参数摘要名称。"""
    if mode == TAB_SINGLE:
        return "Single_W%.3f_%s" % (params["width"], _bend_preset_name(params))
    start_role = "B" if params["start_width_role"] == "bend" else "S"
    end_role = "B" if params["end_width_role"] == "bend" else "S"
    return (
        "Composite_SW%.3f_BW%.3f_Start%s_End%s_T%.3f_TR%.3f_%s"
        % (
            params["straight_width"], params["bend_width"], start_role, end_role,
            params["taper_length"], params["transition_length"],
            _bend_preset_name(params),
        )
    )


def _unique_preset_name(base_name, presets):
    names = set(str(item.get("name", "")) for item in presets)
    if base_name not in names:
        return base_name
    suffix = 2
    while "%s_%d" % (base_name, suffix) in names:
        suffix += 1
    return "%s_%d" % (base_name, suffix)


def _normalize_user_defined(data):
    source = data if isinstance(data, dict) else {}
    normalized = {"selected_id": "", "presets": []}
    seen_ids = set()
    for item in source.get("presets", []):
        if not isinstance(item, dict):
            continue
        mode = item.get("mode")
        if mode not in (TAB_SINGLE, TAB_COMPOSITE):
            continue
        try:
            params = _normalize_editable_params(mode, item.get("params", {}), validate=True)
            _result_from_editable_params(mode, params)
        except Exception:
            continue
        preset_id = _preset_id(mode, params)
        if preset_id in seen_ids:
            continue
        seen_ids.add(preset_id)
        requested_name = str(item.get("name", "")).strip() or _preset_base_name(mode, params)
        name = _unique_preset_name(requested_name, normalized["presets"])
        normalized["presets"].append({
            "id": preset_id, "name": name, "mode": mode, "params": params,
            "note": str(item.get("note", "")),
        })
    selected_id = str(source.get("selected_id", ""))
    ids = [item["id"] for item in normalized["presets"]]
    normalized["selected_id"] = selected_id if selected_id in ids else (ids[0] if ids else "")
    return normalized


def _add_user_preset(settings, mode, values):
    """返回加入预设后的配置、被选预设以及是否新增。"""
    updated = copy.deepcopy(settings)
    params = _normalize_editable_params(mode, values, validate=True)
    _result_from_editable_params(mode, params)
    preset_id = _preset_id(mode, params)
    user_defined = updated["user_defined"]
    for item in user_defined["presets"]:
        if item["id"] == preset_id:
            user_defined["selected_id"] = preset_id
            return updated, item, False
    preset = {
        "id": preset_id,
        "name": _unique_preset_name(_preset_base_name(mode, params), user_defined["presets"]),
        "mode": mode,
        "params": params,
        "note": "",
    }
    user_defined["presets"].append(preset)
    user_defined["selected_id"] = preset_id
    return updated, preset, True


def _delete_user_presets(settings, preset_ids):
    updated = copy.deepcopy(settings)
    remove_ids = set(str(value) for value in preset_ids)
    user_defined = updated["user_defined"]
    before = len(user_defined["presets"])
    user_defined["presets"] = [
        item for item in user_defined["presets"] if item["id"] not in remove_ids
    ]
    remaining_ids = [item["id"] for item in user_defined["presets"]]
    if user_defined.get("selected_id") not in remaining_ids:
        user_defined["selected_id"] = remaining_ids[0] if remaining_ids else ""
    return updated, before - len(user_defined["presets"])


def _update_user_preset_note(settings, preset_id, note):
    """更新指定预设的记录文本；Note 不参与预设身份和几何参数。"""
    updated = copy.deepcopy(settings)
    target_id = str(preset_id)
    for item in updated.get("user_defined", {}).get("presets", []):
        if item.get("id") == target_id:
            item["note"] = str(note)
            return updated, True
    return updated, False


def _update_user_preset_name(settings, preset_id, name):
    """重命名指定预设，同时保持参数生成的稳定 ID 不变。"""
    normalized_name = str(name).strip()
    if not normalized_name:
        raise ValueError("Preset Name 不能为空。")
    updated = copy.deepcopy(settings)
    target_id = str(preset_id)
    presets = updated.get("user_defined", {}).get("presets", [])
    for item in presets:
        if item.get("id") != target_id and item.get("name") == normalized_name:
            raise ValueError("Preset Name 已存在：%s" % normalized_name)
    for item in presets:
        if item.get("id") == target_id:
            item["name"] = normalized_name
            return updated, True
    return updated, False


def _selected_user_preset(settings, preset_id=None):
    user_defined = settings.get("user_defined", {})
    selected_id = str(preset_id or user_defined.get("selected_id", ""))
    for item in user_defined.get("presets", []):
        if item.get("id") == selected_id:
            return item
    presets = user_defined.get("presets", [])
    return presets[0] if presets else None


def _load_waveguide_params():
    defaults = _default_waveguide_params()
    filepath = _waveguide_params_file()
    if not os.path.isfile(filepath):
        return defaults
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return defaults
    if not isinstance(data, dict):
        return defaults
    if isinstance(data.get("single"), dict):
        defaults["single"] = _normalize_editable_params(TAB_SINGLE, data["single"])
        defaults["composite"] = _normalize_editable_params(
            TAB_COMPOSITE, data.get("composite", {}),
        )
        defaults["user_defined"] = _normalize_user_defined(data.get("user_defined", {}))
        active_tab = str(data.get("active_tab", TAB_SINGLE))
        defaults["active_tab"] = (
            active_tab if active_tab in (TAB_SINGLE, TAB_COMPOSITE, TAB_USER_DEFINED)
            else TAB_SINGLE
        )
    else:
        # 旧版平铺 JSON 只迁移到单宽度页。
        defaults["single"] = _normalize_editable_params(TAB_SINGLE, data)
    return defaults


def _save_waveguide_params(params):
    """在配置文件同目录原子替换，写入失败时保留原文件。"""
    filepath = _waveguide_params_file()
    directory = os.path.dirname(filepath)
    os.makedirs(directory, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False, dir=directory,
            prefix=".jnu_waveguide_params_", suffix=".tmp",
        ) as stream:
            temporary = stream.name
            json.dump(params, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, filepath)
    except Exception:
        if temporary and os.path.isfile(temporary):
            try:
                os.remove(temporary)
            except OSError:
                pass
        raise


def _add_edit(page, page_layout, row, label_text, value, readonly=False):
    label = pya.QLabel(label_text, page)
    edit = pya.QLineEdit(page)
    edit.setText(str(value))
    edit.setReadOnly(readonly)
    page_layout.addWidget(label, row, 0)
    page_layout.addWidget(edit, row, 1)
    return label, edit


def _add_width_role_combo(page, page_layout, row, label_text, role):
    label = pya.QLabel(label_text, page)
    combo = pya.QComboBox(page)
    combo.addItem("Straight Width")
    combo.addItem("Bend Width")
    combo.setCurrentIndex(1 if role == "bend" else 0)
    page_layout.addWidget(label, row, 0)
    page_layout.addWidget(combo, row, 1)
    return label, combo


def _width_role_from_combo(combo):
    try:
        return "bend" if int(combo.currentIndex) == 1 else "straight"
    except Exception:
        return "straight"


def _set_width_role_combo_labels(combo, straight_width, bend_width):
    labels = ["Straight Width", "Bend Width"]
    try:
        straight = float(straight_width)
        bend = float(bend_width)
        labels = ["Straight Width (%.3f um)" % straight, "Bend Width (%.3f um)" % bend]
    except Exception:
        pass
    current = 0
    try:
        current = int(combo.currentIndex)
    except Exception:
        pass
    try:
        combo.setItemText(0, labels[0])
        combo.setItemText(1, labels[1])
    except Exception:
        try:
            combo.clear()
            combo.addItem(labels[0])
            combo.addItem(labels[1])
        except Exception:
            return
    try:
        combo.setCurrentIndex(current)
    except Exception:
        pass


def _qt_property_value(obj, name, default=None):
    """兼容读取 Qt 属性的属性/方法两种绑定形式。"""
    try:
        value = getattr(obj, name)
        return value() if callable(value) else value
    except Exception:
        return default


def _set_font_point_size(font, point_size):
    """兼容不同 KLayout Qt 绑定设置字号。"""
    try:
        font.pointSize = int(point_size)
        return True
    except Exception:
        pass
    try:
        font.setPointSize(int(point_size))
        return True
    except Exception:
        return False


def _set_font_bold(font, bold):
    """兼容不同 KLayout Qt 绑定设置粗体。"""
    try:
        font.bold = bool(bold)
        return True
    except Exception:
        pass
    try:
        font.setBold(bool(bold))
        return True
    except Exception:
        return False


def _set_widget_font(widget, font):
    """兼容不同 KLayout Qt 绑定写回字体。"""
    try:
        widget.font = font
        return True
    except Exception:
        pass
    try:
        widget.setFont(font)
        return True
    except Exception:
        return False


def _style_parameter_group_title(group):
    """只放大分组标题，保持标签和输入框使用 KLayout 默认字体。

    部分 KLayout/Qt 组合不会稳定应用 QGroupBox::title 选择器，因此同时
    设置 QGroupBox 自身字体作为标题显示的兜底方案。
    """
    title_font = _qt_property_value(group, "font")
    if title_font is not None:
        _set_font_point_size(title_font, 16)
        _set_font_bold(title_font, True)
        _set_widget_font(group, title_font)
    group.setStyleSheet(
        "QGroupBox { font-size: 16pt; font-weight: bold; } "
        "QGroupBox::title { font-size: 16pt; font-weight: bold; }"
    )


def _restore_parameter_child_fonts(
    controls,
    default_font,
    group_keys=("editable_group", "calculated_group"),
):
    """把分组内普通控件恢复为默认字体，避免标题字号继承到输入区。"""
    if default_font is None:
        return
    excluded = set(group_keys)
    for key, widget in controls.items():
        if key in excluded:
            continue
        if hasattr(widget, "font"):
            _set_widget_font(widget, default_font)


def _build_waveguide_page(parent, values, composite, dbu):
    page = pya.QWidget(parent)
    layout = pya.QHBoxLayout(page)
    page.setLayout(layout)
    default_child_font = _qt_property_value(page, "font")
    editable_group = pya.QGroupBox("Editable Parameters", page)
    calculated_group = pya.QGroupBox("Calculated Parameters", page)
    editable_layout = pya.QGridLayout(editable_group)
    calculated_layout = pya.QGridLayout(calculated_group)
    editable_group.setLayout(editable_layout)
    calculated_group.setLayout(calculated_layout)
    editable_layout.setColumnStretch(1, 1)
    calculated_layout.setColumnStretch(1, 1)
    layout.addWidget(editable_group)
    layout.addWidget(calculated_group)
    layout.setStretch(0, 3)
    layout.setStretch(1, 2)
    controls = {
        "page": page, "layout": layout,
        "editable_group": editable_group, "calculated_group": calculated_group,
        "editable_order": [],
    }
    editable_row = 0

    def add_bend_type(row):
        bend_label = pya.QLabel("Bend Type：", page)
        bend_combo = pya.QComboBox(page)
        bend_types = ["Circular", "Bezier", "Euler"]
        for item in bend_types:
            bend_combo.addItem(item)
        bend_combo.setCurrentIndex(bend_types.index(values["bend_type"]))
        editable_layout.addWidget(bend_label, row, 0)
        editable_layout.addWidget(bend_combo, row, 1)
        controls["bend_type_label"] = bend_label
        controls["bend_type"] = bend_combo
        controls["editable_order"].append("bend_type")
        return bend_combo

    if not composite:
        bend = add_bend_type(editable_row)
        editable_row += 1

    if composite:
        controls["straight_width_label"], controls["straight_width"] = _add_edit(page, editable_layout, editable_row, "Straight Width (um)：", values["straight_width"])
        controls["editable_order"].append("straight_width")
        editable_row += 1
        controls["bend_width_label"], controls["bend_width"] = _add_edit(page, editable_layout, editable_row, "Bend Width (um)：", values["bend_width"])
        controls["editable_order"].append("bend_width")
        editable_row += 1
        controls["start_width_role_label"], controls["start_width_role"] = _add_width_role_combo(page, editable_layout, editable_row, "Start Width：", values.get("start_width_role", "straight"))
        controls["editable_order"].append("start_width_role")
        editable_row += 1
        controls["end_width_role_label"], controls["end_width_role"] = _add_width_role_combo(page, editable_layout, editable_row, "End Width：", values.get("end_width_role", "straight"))
        controls["editable_order"].append("end_width_role")
        editable_row += 1
        controls["taper_length_label"], controls["taper_length"] = _add_edit(page, editable_layout, editable_row, "Taper Length (um)：", values["taper_length"])
        controls["editable_order"].append("taper_length")
        editable_row += 1
        controls["transition_length_label"], controls["transition_length"] = _add_edit(page, editable_layout, editable_row, "Transition Length (um)：", values.get("transition_length", 2.0))
        controls["editable_order"].append("transition_length")
        editable_row += 1
        bend = add_bend_type(editable_row)
        editable_row += 1
    else:
        controls["width_label"], controls["width"] = _add_edit(page, editable_layout, editable_row, "Waveguide Width (um)：", values["width"])
        controls["editable_order"].append("width")
        editable_row += 1

    controls["radius_label"], controls["radius"] = _add_edit(page, editable_layout, editable_row, "Bend Radius (um)：", values["radius"])
    controls["editable_order"].append("radius")
    editable_row += 1
    controls["bezier_label"], controls["bezier"] = _add_edit(page, editable_layout, editable_row, "Bezier B：", values["bezier"])
    controls["editable_order"].append("bezier")
    editable_row += 1
    controls["Euler_Rmax_label"], controls["Euler_Rmax"] = _add_edit(page, editable_layout, editable_row, "Euler Rmax (um)：", values["Euler_Rmax"])
    controls["editable_order"].append("Euler_Rmax")
    editable_row += 1
    controls["Euler_Rmin_label"], controls["Euler_Rmin"] = _add_edit(page, editable_layout, editable_row, "Euler Rmin (um)：", values["Euler_Rmin"])
    controls["editable_order"].append("Euler_Rmin")
    editable_row += 1
    save_button = pya.QPushButton("Save as User-Defined", page)
    save_button.setObjectName(
        "jnu_save_composite_preset" if composite else "jnu_save_single_preset"
    )
    editable_layout.addWidget(save_button, editable_row, 0, 1, 2)
    controls["save_button"] = save_button
    controls["editable_order"].append("save_button")

    calculated_row = 0
    controls["npoints_label"], controls["npoints"] = _add_edit(page, calculated_layout, calculated_row, "Bend Points [uneditable]：", "", True)
    calculated_row += 1
    controls["Bezier_Rmax_label"], controls["Bezier_Rmax"] = _add_edit(page, calculated_layout, calculated_row, "Bezier Rmax [uneditable] (um)：", "", True)
    calculated_row += 1
    controls["Bezier_Rmin_label"], controls["Bezier_Rmin"] = _add_edit(page, calculated_layout, calculated_row, "Bezier Rmin [uneditable] (um)：", "", True)
    calculated_row += 1
    controls["Euler_Reff_label"], controls["Euler_Reff"] = _add_edit(page, calculated_layout, calculated_row, "Euler Reff [uneditable] (um)：", "", True)

    _style_parameter_group_title(editable_group)
    _style_parameter_group_title(calculated_group)
    _restore_parameter_child_fonts(controls, default_child_font)

    def refresh(_value=None):
        bend_type = str(bend.currentText)
        is_bezier, is_euler = bend_type == "Bezier", bend_type == "Euler"
        controls["radius_label"].setVisible(not is_euler)
        controls["radius"].setVisible(not is_euler)
        for key in ("bezier_label", "bezier", "Bezier_Rmax_label", "Bezier_Rmax", "Bezier_Rmin_label", "Bezier_Rmin"):
            controls[key].setVisible(is_bezier)
        for key in ("Euler_Rmax_label", "Euler_Rmax", "Euler_Rmin_label", "Euler_Rmin", "Euler_Reff_label", "Euler_Reff"):
            controls[key].setVisible(is_euler)
        for key in ("npoints", "Bezier_Rmax", "Bezier_Rmin", "Euler_Reff"):
            controls[key].setText("")
        if composite:
            _set_width_role_combo_labels(
                controls["start_width_role"], controls["straight_width"].text, controls["bend_width"].text
            )
            _set_width_role_combo_labels(
                controls["end_width_role"], controls["straight_width"].text, controls["bend_width"].text
            )
        try:
            derived = _calculate_waveguide_derived(
                controls["radius"].text, bend_type, controls["bezier"].text,
                controls["Euler_Rmax"].text, controls["Euler_Rmin"].text, dbu,
            )
            controls["npoints"].setText(str(derived["npoints"]))
            if derived["Bezier_Rmax"] is not None:
                controls["Bezier_Rmax"].setText("%.3f" % derived["Bezier_Rmax"])
                controls["Bezier_Rmin"].setText("%.3f" % derived["Bezier_Rmin"])
            if derived["Euler_Reff"] is not None:
                controls["Euler_Reff"].setText("%.3f" % derived["Euler_Reff"])
        except Exception:
            pass

    bend.currentIndexChanged(refresh)
    for key in ("radius", "bezier", "Euler_Rmax", "Euler_Rmin"):
        controls[key].textChanged(refresh)
    if composite:
        for key in ("straight_width", "bend_width"):
            controls[key].textChanged(refresh)
    controls["refresh"] = refresh
    object_prefix = "jnu_composite_" if composite else "jnu_single_"
    for key in controls["editable_order"]:
        widget = controls.get(key)
        if widget is not None and key != "save_button":
            try:
                widget.setObjectName(object_prefix + key)
            except Exception:
                pass
    refresh()
    return controls


def _parse_waveguide_page(controls, saved_values, composite, dbu):
    mode = TAB_COMPOSITE if composite else TAB_SINGLE
    values = {}
    if composite:
        values["straight_width"] = controls["straight_width"].text
        values["bend_width"] = controls["bend_width"].text
        values["start_width_role"] = _width_role_from_combo(controls["start_width_role"])
        values["end_width_role"] = _width_role_from_combo(controls["end_width_role"])
        values["taper_length"] = controls["taper_length"].text
        values["transition_length"] = controls["transition_length"].text
    else:
        values["width"] = controls["width"].text
    values["bend_type"] = _normalize_bend_type(str(controls["bend_type"].currentText))
    values["radius"] = controls["radius"].text
    values["bezier"] = controls["bezier"].text
    values["Euler_Rmax"] = controls["Euler_Rmax"].text
    values["Euler_Rmin"] = controls["Euler_Rmin"].text
    return _result_from_editable_params(mode, values, dbu)


def _build_user_defined_page(parent):
    page = pya.QWidget(parent)
    layout = pya.QHBoxLayout(page)
    page.setLayout(layout)
    default_child_font = _qt_property_value(page, "font")
    selection_group = pya.QGroupBox("Saved Types", page)
    preview_group = pya.QGroupBox("Selected Parameters", page)
    note_group = pya.QGroupBox("Note", page)
    selection_layout = pya.QVBoxLayout(selection_group)
    preview_layout = pya.QGridLayout(preview_group)
    note_layout = pya.QVBoxLayout(note_group)
    right_panel = pya.QWidget(page)
    right_layout = pya.QVBoxLayout(right_panel)
    selection_group.setLayout(selection_layout)
    preview_group.setLayout(preview_layout)
    note_group.setLayout(note_layout)
    right_panel.setLayout(right_layout)
    preview_layout.setColumnStretch(1, 1)
    combo_label = pya.QLabel("User-Defined Waveguide：", page)
    combo = pya.QComboBox(page)
    combo.setObjectName("jnu_user_defined_preset_combo")
    manage_button = pya.QPushButton("Manage", page)
    empty_label = pya.QLabel("No saved presets.", page)
    note_edit = pya.QPlainTextEdit(page)
    note_edit.setObjectName("jnu_user_defined_note")
    note_edit.setPlaceholderText("Enter notes for the selected preset...")
    note_edit.setMinimumHeight(90)
    selection_layout.addWidget(combo_label)
    selection_layout.addWidget(combo)
    selection_layout.addWidget(manage_button)
    selection_layout.addWidget(empty_label)
    selection_layout.addStretch(1)
    note_layout.addWidget(note_edit)
    right_layout.addWidget(preview_group)
    right_layout.addWidget(note_group)
    right_layout.setStretch(0, 4)
    right_layout.setStretch(1, 1)
    layout.addWidget(selection_group)
    layout.addWidget(right_panel)
    layout.setStretch(0, 2)
    layout.setStretch(1, 3)
    controls = {
        "page": page, "combo": combo, "manage_button": manage_button,
        "empty_label": empty_label, "preset_ids": [],
        "selection_group": selection_group, "preview_group": preview_group,
        "combo_label": combo_label, "note_group": note_group,
        "note_edit": note_edit, "right_panel": right_panel,
    }
    fields = (
        ("preset_name", "Preset Name："),
        ("mode", "Waveguide Mode："),
        ("width", "Waveguide Width (um)："),
        ("straight_width", "Straight Width (um)："),
        ("bend_width", "Bend Width (um)："),
        ("start_width_role", "Start Width："),
        ("end_width_role", "End Width："),
        ("taper_length", "Taper Length (um)："),
        ("transition_length", "Transition Length (um)："),
        ("bend_type", "Bend Type："),
        ("radius", "Bend Radius (um)："),
        ("bezier", "Bezier B："),
        ("Euler_Rmax", "Euler Rmax (um)："),
        ("Euler_Rmin", "Euler Rmin (um)："),
        ("npoints", "Bend Points [uneditable]："),
        ("Bezier_Rmax", "Bezier Rmax [uneditable] (um)："),
        ("Bezier_Rmin", "Bezier Rmin [uneditable] (um)："),
        ("Euler_Reff", "Euler Reff [uneditable] (um)："),
    )
    for row, (key, label) in enumerate(fields):
        controls[key + "_label"], controls[key] = _add_edit(
            page, preview_layout, row, label, "", key != "preset_name",
        )
    controls["preset_name"].setObjectName("jnu_user_defined_preset_name")
    _style_parameter_group_title(selection_group)
    _style_parameter_group_title(preview_group)
    _restore_parameter_child_fonts(
        controls,
        default_child_font,
        ("selection_group", "preview_group"),
    )
    return controls


def _set_user_preview_field(controls, key, value, visible=True):
    controls[key].setText(str(value))
    controls[key].setVisible(visible)
    controls[key + "_label"].setVisible(visible)


def _refresh_user_defined_preview(controls, preset, dbu=0.001):
    """以只读字段展示所选预设，字段显隐与对应基础页保持一致。"""
    all_keys = (
        "preset_name", "mode", "width", "straight_width", "bend_width",
        "start_width_role", "end_width_role", "taper_length", "transition_length",
        "bend_type", "radius", "bezier", "Euler_Rmax", "Euler_Rmin", "npoints",
        "Bezier_Rmax", "Bezier_Rmin", "Euler_Reff",
    )
    if preset is None:
        for key in all_keys:
            _set_user_preview_field(controls, key, "", False)
        return

    result = _result_from_editable_params(preset["mode"], preset["params"], dbu)
    is_composite = preset["mode"] == TAB_COMPOSITE
    is_bezier = result["bend_type"] == "Bezier"
    is_euler = result["bend_type"] == "Euler"
    _set_user_preview_field(controls, "preset_name", preset["name"])
    _set_user_preview_field(
        controls, "mode",
        "Composite-Width Waveguide" if is_composite else "Single-Width Waveguide",
    )
    _set_user_preview_field(controls, "width", "%.3f" % result.get("width", 0.0), not is_composite)
    _set_user_preview_field(controls, "straight_width", "%.3f" % result.get("straight_width", 0.0), is_composite)
    _set_user_preview_field(controls, "bend_width", "%.3f" % result.get("bend_width", 0.0), is_composite)
    _set_user_preview_field(
        controls, "start_width_role",
        "Bend Width" if result.get("start_width_role") == "bend" else "Straight Width",
        is_composite,
    )
    _set_user_preview_field(
        controls, "end_width_role",
        "Bend Width" if result.get("end_width_role") == "bend" else "Straight Width",
        is_composite,
    )
    _set_user_preview_field(controls, "taper_length", "%.3f" % result.get("taper_length", 0.0), is_composite)
    _set_user_preview_field(controls, "transition_length", "%.3f" % result.get("transition_length", 0.0), is_composite)
    _set_user_preview_field(controls, "bend_type", result["bend_type"])
    _set_user_preview_field(controls, "radius", "%.3f" % result["radius"], not is_euler)
    _set_user_preview_field(controls, "bezier", "%.3f" % result["bezier"], is_bezier)
    _set_user_preview_field(controls, "Euler_Rmax", "%.3f" % result["Euler_Rmax"], is_euler)
    _set_user_preview_field(controls, "Euler_Rmin", "%.3f" % result["Euler_Rmin"], is_euler)
    _set_user_preview_field(controls, "npoints", str(result["npoints"]))
    _set_user_preview_field(controls, "Bezier_Rmax", "%.3f" % result["Bezier_Rmax"] if is_bezier else "", is_bezier)
    _set_user_preview_field(controls, "Bezier_Rmin", "%.3f" % result["Bezier_Rmin"] if is_bezier else "", is_bezier)
    _set_user_preview_field(controls, "Euler_Reff", "%.3f" % result["Euler_Reff"] if is_euler else "", is_euler)


def _current_user_preset_id(controls):
    try:
        index = int(controls["combo"].currentIndex)
    except Exception:
        index = -1
    if index < 0 or index >= len(controls["preset_ids"]):
        return ""
    return controls["preset_ids"][index]


def _refresh_user_defined_page(controls, settings, dbu=0.001):
    combo = controls["combo"]
    user_defined = settings["user_defined"]
    presets = user_defined["presets"]
    combo.blockSignals(True)
    combo.clear()
    controls["preset_ids"] = []
    selected_index = -1
    for index, preset in enumerate(presets):
        combo.addItem(preset["name"])
        controls["preset_ids"].append(preset["id"])
        if preset["id"] == user_defined.get("selected_id"):
            selected_index = index
    if presets:
        combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
    combo.blockSignals(False)
    has_presets = bool(presets)
    combo.setEnabled(has_presets)
    controls["manage_button"].setEnabled(has_presets)
    controls["empty_label"].setVisible(not has_presets)
    selected = _selected_user_preset(settings, _current_user_preset_id(controls))
    _refresh_user_defined_preview(controls, selected, dbu)
    controls["note_edit"].blockSignals(True)
    controls["note_edit"].setPlainText(selected.get("note", "") if selected else "")
    controls["note_edit"].blockSignals(False)
    controls["note_edit"].setEnabled(has_presets)


def _show_manage_presets_dialog(parent, presets):
    """返回管理窗口确认后的预设列表；取消时返回 None。"""
    staged = copy.deepcopy(presets)
    dialog = pya.QDialog(parent)
    dialog.setWindowTitle("Manage User-Defined Waveguides")
    layout = pya.QVBoxLayout(dialog)
    dialog.setLayout(layout)
    list_widget = pya.QListWidget(dialog)
    list_widget.setSelectionMode(pya.QAbstractItemView.ExtendedSelection)
    for preset in staged:
        mode_label = "Single" if preset["mode"] == TAB_SINGLE else "Composite"
        list_widget.addItem("[%s] %s" % (mode_label, preset["name"]))
    delete_button = pya.QPushButton("Delete Selected", dialog)
    layout.addWidget(list_widget)
    layout.addWidget(delete_button)

    def delete_selected(_checked=False):
        rows = sorted(
            set(int(list_widget.row(item)) for item in list_widget.selectedItems()),
            reverse=True,
        )
        for row in rows:
            list_widget.takeItem(row)
            staged.pop(row)

    delete_button.clicked(delete_selected)
    buttons = pya.QHBoxLayout(dialog)
    ok_button = pya.QPushButton("OK", dialog)
    cancel_button = pya.QPushButton("Cancel", dialog)
    ok_button.clicked(lambda _checked: dialog.accept())
    cancel_button.clicked(lambda _checked: dialog.reject())
    buttons.addWidget(ok_button)
    buttons.addWidget(cancel_button)
    layout.addLayout(buttons)
    result = exec_dialog_with_persisted_size(
        dialog, "manage_waveguide_presets", (720, 420),
    )
    return staged if result != 0 else None


def _show_waveguide_dialog(dbu=0.001):
    state = {"saved": _load_waveguide_params()}
    dialog = pya.QDialog(_main_window())
    dialog.setWindowTitle("JNU Path to Waveguide")
    layout = pya.QVBoxLayout(dialog)
    dialog.setLayout(layout)
    tabs = pya.QTabWidget(dialog)
    tabs.setObjectName("jnu_path_to_waveguide_tabs")
    single = _build_waveguide_page(tabs, state["saved"]["single"], False, dbu)
    composite = _build_waveguide_page(tabs, state["saved"]["composite"], True, dbu)
    user_defined = _build_user_defined_page(tabs)
    tabs.addTab(user_defined["page"], TAB_LABELS[TAB_USER_DEFINED])
    tabs.addTab(single["page"], TAB_LABELS[TAB_SINGLE])
    tabs.addTab(composite["page"], TAB_LABELS[TAB_COMPOSITE])
    active_indices = {TAB_USER_DEFINED: 0, TAB_SINGLE: 1, TAB_COMPOSITE: 2}
    tabs.setCurrentIndex(
        active_indices.get(state["saved"]["active_tab"], active_indices[TAB_SINGLE])
    )
    layout.addWidget(tabs)

    buttons = pya.QHBoxLayout(dialog)
    ok_btn, cancel_btn = pya.QPushButton("OK", dialog), pya.QPushButton("Cancel", dialog)
    buttons.addWidget(ok_btn)
    buttons.addWidget(cancel_btn)
    layout.addLayout(buttons)
    ok_btn.setDefault(True)
    # 主参数窗口每次都从统一尺寸打开；用户本次会话中的临时缩放不写入配置。
    dialog.setMinimumSize(600, 400)
    dialog.resize(1187, 541)

    name_timer = pya.QTimer(dialog)
    name_timer.setSingleShot(True)
    note_timer = pya.QTimer(dialog)
    note_timer.setSingleShot(True)
    name_state = {
        "preset_id": "", "committed_name": "", "dirty": False, "loading": False,
    }
    note_state = {"preset_id": "", "dirty": False, "loading": False}

    def preset_name_text():
        return str(_value(user_defined["preset_name"], "text"))

    def set_current_combo_text(text):
        index = int(_value(user_defined["combo"], "currentIndex"))
        if 0 <= index < len(user_defined["preset_ids"]):
            user_defined["combo"].setItemText(index, str(text))

    def load_selected_name(preset):
        name_timer.stop()
        name_state["loading"] = True
        try:
            name = preset.get("name", "") if preset else ""
            user_defined["preset_name"].blockSignals(True)
            user_defined["preset_name"].setText(name)
            user_defined["preset_name"].blockSignals(False)
            user_defined["preset_name"].setEnabled(preset is not None)
            name_state["preset_id"] = preset.get("id", "") if preset else ""
            name_state["committed_name"] = name
            name_state["dirty"] = False
            if preset is not None:
                set_current_combo_text(name)
        finally:
            user_defined["preset_name"].blockSignals(False)
            name_state["loading"] = False

    def flush_name(force=False):
        if not name_state["dirty"] or not name_state["preset_id"]:
            return True
        try:
            candidate, found = _update_user_preset_name(
                state["saved"], name_state["preset_id"], preset_name_text(),
            )
        except ValueError as error:
            if force:
                _message("JNU_MWP_PDK", str(error))
            return False
        if not found:
            name_state["dirty"] = False
            return True
        try:
            _save_waveguide_params(candidate)
            state["saved"] = candidate
            preset = _selected_user_preset(candidate, name_state["preset_id"])
            committed_name = preset.get("name", "") if preset else ""
            name_state["committed_name"] = committed_name
            name_state["dirty"] = False
            name_timer.stop()
            name_state["loading"] = True
            user_defined["preset_name"].blockSignals(True)
            user_defined["preset_name"].setText(committed_name)
            user_defined["preset_name"].blockSignals(False)
            set_current_combo_text(committed_name)
            name_state["loading"] = False
            return True
        except Exception as error:
            name_state["loading"] = False
            _message("JNU_MWP_PDK", "Preset Name 自动保存失败：\n%s" % error)
            return False

    def preset_name_changed(_text=None):
        if name_state["loading"] or not name_state["preset_id"]:
            return
        set_current_combo_text(preset_name_text())
        name_state["dirty"] = True
        name_timer.start(500)

    def note_text():
        return str(_value(user_defined["note_edit"], "toPlainText"))

    def load_selected_note(preset):
        note_timer.stop()
        note_state["loading"] = True
        try:
            user_defined["note_edit"].blockSignals(True)
            user_defined["note_edit"].setPlainText(
                preset.get("note", "") if preset else ""
            )
            user_defined["note_edit"].blockSignals(False)
            user_defined["note_edit"].setEnabled(preset is not None)
            note_state["preset_id"] = preset.get("id", "") if preset else ""
            note_state["dirty"] = False
        finally:
            user_defined["note_edit"].blockSignals(False)
            note_state["loading"] = False

    def flush_note():
        if not note_state["dirty"] or not note_state["preset_id"]:
            return True
        candidate, found = _update_user_preset_note(
            state["saved"], note_state["preset_id"], note_text(),
        )
        if not found:
            note_state["dirty"] = False
            return True
        try:
            _save_waveguide_params(candidate)
            state["saved"] = candidate
            note_state["dirty"] = False
            note_timer.stop()
            return True
        except Exception as error:
            _message("JNU_MWP_PDK", "Note 自动保存失败：\n%s" % error)
            return False

    def note_changed():
        if note_state["loading"] or not note_state["preset_id"]:
            return
        note_state["dirty"] = True
        note_timer.start(500)

    def flush_user_fields(force=False):
        if not flush_name(force):
            return False
        return flush_note()

    def restore_note_combo(preset_id):
        if preset_id not in user_defined["preset_ids"]:
            return
        user_defined["combo"].blockSignals(True)
        user_defined["combo"].setCurrentIndex(
            user_defined["preset_ids"].index(preset_id)
        )
        user_defined["combo"].blockSignals(False)

    def update_user_preview(_index=None):
        previous_id = name_state["preset_id"] or note_state["preset_id"]
        if not flush_user_fields(True):
            restore_note_combo(previous_id)
            return
        preset_id = _current_user_preset_id(user_defined)
        state["saved"]["user_defined"]["selected_id"] = preset_id
        preset = _selected_user_preset(state["saved"], preset_id)
        name_state["loading"] = True
        try:
            _refresh_user_defined_preview(user_defined, preset, dbu)
        finally:
            name_state["loading"] = False
        load_selected_name(preset)
        load_selected_note(preset)

    def update_ok_enabled(_index=None):
        enabled = (
            int(_value(tabs, "currentIndex")) != active_indices[TAB_USER_DEFINED]
            or bool(state["saved"]["user_defined"]["presets"])
        )
        ok_btn.setEnabled(enabled)

    def refresh_user_page():
        name_timer.stop()
        note_timer.stop()
        name_state["loading"] = True
        try:
            _refresh_user_defined_page(user_defined, state["saved"], dbu)
        finally:
            name_state["loading"] = False
        preset = _selected_user_preset(
            state["saved"], _current_user_preset_id(user_defined),
        )
        load_selected_name(preset)
        load_selected_note(preset)
        update_ok_enabled()

    def save_as_user_defined(mode, controls, composite_mode):
        if not flush_user_fields(True):
            return
        try:
            result = _parse_waveguide_page(
                controls, state["saved"][mode], composite_mode, dbu,
            )
            candidate, preset, created = _add_user_preset(
                state["saved"], mode, _editable_params_from_result(result),
            )
            _save_waveguide_params(candidate)
            state["saved"] = candidate
            refresh_user_page()
            if created:
                _message(
                    "JNU_MWP_PDK",
                    "User-Defined 参数保存成功：\n%s" % preset["name"],
                )
            else:
                _message(
                    "JNU_MWP_PDK",
                    "User-Defined 参数已存在，已选择现有预设：\n%s" % preset["name"],
                )
        except Exception as error:
            _message("JNU_MWP_PDK", "保存 User-Defined 参数失败：\n%s" % error)

    def manage_presets(_checked=False):
        if not flush_user_fields(True):
            return
        current_id = _current_user_preset_id(user_defined)
        if current_id:
            state["saved"]["user_defined"]["selected_id"] = current_id
        staged = _show_manage_presets_dialog(
            dialog, state["saved"]["user_defined"]["presets"],
        )
        if staged is None:
            return
        try:
            candidate = copy.deepcopy(state["saved"])
            candidate["user_defined"]["presets"] = staged
            candidate["user_defined"] = _normalize_user_defined(candidate["user_defined"])
            _save_waveguide_params(candidate)
            state["saved"] = candidate
            refresh_user_page()
        except Exception as error:
            _message("JNU_MWP_PDK", "删除 User-Defined 参数失败：\n%s" % error)

    def change_tab(index):
        if (
            int(index) != active_indices[TAB_USER_DEFINED]
            and not flush_user_fields(True)
        ):
            tabs.blockSignals(True)
            tabs.setCurrentIndex(active_indices[TAB_USER_DEFINED])
            tabs.blockSignals(False)
        update_ok_enabled()

    def accept_dialog(_checked=False):
        if flush_user_fields(True):
            dialog.accept()

    def reject_dialog(_checked=False):
        if flush_user_fields(True):
            dialog.reject()

    single["save_button"].clicked(
        lambda _checked: save_as_user_defined(TAB_SINGLE, single, False)
    )
    composite["save_button"].clicked(
        lambda _checked: save_as_user_defined(TAB_COMPOSITE, composite, True)
    )
    user_defined["combo"].currentIndexChanged(update_user_preview)
    user_defined["manage_button"].clicked(manage_presets)
    user_defined["preset_name"].textChanged(preset_name_changed)
    user_defined["note_edit"].textChanged(note_changed)
    name_timer.timeout(lambda: flush_name(False))
    note_timer.timeout(flush_note)
    tabs.currentChanged(change_tab)
    ok_btn.clicked(accept_dialog)
    cancel_btn.clicked(reject_dialog)
    refresh_user_page()

    # Qt 首次显示时会按三个页签的尺寸提示扩张窗口；显示事件完成后再次设置，
    # 才能稳定得到横向展开、纵向紧凑的目标尺寸。
    initial_size_timer = pya.QTimer(dialog)
    initial_size_timer.setSingleShot(True)
    def apply_initial_dialog_size():
        dialog.setMinimumSize(600, 400)
        dialog.resize(1187, 541)

    initial_size_timer.timeout(apply_initial_dialog_size)
    initial_size_timer.start(0)

    def persist_dialog_settings():
        """保存三个页签的有效设置；未完成的无效输入保留上次有效值。"""
        candidate = copy.deepcopy(state["saved"])
        current_index = int(_value(tabs, "currentIndex"))
        index_to_tab = {index: name for name, index in active_indices.items()}
        candidate["active_tab"] = index_to_tab.get(current_index, TAB_SINGLE)
        current_preset_id = _current_user_preset_id(user_defined)
        if current_preset_id:
            candidate["user_defined"]["selected_id"] = current_preset_id
        for mode, controls, composite_mode in (
            (TAB_SINGLE, single, False),
            (TAB_COMPOSITE, composite, True),
        ):
            try:
                parsed = _parse_waveguide_page(
                    controls, state["saved"][mode], composite_mode, dbu,
                )
                candidate[mode] = _editable_params_from_result(parsed)
            except (TypeError, ValueError):
                pass
        try:
            _save_waveguide_params(candidate)
            state["saved"] = candidate
            return True
        except Exception as error:
            _message("JNU_MWP_PDK", "参数配置保存失败：\n%s" % error)
            return False

    while True:
        dialog_result = dialog.exec_()
        if flush_user_fields(True):
            break
    persist_dialog_settings()
    if dialog_result == 0:
        return None

    active = int(_value(tabs, "currentIndex"))
    try:
        if active == active_indices[TAB_USER_DEFINED]:
            preset_id = _current_user_preset_id(user_defined)
            preset = _selected_user_preset(state["saved"], preset_id)
            if preset is None:
                raise ValueError("没有可用的 User-Defined 波导参数。")
            result = _result_from_editable_params(preset["mode"], preset["params"], dbu)
        else:
            is_composite = active == active_indices[TAB_COMPOSITE]
            group = TAB_COMPOSITE if is_composite else TAB_SINGLE
            controls = composite if is_composite else single
            result = _parse_waveguide_page(
                controls, state["saved"][group], is_composite, dbu,
            )
    except (TypeError, ValueError) as error:
        _message("JNU_MWP_PDK", str(error))
        return None
    return result


def _layer_value(layer_info, attr_name):
    """兼容读取 LayerInfo 的 layer/datatype 属性或方法。"""
    attr = getattr(layer_info, attr_name)
    return attr() if callable(attr) else attr


def _same_layer_info(left, right):
    """判断两个 LayerInfo 是否指向同一个 layer/datatype。"""
    return (
        _layer_value(left, "layer") == _layer_value(right, "layer")
        and _layer_value(left, "datatype") == _layer_value(right, "datatype")
    )


def _selected_path_on_allowed_layer(layout, obj):
    """判断选中的 Path 是否位于 Si 层或 Waveguide 层。

    某些 KLayout 版本或特殊选择对象可能读不到 obj.layer；此时保持宽松，
    仍允许该 Path 进入后续流程，避免 GUI 选择属性差异导致工具失效。
    """
    try:
        layer_index = obj.layer
        layer_info = layout.get_info(layer_index)
    except Exception:
        return True
    return _same_layer_info(layer_info, SI_LAYER) or _same_layer_info(layer_info, WG_LAYER)


def _selected_paths(view, layout):
    selection = []
    for obj in view.object_selection:
        if (
            (not obj.is_cell_inst())
            and obj.shape is not None
            and obj.shape.is_path()
            and _selected_path_on_allowed_layer(layout, obj)
        ):
            selection.append(obj)
    return selection


def _copy_integer_path(path):
    """复制整数Path，避免后续选择句柄失效时丢失原始几何。"""
    return pya.Path(
        [pya.Point(point.x, point.y) for point in path.each_point()],
        path.width,
        path.bgn_ext,
        path.end_ext,
    )


def _paths_equal(left, right):
    """比较两个Path的整数几何，用于在当前cell中回找原始图形。"""
    if left.width != right.width or left.bgn_ext != right.bgn_ext or left.end_ext != right.end_ext:
        return False
    left_points = list(left.each_point())
    right_points = list(right.each_point())
    if len(left_points) != len(right_points):
        return False
    return all(a == b for a, b in zip(left_points, right_points))


def _delete_selected_path_shape(obj, parent_cell, layer_index, original_path):
    """删除已转换的原始Path；选择句柄失效时回退为按几何匹配删除。"""
    try:
        shape = obj.shape
        if shape is not None:
            shape.delete()
            return True
    except Exception as error:
        _debug_log("direct shape.delete failed, fallback to erase: %s" % error)

    try:
        shapes = parent_cell.shapes(layer_index)
        for shape in shapes:
            if shape.is_path() and _paths_equal(shape.path, original_path):
                shapes.erase(shape)
                return True
    except Exception as error:
        _debug_log("fallback path erase failed: %s" % error)
    return False


def _validate_selected_paths(selected_paths, radius, dbu):
    for obj in selected_paths:
        path = obj.shape.path

        if hasattr(path, "is_manhattan_endsegments") and not path.is_manhattan_endsegments():
            raise RuntimeError("选中的 Path 首尾段必须是水平或垂直方向。")

        if hasattr(path, "is_manhattan") and not path.is_manhattan():
            raise RuntimeError("选中的 Path 必须是 Manhattan 路径（仅水平/垂直线段）。")

        radius_in_dbu = radius / dbu
        if hasattr(path, "radius_check") and not path.radius_check(radius_in_dbu, True):
            raise RuntimeError(
                "选中的 Path 某一段长度不足，无法放置弯曲半径 %.3f um。\n"
                "请增加 Path 转弯前后的直线段长度，或减小弯曲半径。" % radius
            )


def _canonical_manhattan_points(path):
    """返回去重、去同向共线点后的Manhattan点列。"""
    points = _dedupe_path_points(list(path.each_point()))
    result = []
    for point in points:
        result.append(point)
        while len(result) >= 3:
            a, b, c = result[-3:]
            ab = b - a
            bc = c - b
            if (ab.x == 0 and bc.x == 0 and ab.y * bc.y > 0) or (
                ab.y == 0 and bc.y == 0 and ab.x * bc.x > 0
            ):
                result.pop(-2)
            else:
                break
    return result


def _analyze_path_capacity(
    path, requested_radius_um, taper_um, dbu, path_number=1,
    start_taper_um=0.0, end_taper_um=0.0,
    start_bend_taper_um=None, end_bend_taper_um=None,
):
    """计算一条Path可容纳的统一最大半径，并列出不足线段。"""
    points = _canonical_manhattan_points(path)
    if len(points) < 2:
        raise ValueError("Path %d 的有效点数不足。" % path_number)
    for index in range(1, len(points)):
        delta = points[index] - points[index - 1]
        if delta.x != 0 and delta.y != 0:
            raise ValueError("Path %d 不是Manhattan路径。" % path_number)
        if index < len(points) - 1:
            following = points[index + 1] - points[index]
            cross = delta.x * following.y - delta.y * following.x
            if cross == 0:
                raise ValueError("Path %d 包含180度折返或无效转角。" % path_number)

    requested_radius_um = float(requested_radius_um)
    taper_um = max(0.0, float(taper_um))
    start_taper_um = max(0.0, float(start_taper_um))
    end_taper_um = max(0.0, float(end_taper_um))
    start_bend_taper_um = taper_um if start_bend_taper_um is None else max(0.0, float(start_bend_taper_um))
    end_bend_taper_um = taper_um if end_bend_taper_um is None else max(0.0, float(end_bend_taper_um))
    issues = []
    limits = []
    possible = True
    for index in range(len(points) - 1):
        p0, p1 = points[index], points[index + 1]
        length_um = p0.distance(p1) * dbu
        adjacent_bends = int(index > 0) + int(index < len(points) - 2)
        if adjacent_bends == 0:
            endpoint_taper = 0.0
            if index == 0:
                endpoint_taper += start_taper_um
            if index == len(points) - 2:
                endpoint_taper += end_taper_um
            if length_um + dbu < endpoint_taper:
                possible = False
                issues.append({
                    "path_number": path_number,
                    "segment_number": index + 1,
                    "start": p0,
                    "end": p1,
                    "length_um": length_um,
                    "required_um": endpoint_taper,
                    "max_radius_um": requested_radius_um,
                })
            continue
        bend_taper = 0.0
        if index > 0:
            bend_taper += end_bend_taper_um if index == len(points) - 2 else taper_um
        if index < len(points) - 2:
            bend_taper += start_bend_taper_um if index == 0 else taper_um
        max_radius = (length_um - bend_taper) / adjacent_bends
        limits.append(max_radius)
        required = adjacent_bends * requested_radius_um + bend_taper
        if length_um + dbu < required:
            issues.append({
                "path_number": path_number,
                "segment_number": index + 1,
                "start": p0,
                "end": p1,
                "length_um": length_um,
                "required_um": required,
                "max_radius_um": max_radius,
            })
    maximum_radius = min(limits) if limits else requested_radius_um
    quantized_maximum = math.floor((maximum_radius + 1e-12) / dbu) * dbu
    possible = possible and quantized_maximum > 0.010
    return {
        "points": points,
        "issues": issues,
        "maximum_radius_um": quantized_maximum,
        "actual_radius_um": min(requested_radius_um, quantized_maximum),
        "possible": possible,
    }


def _params_with_effective_radius(params, actual_radius_um, dbu=0.001):
    """把请求参数转换为实际可行半径参数，Euler保持Rmax/Rmin比例。"""
    adjusted = dict(params)
    actual_radius_um = float(actual_radius_um)
    if adjusted["bend_type"] == "Euler":
        requested = euler_Reff(adjusted["Euler_Rmax"], adjusted["Euler_Rmin"])
        scale = actual_radius_um / requested
        adjusted["Euler_Rmax"] *= scale
        adjusted["Euler_Rmin"] *= scale
    else:
        adjusted["radius"] = actual_radius_um
    derived = _calculate_waveguide_derived(
        adjusted["radius"], adjusted["bend_type"], adjusted["bezier"],
        adjusted["Euler_Rmax"], adjusted["Euler_Rmin"], dbu,
    )
    adjusted.update(derived)
    return adjusted


def _format_capacity_issues(analyses, requested_radius, dbu=0.001):
    """生成确认框和完成提示共用的问题线段说明。"""
    lines = ["请求半径：%.3f um" % requested_radius]
    for analysis in analyses:
        for issue in analysis["issues"]:
            p0, p1 = issue["start"], issue["end"]
            lines.append(
                "Path %d，线段 %d：(%.3f,%.3f)→(%.3f,%.3f) um，长度 %.3f um，可用半径 %.3f um"
                % (
                    issue["path_number"], issue["segment_number"],
                    p0.x * dbu, p0.y * dbu, p1.x * dbu, p1.y * dbu,
                    issue["length_um"], issue["max_radius_um"],
                )
            )
    return "\n".join(lines)


def _confirm_radius_reduction(details):
    """用Yes/Cancel确认是否按可行半径继续生成。"""
    message = pya.QMessageBox()
    message.setWindowTitle("JNU Path to Waveguide")
    message.setText("部分线段不足以容纳请求的弯曲半径。")
    message.setInformativeText(details + "\n\n是否降低半径并继续生成？")
    message.setStandardButtons(pya.QMessageBox.Yes | pya.QMessageBox.Cancel)
    message.setDefaultButton(pya.QMessageBox.Yes)
    return pya.QMessageBox_StandardButton(message.exec_()) == pya.QMessageBox.Yes


def _safe_cell_name(layout, base_name, current_cell=None):
    name = base_name
    index = 2
    current_index = None
    if current_cell is not None:
        try:
            current_index = current_cell.cell_index()
        except Exception:
            current_index = None

    while True:
        existing = layout.cell(name)
        if existing is None:
            return name
        try:
            if current_index is not None and existing.cell_index() == current_index:
                return name
        except Exception:
            pass
        name = "%s__%03d" % (base_name, index)
        index += 1


def _cell_display_title(cell):
    """读取 PCell 参数化显示名称，并兼容属性与方法两种绑定。"""
    title = getattr(cell, "display_title", "")
    title = title() if callable(title) else title
    return str(title or cell.name)


def _waveguide_signature_value(cell):
    """读取波导签名；旧文件可能只保存数字 GDS 属性。"""
    for key in (WAVEGUIDE_KIND_PROPERTY, WAVEGUIDE_KIND_GDS_PROPERTY):
        try:
            _ = cell.property(key)
        except Exception:
            pass
    for key in (RAW_PATH_PROPERTY, RAW_PATH_GDS_PROPERTY):
        try:
            value = cell.property(key)
        except Exception:
            value = None
        if not value:
            continue
        try:
            data = json.loads(str(value))
        except Exception:
            continue
        signature = data.get("jnu_waveguide_signature")
        if signature:
            return str(signature)
    return ""


def _claim_parameterized_cell_name(layout, waveguide_cell, pcell_id, declaration,
                                   pcell_params, signature):
    """用参数化名称命名 PCell；同名不同路径按 __NNN 追加确定性后缀。"""
    base_name = _cell_display_title(waveguide_cell)
    current = waveguide_cell
    suffix_index = 1

    while True:
        suffix = "" if suffix_index == 1 else "__%03d" % suffix_index
        candidate = base_name + suffix
        existing = layout.cell(candidate)
        if existing is None or existing.cell_index() == current.cell_index():
            if suffix:
                values = dict(pcell_params)
                values["name_suffix"] = suffix
                parameter_values = _local_pcell_parameter_values(declaration, values)
                candidate_index = layout.add_pcell_variant(pcell_id, parameter_values)
                candidate_cell = layout.cell(candidate_index)
                if candidate_cell is None:
                    raise RuntimeError("无法创建带重名后缀的内部 Waveguide PCell。")
                current = candidate_cell
            current.name = candidate
            return current

        if (
            existing.is_pcell_variant()
            and _waveguide_signature_value(existing) == str(signature)
        ):
            return existing
        suffix_index += 1


def _internal_waveguide_declaration(pcell_name):
    """创建工具内部波导 PCell 声明，不把它加入公开 JNULib。"""
    pymacros_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if pymacros_dir not in sys.path:
        sys.path.insert(0, pymacros_dir)
    if pcell_name == "Waveguide":
        from JNU_MWP_pcells.waveguide import Waveguide

        return Waveguide()
    if pcell_name == "Composite_Waveguide":
        from JNU_MWP_pcells.composite_waveguide import CompositeWaveguide

        return CompositeWaveguide()
    raise RuntimeError("未知的内部波导 PCell：%s" % pcell_name)


def _ensure_local_waveguide_pcell(layout, pcell_name):
    """在当前版图中按需注册波导 PCell，并返回声明及其本地 ID。"""
    declaration = layout.pcell_declaration(pcell_name)
    if declaration is None:
        layout.register_pcell(pcell_name, _internal_waveguide_declaration(pcell_name))
        declaration = layout.pcell_declaration(pcell_name)
    if declaration is None:
        raise RuntimeError("无法在当前版图中注册 %s PCell。" % pcell_name)

    pcell_id = layout.pcell_id(pcell_name)
    if pcell_id is None or int(pcell_id) < 0:
        raise RuntimeError("无法取得当前版图中的 %s PCell ID。" % pcell_name)
    return declaration, int(pcell_id)


def _local_pcell_parameter_values(declaration, values_by_name):
    """按声明顺序构造本地 PCell variant 所需的参数序列。"""
    return [
        values_by_name.get(parameter.name, parameter.default)
        for parameter in declaration.get_parameters()
    ]


def _waveguide_pcell_name(params):
    """根据页签模式返回需要按需注册的内部 PCell 名称。"""
    return "Composite_Waveguide" if params.get("mode") == "composite" else "Waveguide"


def _cleanup_new_local_waveguide_cells(layout, preexisting_cell_indices):
    """清理本轮预生成但未被任何实例引用的内部 PCell variant。"""
    if layout is None or preexisting_cell_indices is None:
        return 0
    removed = 0
    current_indices = [cell.cell_index() for cell in layout.each_cell()]
    for cell_index in current_indices:
        if cell_index in preexisting_cell_indices:
            continue
        cell = layout.cell(cell_index)
        if cell is None or not cell.is_pcell_variant():
            continue
        declaration = cell.pcell_declaration()
        declaration_name = declaration.name() if declaration is not None else ""
        if declaration_name not in INTERNAL_WAVEGUIDE_PCELL_NAMES:
            continue
        try:
            if any(True for _parent in cell.each_parent_inst()):
                continue
        except Exception:
            continue
        try:
            layout.delete_cell(cell_index)
            removed += 1
        except Exception:
            pass
    return removed


def _composite_recovery_metadata(params):
    """记录复合宽度参数；反向Path仍使用全局直波导宽度。"""
    if params.get("mode") != "composite":
        return None
    return {
        "straight_width_um": float(params["straight_width"]),
        "start_width_um": float(params["start_width"]),
        "end_width_um": float(params["end_width"]),
        "bend_width_um": float(params["bend_width"]),
        "taper_length_um": float(params["taper_length"]),
        "transition_length_um": float(params.get("transition_length", 2.0)),
    }


def _create_waveguide_cell(layout, dpath, params, index):
    """根据页签模式创建单一或复合宽度Waveguide PCell variant。"""
    _ = index  # 保留旧调用接口；PCell variant 的身份由参数集合决定。
    params = dict(params)
    bend_type = params["bend_type"]
    derived = _calculate_waveguide_derived(
        params["radius"],
        bend_type,
        params.get("bezier", 0.35),
        params.get("Euler_Rmax", 30.0),
        params.get("Euler_Rmin", 10.0),
        layout.dbu,
    )
    params.update(derived)

    is_composite = params.get("mode") == "composite"
    pcell_name = _waveguide_pcell_name(params)
    if is_composite:
        pcell_params = {
            "path": dpath,
            "straight_width": float(params["straight_width"]),
            "start_width": float(params["start_width"]),
            "end_width": float(params["end_width"]),
            "bend_width": float(params["bend_width"]),
            "taper_length": float(params["taper_length"]),
            "transition_length": float(params.get("transition_length", 2.0)),
            "radius": float(params["radius"]),
            "bend_type": bend_type,
            "bezier_k": float(params.get("bezier", 0.3)),
            "Euler_Rmax": float(params.get("Euler_Rmax", 30.0)),
            "Euler_Rmin": float(params.get("Euler_Rmin", 10.0)),
            "name_suffix": "",
        }
    else:
        pcell_params = {
            "path": dpath,
            "width": float(params["width"]),
            "radius": float(params["radius"]),
            "bend_type": bend_type,
            "bezier_k": float(params.get("bezier", 0.35)),
            "Euler_Rmax": float(params.get("Euler_Rmax", 30.0)),
            "Euler_Rmin": float(params.get("Euler_Rmin", 10.0)),
            "name_suffix": "",
        }
    declaration, pcell_id = _ensure_local_waveguide_pcell(layout, pcell_name)
    parameter_values = _local_pcell_parameter_values(declaration, pcell_params)
    cell_index = layout.add_pcell_variant(pcell_id, parameter_values)
    waveguide_cell = layout.cell(cell_index)
    if waveguide_cell is None:
        raise RuntimeError("当前版图中的 %s PCell 创建失败。" % pcell_name)
    try:
        if not waveguide_cell.is_pcell_variant():
            raise RuntimeError("创建结果不是 Waveguide PCell variant。")
    except AttributeError:
        pass
    waveguide_kind, signature = _waveguide_variant_signature(dpath, params, layout.dbu)
    waveguide_cell = _claim_parameterized_cell_name(
        layout, waveguide_cell, pcell_id, declaration, pcell_params, signature
    )

    recovery_metadata = _composite_recovery_metadata(params) or {}
    recovery_metadata.update({
        "jnu_waveguide_kind": waveguide_kind,
        "jnu_waveguide_signature": signature,
    })
    _store_waveguide_recovery_property(waveguide_cell, dpath, recovery_metadata)
    _mark_waveguide(waveguide_cell, waveguide_kind)
    return waveguide_cell


def path_to_waveguide():
    transaction_started = False
    layout = None
    preexisting_cell_indices = None
    try:
        _debug_log("Path to Waveguide: start")
        view, layout, cell = _active_context()

        selected_paths = _selected_paths(view, layout)
        _debug_log("selected paths: %d" % len(selected_paths))
        if not selected_paths:
            _message("JNU_MWP_PDK", "请先选中一个或多个 Path，再执行 Path to Waveguide。")
            return

        params = _show_waveguide_dialog(layout.dbu)
        if params is None:
            _debug_log("user cancelled")
            return
        _debug_log("params: %s" % params)

        pins = _find_pins_in_cell(cell, layout)
        _debug_log("optical pins for snap: %d" % len(pins))

        requested_radius = float(params["effective_radius"])
        taper_for_check = 0.0
        start_taper_for_check = 0.0
        end_taper_for_check = 0.0
        start_bend_taper_for_check = None
        end_bend_taper_for_check = None
        if params.get("mode") == "composite":
            straight_width = float(params["straight_width"])
            taper_length = float(params["taper_length"])
            transition_length = float(params.get("transition_length", 2.0))
            if abs(straight_width - float(params["bend_width"])) > layout.dbu:
                taper_for_check = taper_length + 2.0 * transition_length
            start_role = params.get("start_width_role", "straight")
            end_role = params.get("end_width_role", "straight")
            start_bend_taper_for_check = 0.0 if start_role == "bend" else taper_for_check
            end_bend_taper_for_check = 0.0 if end_role == "bend" else taper_for_check
            if taper_for_check > 0 and start_role == "bend" and end_role != "bend":
                start_taper_for_check = taper_length
            if taper_for_check > 0 and end_role == "bend" and start_role != "bend":
                end_taper_for_check = taper_length

        prepared = []
        invalid_summaries = []
        for index, obj in enumerate(selected_paths, 1):
            original = obj.shape.path
            original_copy = _copy_integer_path(original)
            preview = pya.Path(
                [pya.Point(point.x, point.y) for point in original.each_point()],
                original.width,
                original.bgn_ext,
                original.end_ext,
            )
            _snap_path_to_pins(preview, pins, layout.dbu)
            try:
                analysis = _analyze_path_capacity(
                    preview, requested_radius, taper_for_check, layout.dbu, index,
                    start_taper_for_check, end_taper_for_check,
                    start_bend_taper_for_check, end_bend_taper_for_check,
                )
            except ValueError as error:
                invalid_summaries.append("Path %d：%s" % (index, error))
                continue
            prepared.append((index, obj, preview, original_copy, analysis))

        if not prepared:
            message = "未找到可转换的 Manhattan Path。"
            if invalid_summaries:
                message += "\n\n已跳过：\n" + "\n".join(invalid_summaries[:12])
                if len(invalid_summaries) > 12:
                    message += "\n……另有 %d 条。" % (len(invalid_summaries) - 12)
                message += "\n\n请只选择原始水平/垂直折线路径；已圆滑的 Waveguide 或 S_Bend 应先执行 Waveguide to Path。"
            _message("JNU_MWP_PDK", message)
            return

        reducible = [analysis for _index, _obj, _path, _original, analysis in prepared if analysis["issues"] and analysis["possible"]]
        impossible = [analysis for _index, _obj, _path, _original, analysis in prepared if not analysis["possible"]]
        if reducible:
            details = _format_capacity_issues(reducible + impossible, requested_radius, layout.dbu)
            if impossible:
                details += "\n\n另有 %d 条Path即使降低半径也无法容纳固定过渡段，将保留原Path。" % len(impossible)
            if not _confirm_radius_reduction(details):
                return
        elif impossible:
            _message(
                "JNU_MWP_PDK",
                "以下Path无法容纳固定过渡段，将保留原Path：\n" +
                _format_capacity_issues(impossible, requested_radius, layout.dbu),
            )

        # 本地 PCell 的声明注册和首次 variant 几何生产都不能在活动的
        # KLayout Undo transaction 中执行，因此先完成所有 variant 预生成。
        _ensure_local_waveguide_pcell(layout, _waveguide_pcell_name(params))
        preexisting_cell_indices = {item.cell_index() for item in layout.each_cell()}
        conversions = []
        adjusted_summaries = []
        skipped_count = 0

        for index, obj, path, original_path, analysis in prepared:
            if not analysis["possible"]:
                skipped_count += 1
                continue

            actual_params = _params_with_effective_radius(
                params, analysis["actual_radius_um"], layout.dbu
            )
            port_width = (
                actual_params["straight_width"]
                if actual_params.get("mode") == "composite"
                else actual_params["width"]
            )
            source_dpath = _path_to_dpath(path, layout.dbu, port_width)
            if source_dpath is None:
                continue
            dpath, placement = _normalize_dpath_to_origin(source_dpath, layout.dbu)
            if dpath is None or placement is None:
                continue

            waveguide_cell = _create_waveguide_cell(layout, dpath, actual_params, index)
            if waveguide_cell is None:
                raise RuntimeError("无法根据第 %d 条 Path 生成 Waveguide cell。" % index)

            conversions.append(
                (index, obj, original_path, analysis, actual_params, dpath, placement, waveguide_cell)
            )
            if analysis["issues"]:
                segments = ", ".join(str(item["segment_number"]) for item in analysis["issues"])
                adjusted_summaries.append(
                    "Path %d（线段 %s）：半径 %.3f → %.3f um"
                    % (index, segments, requested_radius, analysis["actual_radius_um"])
                )

        if not conversions:
            if skipped_count:
                _message("JNU_MWP_PDK", "所有选中Path均无法容纳固定过渡段，未生成Waveguide。")
                return
            raise RuntimeError("选中的 Path 点数不足，未生成 Waveguide。")

        view.transaction("JNU Path to Waveguide")
        transaction_started = True
        created_count = 0

        for index, obj, original_path, analysis, actual_params, dpath, placement, waveguide_cell in conversions:

            waveguide_inst = cell.insert(
                pya.CellInstArray(waveguide_cell.cell_index(), placement)
            )
            # PCell variant 的 cell property 在写出 GDS 时会被展开器丢弃，
            # 因此在实例上同步同一份无图形恢复属性，保证文件重读可逆。
            _store_waveguide_recovery_property(
                waveguide_inst, dpath, _composite_recovery_metadata(actual_params)
            )
            _mark_waveguide(
                waveguide_inst,
                "composite" if actual_params.get("mode") == "composite" else "single",
            )
            try:
                layer_index = obj.layer
            except Exception:
                layer_index = layout.layer(SI_LAYER)
            if not _delete_selected_path_shape(obj, cell, layer_index, original_path):
                raise RuntimeError("无法删除第 %d 条原始Path，已取消本次转换。" % index)
            created_count += 1
            _debug_log("created cell: %s" % waveguide_cell.name)

        view.clear_object_selection()
        view.commit()
        transaction_started = False
        _debug_log("Path to Waveguide: done")
        if adjusted_summaries or skipped_count:
            summary = []
            if adjusted_summaries:
                summary.append("已降低半径：\n" + "\n".join(adjusted_summaries))
            if skipped_count:
                summary.append(
                    "因固定过渡段无法容纳而保留原Path：%d 条。\n%s"
                    % (skipped_count, _format_capacity_issues(impossible, requested_radius, layout.dbu))
                )
            if invalid_summaries:
                summary.append("已跳过非Manhattan Path：%d 条。\n%s" % (
                    len(invalid_summaries), "\n".join(invalid_summaries[:12])
                ))
            _message("JNU_MWP_PDK", "\n\n".join(summary))
        elif invalid_summaries:
            _message(
                "JNU_MWP_PDK",
                "已转换 %d 条Path；另跳过非Manhattan Path %d 条。\n%s"
                % (created_count, len(invalid_summaries), "\n".join(invalid_summaries[:12])),
            )
    except Exception as error:
        if transaction_started:
            try:
                view.cancel()
            except Exception:
                try:
                    view.commit()
                except Exception:
                    pass
        _cleanup_new_local_waveguide_cells(layout, preexisting_cell_indices)
        _debug_log("Path to Waveguide failed: %s" % error)
        _message("JNU_MWP_PDK", "Path to Waveguide 失败：\n%s" % error)

__all__ = [
    "path_to_waveguide",
    "TAB_SINGLE",
    "TAB_COMPOSITE",
    "TAB_USER_DEFINED",
    "TAB_LABELS",
    "_calculate_waveguide_derived",
    "_build_waveguide_cell_base_name",
    "_create_waveguide_cell",
    "_default_waveguide_params",
    "_normalize_editable_params",
    "_result_from_editable_params",
    "_add_user_preset",
    "_delete_user_presets",
    "_update_user_preset_name",
    "_update_user_preset_note",
    "_safe_cell_name",
    "_ensure_local_waveguide_pcell",
    "_store_waveguide_recovery_property",
    "_normalize_dpath_to_origin",
    "_waveguide_variant_signature",
    "_stable_waveguide_cell_name",
    "_mark_waveguide",
    "_mark_waveguide_container",
    "_is_waveguide_container_cell",
    "_get_or_create_waveguide_container",
]
