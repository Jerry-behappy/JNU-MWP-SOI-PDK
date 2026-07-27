# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

# JNU_MWP_PDK 的参数化 Waveguide PCell。
# 该 PCell 不依赖 WAVEGUIDES.xml，而是直接使用 path、width、radius、bend_type 参数生成波导。

import json
import math
import os
import sys

import pya

try:
    from .pcell_defaults import default_choice, default_float, save_pcell_defaults
except ImportError:
    PCELL_DIR = os.path.dirname(os.path.abspath(__file__))
    if PCELL_DIR not in sys.path:
        sys.path.insert(0, PCELL_DIR)
    from pcell_defaults import default_choice, default_float, save_pcell_defaults

# 弯曲工具模块位于 tools 目录（在 JNU_MWP_PDK 根目录下）
PYMACROS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PYMACROS_DIR not in sys.path:
    sys.path.insert(0, PYMACROS_DIR)

from JNU_MWP_tools.core.bend_sampling import AUTO_SAMPLE_COUNT, effective_points_per_90
from JNU_MWP_tools.core.bend_curvature import bezier_Rmax_Rmin, euler_Reff
from JNU_MWP_tools.core.path_geometry import insert_centerline_polygons

# 确保 pymacros 目录在 sys.path 中，以便从 bend_90deg 导入公共弯曲点生成函数
_PYMACROS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PYMACROS_DIR not in sys.path:
    sys.path.insert(0, _PYMACROS_DIR)

from JNU_MWP_pcells.bend_90deg import (
    _normalize_bend_type,
    corner_points,
)


SI_LAYER = pya.LayerInfo(1, 0)          # Si 波导实体层。
WG_LAYER = pya.LayerInfo(1, 99)         # Waveguide 引导路径层。
PIN_LAYER = pya.LayerInfo(1, 10)        # PinRec 端口识别层。
DEVREC_LAYER = pya.LayerInfo(68, 0)     # DevRec 器件识别层。
TEXT_LAYER = pya.LayerInfo(10, 0)       # Text 文字层。

PCELL_NAME = "Waveguide"
SI_LAYER = pya.LayerInfo(1, 0)       # Si 波导实体层。
WG_LAYER = pya.LayerInfo(1, 99)      # Waveguide 原始路径层。
PIN_LAYER = pya.LayerInfo(1, 10)     # PinRec 端口识别层。
DEVREC_LAYER = pya.LayerInfo(68, 0)  # DevRec 器件识别层。
TEXT_LAYER = pya.LayerInfo(10, 0)    # Text 参数标注层。
RAW_PATH_PROPERTY = "JNU_MWP_raw_manhattan_path"
RAW_PATH_GDS_PROPERTY = 126
DEFAULT_WIDTH = 0.5
DEFAULT_RADIUS = 20.0
DEVREC_SIDE_CLEARANCE_UM = 1.0
EULER_SAMPLES = 28
NORMAL_SAMPLES = 24
DEFAULT_NPOINTS = AUTO_SAMPLE_COUNT
DEFAULT_BEZIER_K = 0.35
DEFAULT_EULER_RMAX = 30.0
DEFAULT_EULER_RMIN = 10.0


def _ensure_tools_path():
    """保证 pymacros 父目录可用于导入分类后的工具子包。"""
    pymacros_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if pymacros_dir not in sys.path:
        sys.path.insert(0, pymacros_dir)


def _to_itype(value, dbu):
    """把微米单位的浮点数转换为 KLayout 数据库整数单位。"""
    return int(round(float(value) / dbu))


def _unit_step(delta):
    """把任意线段方向压成 Manhattan 单位方向。"""
    if abs(delta.x) >= abs(delta.y):
        return pya.Point(1 if delta.x >= 0 else -1, 0)
    return pya.Point(0, 1 if delta.y >= 0 else -1)


def _distance(p1, p2):
    """计算两个数据库坐标点之间的欧氏距离。"""
    return math.hypot(p2.x - p1.x, p2.y - p1.y)


def _dedupe_points(points):
    """移除连续重复点，避免 KLayout Path 出现零长度段。"""
    clean = []
    for point in points:
        point = pya.Point(int(round(point.x)), int(round(point.y)))
        if not clean or clean[-1] != point:
            clean.append(point)
    return clean


def _left_normal(unit):
    """返回 Manhattan 单位方向的左法向。"""
    return pya.Point(-unit.y, unit.x)


def _local_to_global(start, unit_in, turn_sign, x, y):
    """把标准左转局部曲线坐标映射到实际拐角坐标。"""
    normal = _left_normal(unit_in)
    return pya.Point(
        int(round(start.x + unit_in.x * x + normal.x * turn_sign * y)),
        int(round(start.y + unit_in.y * x + normal.y * turn_sign * y)),
    )


def _smooth_path_points(points, radius, bend_type, npoints=64, bezier_k=0.0, euler_Rmax=DEFAULT_EULER_RMAX, euler_Rmin=DEFAULT_EULER_RMIN):
    """把 Manhattan 折线路径转换为带弯曲采样点的中心线。"""
    points = _dedupe_points(points)
    if len(points) < 3 or radius <= 0:
        return points

    smoothed = [points[0]]
    last_corner = len(points) - 2

    for idx in range(1, len(points) - 1):
        prev_pt = points[idx - 1]
        corner = points[idx]
        next_pt = points[idx + 1]

        unit_in = _unit_step(corner - prev_pt)
        unit_out = _unit_step(next_pt - corner)
        cross = unit_in.x * unit_out.y - unit_in.y * unit_out.x

        # 非 90 度拐角不强行改造，直接保留原始点。
        if cross == 0:
            smoothed.append(corner)
            continue

        dist_in = _distance(prev_pt, corner)
        dist_out = _distance(corner, next_pt)
        if len(points) == 3:
            use_radius = min(radius, dist_in, dist_out)
        elif idx == 1:
            use_radius = min(radius, dist_in, dist_out / 2)
        elif idx == last_corner:
            use_radius = min(radius, dist_in / 2, dist_out)
        else:
            use_radius = min(radius, dist_in / 2, dist_out / 2)

        if use_radius <= 1:
            smoothed.append(corner)
            continue

        start = pya.Point(
            int(round(corner.x - unit_in.x * use_radius)),
            int(round(corner.y - unit_in.y * use_radius)),
        )
        smoothed.append(start)

        local_pts = corner_points(use_radius, bend_type, npoints, bezier_k, euler_Rmax, euler_Rmin)
        for x, y in local_pts[1:]:
            smoothed.append(_local_to_global(start, unit_in, 1 if cross > 0 else -1, x, y))

    smoothed.append(points[-1])
    return _dedupe_points(smoothed)


def _pin_direction(from_point, to_point):
    """根据从相邻点指向端点的方向，返回 SiEPIC pin 朝向角度。"""
    delta = from_point - to_point
    if abs(delta.x) >= abs(delta.y):
        return 0 if delta.x > 0 else 180
    return 90 if delta.y > 0 else 270


def _path_length_um(points, dbu):
    """计算中心线长度，单位为微米。"""
    length = 0.0
    for idx in range(1, len(points)):
        length += _distance(points[idx - 1], points[idx]) * dbu
    return length


def _path_ext_um(path, attr_name, dbu):
    """兼容读取 Path 的端点延长量，并转换为微米。"""
    try:
        attr = getattr(path, attr_name)
        value = attr() if callable(attr) else attr
        return float(value) * dbu
    except Exception:
        return 0.0


def _dpath_to_integer_path(dpath, dbu):
    """显式量化 DPath，避免部分 KLayout 版本的 to_itype 丢失端部延伸。"""
    points = [
        pya.Point(
            int(round(point.x / dbu)),
            int(round(point.y / dbu)),
        )
        for point in dpath.each_point()
    ]
    bgn_ext_um = _path_ext_um(dpath, "bgn_ext", 1.0)
    end_ext_um = _path_ext_um(dpath, "end_ext", 1.0)
    return pya.Path(
        points,
        max(1, _to_itype(dpath.width, dbu)),
        _to_itype(bgn_ext_um, dbu),
        _to_itype(end_ext_um, dbu),
    )


def _store_raw_manhattan_path(cell, raw_path, raw_points, width_dbu, dbu, extra=None):
    """把原始 Manhattan 输入写入无图形属性，作为 PCell 参数的读取后备。"""
    data = {
        "width_um": float(width_dbu) * dbu,
        "points_um": [[point.x * dbu, point.y * dbu] for point in raw_points],
        "bgn_ext_um": _path_ext_um(raw_path, "bgn_ext", dbu),
        "end_ext_um": _path_ext_um(raw_path, "end_ext", dbu),
    }
    if isinstance(extra, dict):
        data.update(extra)
    try:
        value = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        cell.set_property(RAW_PATH_PROPERTY, value)
        # 数字属性号是 GDSII 保存 cell property 的标准载体。
        cell.set_property(RAW_PATH_GDS_PROPERTY, value)
    except Exception:
        # 某些旧版 KLayout 若不支持 cell property，也不能影响波导实体生成。
        pass


def draw_waveguide_geometry(cell, layout, dpath, width, radius, bend_type, npoints=None, bezier_k=DEFAULT_BEZIER_K, euler_Rmax=DEFAULT_EULER_RMAX, euler_Rmin=DEFAULT_EULER_RMIN):
    """在指定 cell 中绘制一条 JNU 波导，并返回波导中心线长度。

    Waveguide PCell 通过该函数生成 Si、DevRec、PinRec 和 Text；菜单转换
    先创建真实 PCell variant，再由 PCell 的生产流程调用本函数。

    npoints: 弯曲采样点数。若为 None 或 0，则按半径和 dbu 自动计算。
    bezier_k: Bezier 弯曲控制系数，仅对 Bezier 类型生效。
    euler_Rmax: Euler 弯曲端点最大曲率半径，仅对 Euler 类型生效。
    euler_Rmin: Euler 弯曲中点最小曲率半径，仅对 Euler 类型生效。
    """
    dbu = layout.dbu
    raw_path = _dpath_to_integer_path(dpath, dbu)
    raw_points = _dedupe_points(list(raw_path.each_point()))
    if len(raw_points) < 2:
        return 0.0

    bend_type = _normalize_bend_type(bend_type)
    effective_radius = (
        euler_Reff(euler_Rmax, euler_Rmin)
        if bend_type == "Euler"
        else float(radius)
    )
    radius_dbu = _to_itype(effective_radius, dbu)
    width_dbu = max(1, _to_itype(width, dbu))
    devrec_clearance_dbu = max(0, _to_itype(DEVREC_SIDE_CLEARANCE_UM, dbu))
    devrec_width_dbu = width_dbu + 2 * devrec_clearance_dbu
    npoints = effective_points_per_90(
        DEFAULT_NPOINTS if npoints is None else npoints,
        effective_radius,
        dbu,
    )

    centerline = _smooth_path_points(raw_points, radius_dbu, bend_type, npoints, bezier_k, euler_Rmax, euler_Rmin)
    if len(centerline) < 2:
        return 0.0

    si_layer = layout.layer(SI_LAYER)
    devrec_layer = layout.layer(DEVREC_LAYER)
    text_layer = layout.layer(TEXT_LAYER)
    pin_layer = layout.layer(PIN_LAYER)

    # 原始 Manhattan Path 由 PCell 的 TypeShape 参数保存；cell property 只作为
    # GDS 重读后的无图形恢复后备，不在任何物理图层重复绘制引导 Path。
    _store_raw_manhattan_path(cell, raw_path, raw_points, width_dbu, dbu)
    insert_centerline_polygons(cell, si_layer, centerline, width_dbu)
    # DevRec 沿波导中心线两侧各扩展固定净空，覆盖完整 Si 实体并留出器件识别边界。
    insert_centerline_polygons(cell, devrec_layer, centerline, devrec_width_dbu)

    waveguide_length = round(_path_length_um(centerline, dbu), 3)

    # 生成 SiEPIC 可识别的两个光学端口。
    _ensure_tools_path()
    from JNU_MWP_tools.core.make_pin import make_pin

    make_pin(
        cell,
        "opt1",
        centerline[0],
        width_dbu,
        pin_layer,
        _pin_direction(centerline[0], centerline[1]),
    )
    make_pin(
        cell,
        "opt2",
        centerline[-1],
        width_dbu,
        pin_layer,
        _pin_direction(centerline[-1], centerline[-2]),
    )

    # 在 Text 层记录关键参数，方便用户在版图中追溯波导设置。
    text = pya.Text(
        "Waveguide width=%.3fum radius=%.3fum bend=%s length=%.3fum"
        % (width, radius, bend_type, waveguide_length),
        pya.Trans(pya.Trans.R0, centerline[0].x, centerline[0].y),
    )
    shape = cell.shapes(text_layer).insert(text)
    shape.text_dsize = max(0.1, width * 0.5)

    return waveguide_length


class Waveguide(pya.PCellDeclarationHelper):
    """JNU 波导 PCell：由 Path to Waveguide 功能自动实例化。"""

    def __init__(self, technology_name=""):
        super(Waveguide, self).__init__()

        # 保留 technology_name 参数兼容旧调用，但不再主动设置 layout technology。
        self.technology_name = technology_name
        self.cellName = "Waveguide"

        self.param(
            "path",
            self.TypeShape,
            "Path",
            default=pya.DPath(
                [pya.DPoint(0, 0), pya.DPoint(20, 0), pya.DPoint(20, 20)],
                DEFAULT_WIDTH,
            ),
        )
        self.param(
            "width",
            self.TypeDouble,
            "Waveguide width",
            unit="um",
            default=default_float(PCELL_NAME, "width", DEFAULT_WIDTH),
        )
        self.param(
            "radius",
            self.TypeDouble,
            "Bend radius",
            unit="um",
            default=default_float(PCELL_NAME, "radius", DEFAULT_RADIUS),
        )

        bend_type_default = _normalize_bend_type(
            default_choice(
                PCELL_NAME,
                "bend_type",
                "Circular",
                ("Circular", "Bezier", "Euler"),
            )
        )

        bend_param = self.param(
            "bend_type",
            self.TypeList,
            "Bend type",
            default=bend_type_default,
        )
        for choice in ("Circular", "Bezier", "Euler"):
            bend_param.add_choice(choice, choice)

        # Bezier 弯曲参数
        self.bezier_k_param = self.param(
            "bezier_k",
            self.TypeDouble,
            "Bezier shape factor",
            default=default_float(PCELL_NAME, "bezier_k", DEFAULT_BEZIER_K),
        )

        # Euler 弯曲参数
        self.Euler_Rmax_param = self.param(
            "Euler_Rmax",
            self.TypeDouble,
            "Euler max radius (endpoint)",
            unit="um",
            default=default_float(PCELL_NAME, "Euler_Rmax", DEFAULT_EULER_RMAX),
        )
        self.Euler_Rmin_param = self.param(
            "Euler_Rmin",
            self.TypeDouble,
            "Euler min radius (midpoint)",
            unit="um",
            default=default_float(PCELL_NAME, "Euler_Rmin", DEFAULT_EULER_RMIN),
        )

        # 内部后缀只用于区分参数化显示名称相同、但路径形状不同的 PCell variant。
        self.name_suffix_param = self.param(
            "name_suffix",
            self.TypeString,
            "Internal name suffix",
            default="",
        )
        try:
            self.name_suffix_param.hidden = True
        except Exception:
            pass

        # 只读派生参数统一放在全部可编辑参数之后。
        self.Bezier_Rmax_param = self.param(
            "Bezier_Rmax",
            self.TypeDouble,
            "Bezier max radius [uneditable]",
            unit="um",
            default=0.0,
            readonly=True,
        )
        self.Bezier_Rmin_param = self.param(
            "Bezier_Rmin",
            self.TypeDouble,
            "Bezier min radius [uneditable]",
            unit="um",
            default=0.0,
            readonly=True,
        )
        self.Euler_Reff_param = self.param(
            "Euler_Reff",
            self.TypeDouble,
            "Euler effective radius [uneditable]",
            unit="um",
            default=0.0,
            readonly=True,
        )

        # 根据默认弯曲类型，设置初始隐藏状态
        try:
            self.bezier_k_param.hidden = bend_type_default != "Bezier"
            self.Bezier_Rmax_param.hidden = bend_type_default != "Bezier"
            self.Bezier_Rmin_param.hidden = bend_type_default != "Bezier"
            self.Euler_Rmax_param.hidden = bend_type_default != "Euler"
            self.Euler_Rmin_param.hidden = bend_type_default != "Euler"
            self.Euler_Reff_param.hidden = bend_type_default != "Euler"
        except Exception:
            pass

    def display_text_impl(self):
        """在实例属性中显示全部用户参数（排除弯曲点数、波导层）。"""
        length = getattr(self, "waveguide_length", 0)
        suffix = str(getattr(self, "name_suffix", "") or "")
        if self.bend_type == "Bezier":
            return "Waveguide_w%.3f_R%.3f_%s_B%.3f_L%.3f%s" % (
                self.width, self.radius, self.bend_type,
                self.bezier_k, length, suffix,
            )
        elif self.bend_type == "Euler":
            return "Waveguide_w%.3f_Rmax%.3f_Rmin%.3f_%s_L%.3f%s" % (
                self.width, self.Euler_Rmax, self.Euler_Rmin,
                self.bend_type, length, suffix,
            )
        return "Waveguide_w%.3f_R%.3f_%s_L%.3f%s" % (
            self.width, self.radius, self.bend_type, length, suffix,
        )

    def coerce_parameters_impl(self):
        """约束参数范围，避免生成零宽或负半径波导，并更新曲率参数。"""
        self.width = max(0.001, float(self.width))
        self.radius = max(0.0, float(self.radius))
        self.bend_type = _normalize_bend_type(self.bend_type)

        # 约束 Bezier 参数
        self.bezier_k = max(0.05, min(0.95, float(self.bezier_k)))

        # 约束 Euler 参数
        self.Euler_Rmax = max(0.001, float(self.Euler_Rmax))
        self.Euler_Rmin = max(0.001, float(self.Euler_Rmin))
        # 确保 Rmax > Rmin
        if self.Euler_Rmin >= self.Euler_Rmax:
            self.Euler_Rmin = self.Euler_Rmax * 0.5

        # 计算并更新曲率参数（保留三位小数）
        if self.bend_type == "Bezier":
            Rmax, Rmin = bezier_Rmax_Rmin(self.radius, self.bezier_k)
            self.Bezier_Rmax = round(Rmax, 3)
            self.Bezier_Rmin = round(Rmin, 3)
        elif self.bend_type == "Euler":
            Reff = euler_Reff(self.Euler_Rmax, self.Euler_Rmin)
            self.Euler_Reff = round(Reff, 3)

        save_pcell_defaults(self, PCELL_NAME, ["width", "radius", "bend_type", "bezier_k", "Euler_Rmax", "Euler_Rmin"])

    def can_create_from_shape_impl(self):
        """允许 KLayout 从选中的 Path 直接创建本 PCell。"""
        return self.shape.is_path()

    def transformation_from_shape_impl(self):
        """从 Path 创建 PCell 时不额外引入位移或旋转。"""
        return pya.Trans(pya.Trans.R0, 0, 0)

    def parameters_from_shape_impl(self):
        """把 KLayout 选中的 Path 转成 PCell 参数。"""
        path = self.shape.path
        self.path = path.to_dtype(self.layout.dbu)
        self.width = max(0.001, path.width * self.layout.dbu)

    def callback(self, layout, name, states):
        """保持 KLayout 标准回调流程。"""
        try:
            self._jnu_callback_dbu = layout.dbu
        except Exception:
            self._jnu_callback_dbu = 0.001
        return super(Waveguide, self).callback(layout, name, states)

    def _state_value(self, state):
        """兼容读取 PCellParameterState.value 的属性/方法形式。"""
        try:
            value = state.value
            return value() if callable(value) else value
        except Exception:
            return None

    def _state_to_string(self, state):
        """从 GUI 参数状态读取字符串值。"""
        val = self._state_value(state)
        return str(val) if val is not None else ""

    def callback_impl(self, name):
        """用户切换 bend_type 时，动态显示/隐藏 Bezier/Euler 参数。"""
        try:
            # 在 callback_impl 中，self.bend_type 等是 PCellParameterState，不是值
            bend_type = self._state_to_string(self.bend_type).lower()
            is_bezier = bend_type == "bezier"
            is_euler = bend_type == "euler"

            self.bezier_k.visible = is_bezier
            self.Bezier_Rmax.visible = is_bezier
            self.Bezier_Rmin.visible = is_bezier

            self.Euler_Rmax.visible = is_euler
            self.Euler_Rmin.visible = is_euler
            self.Euler_Reff.visible = is_euler

        except Exception:
            # 回退：通过声明对象的 hidden 属性控制可见性
            try:
                bend_type = _normalize_bend_type(self.bend_type)
                self.bezier_k_param.hidden = bend_type != "Bezier"
                self.Bezier_Rmax_param.hidden = bend_type != "Bezier"
                self.Bezier_Rmin_param.hidden = bend_type != "Bezier"
                self.Euler_Rmax_param.hidden = bend_type != "Euler"
                self.Euler_Rmin_param.hidden = bend_type != "Euler"
                self.Euler_Reff_param.hidden = bend_type != "Euler"
            except Exception:
                pass

    def produce_impl(self):
        """根据参数绘制波导实体、DevRec 和 PinRec；引导路径保存在 PCell 参数中。"""
        self.waveguide_length = draw_waveguide_geometry(
            self.cell,
            self.layout,
            self.path,
            self.width,
            self.radius,
            self.bend_type,
            bezier_k=self.bezier_k,
            euler_Rmax=self.Euler_Rmax,
            euler_Rmin=self.Euler_Rmin,
        )


__all__ = [
    "Waveguide", "draw_waveguide_geometry", "RAW_PATH_PROPERTY",
    "_dpath_to_integer_path",
]
