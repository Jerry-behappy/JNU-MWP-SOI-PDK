# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-06

"""JNU 自适应采样计算工具。"""

import math

AUTO_SAMPLE_COUNT = 0
LEGACY_FIXED_SAMPLE_COUNT = 1000
MIN_POINTS_PER_90 = 4


def default_sample_count(value, legacy_default=LEGACY_FIXED_SAMPLE_COUNT):
    """把旧版固定默认值迁移为 Auto，同时兼容用户手动输入。"""
    try:
        count = int(value)
    except Exception:
        return AUTO_SAMPLE_COUNT
    if count == int(legacy_default):
        return AUTO_SAMPLE_COUNT
    return max(AUTO_SAMPLE_COUNT, count)


def points_per_circle(radius_um, dbu=0.001):
    """按不超过半个 DBU 的弦高误差计算整圆采样点数。"""
    radius = abs(float(radius_um))
    if radius <= 0:
        return MIN_POINTS_PER_90 * 4
    if radius <= 1.0:
        return 10
    dbu_val = float(dbu) if dbu else 0.001
    error = abs(dbu_val) / 2.0
    if error <= 0:
        error = 0.0005
    ratio = 1.0 - error / radius
    ratio = max(-1.0, min(0.999999999999999, ratio))
    return int(math.ceil(math.pi / math.acos(ratio)))


def points_per_90(radius_um, dbu=0.001):
    """计算 90 度弯曲采样点数。"""
    return max(MIN_POINTS_PER_90, int(math.ceil(points_per_circle(radius_um, dbu) / 4.0)))


def effective_points_per_90(value, radius_um, dbu=0.001, min_points=MIN_POINTS_PER_90):
    """计算实际 90 度弯曲采样点数。value<=0 表示按半径自动计算。"""
    try:
        count = int(value)
    except Exception:
        count = AUTO_SAMPLE_COUNT
    if count <= 0:
        return max(int(min_points), points_per_90(radius_um, dbu))
    return max(int(min_points), count)


def effective_arc_points(value, radius_um, angle_rad, dbu=0.001, min_points=MIN_POINTS_PER_90):
    """根据圆弧角度计算实际采样点数。value<=0 表示自动。"""
    try:
        count = int(value)
    except Exception:
        count = AUTO_SAMPLE_COUNT
    if count > 0:
        return max(int(min_points), count)
    fraction = abs(float(angle_rad)) / (2.0 * math.pi)
    auto_count = int(math.ceil(points_per_circle(radius_um, dbu) * fraction))
    return max(int(min_points), auto_count)
