# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-06

"""Bezier 和 Euler 弯曲曲率计算工具。

参考文献：
- Bezier: Bahadori M, et al. Universal design of waveguide bends in silicon-on-insulator
  photonics platform[J]. Journal of Lightwave Technology, 2019, 37(13): 3044-3054.
- Euler: Jiang X, Wu H, Dai D. Low-loss and low-crosstalk multimode waveguide bend on
  silicon[J]. Optics Express, 2018, 26(13): 17680-17693.
"""

import math


def bezier_curvature_90deg(t, R0, k=0.35):
    """计算 90° Bezier 弯曲在参数 t 处的曲率。

    控制点（Bahadori 论文标准对称配置）：
    - P0 = (0, 0)
    - P1 = (R0*(1-k), 0)
    - P2 = (R0, R0*k)
    - P3 = (R0, R0)

    Args:
        t: 参数 [0, 1]
        R0: 弯曲盒尺寸（有效半径）
        k: Bezier 控制参数（形状因子 B）

    Returns:
        曲率值 κ (1/radius)
    """
    # 控制点
    p0x, p0y = 0.0, 0.0
    p1x, p1y = R0 * (1.0 - k), 0.0
    p2x, p2y = R0, R0 * k
    p3x, p3y = R0, R0

    # 一阶导数
    u = 1.0 - t
    dx = (3.0 * u**2 * (p1x - p0x) +
          6.0 * u * t * (p2x - p1x) +
          3.0 * t**2 * (p3x - p2x))
    dy = (3.0 * u**2 * (p1y - p0y) +
          6.0 * u * t * (p2y - p1y) +
          3.0 * t**2 * (p3y - p2y))

    # 二阶导数
    ddx = (6.0 * u * (p2x - 2.0 * p1x + p0x) +
           6.0 * t * (p3x - 2.0 * p2x + p1x))
    ddy = (6.0 * u * (p2y - 2.0 * p1y + p0y) +
           6.0 * t * (p3y - 2.0 * p2y + p1y))

    # 曲率公式: κ = |x'y'' - y'x''| / (x'² + y'²)^(3/2)
    cross = abs(dx * ddy - dy * ddx)
    speed2 = dx**2 + dy**2

    if cross <= 1e-15 or speed2 <= 1e-15:
        return 0.0

    return cross / (speed2**1.5)


def bezier_Rmax_Rmin(R0, k=0.35, samples=512):
    """计算 Bezier 90° 弯曲的最大和最小曲率半径。

    对于对称 Bezier 弯曲：
    - Rmax 通常出现在端点（曲率最小）
    - Rmin 通常出现在中间（曲率最大）

    Args:
        R0: 弯曲盒尺寸（有效半径）
        k: Bezier 控制参数
        samples: 采样点数

    Returns:
        (Rmax, Rmin) - 最大和最小曲率半径
    """
    if R0 <= 0:
        return 0.0, 0.0

    max_curvature = 0.0
    min_curvature = float('inf')

    for i in range(samples + 1):
        t = i / samples
        curvature = bezier_curvature_90deg(t, R0, k)

        if curvature > 1e-12:
            max_curvature = max(max_curvature, curvature)
            min_curvature = min(min_curvature, curvature)

    Rmax = 1.0 / min_curvature if min_curvature > 1e-12 else float('inf')
    Rmin = 1.0 / max_curvature if max_curvature > 1e-12 else 0.0

    return Rmax, Rmin


def euler_curvature_half(s, R_max, R_min, L0):
    """计算 Euler 弯曲单段（45°）在弧长 s 处的曲率。

    曲率沿弧长线性分布：κ(s) = s/A² + 1/R_max
    其中 A = sqrt(L0 / (1/R_min - 1/R_max))

    Args:
        s: 弧长 [0, L0]
        R_max: 端点最大曲率半径
        R_min: 中点最小曲率半径
        L0: 单段弧长

    Returns:
        曲率值 κ (1/radius)
    """
    if R_max <= 0 or R_min <= 0 or R_min >= R_max:
        return 1.0 / R_max if R_max > 0 else 0.0

    delta_kappa = 1.0 / R_min - 1.0 / R_max
    if delta_kappa <= 1e-12:
        return 1.0 / R_max

    A2 = L0 / delta_kappa
    kappa = s / A2 + 1.0 / R_max
    return kappa


def euler_Reff(R_max, R_min, samples=1000):
    """计算 Euler 90° 弯曲的等效半径（数值积分）。

    R_eff = 弯曲终点 x 坐标

    Args:
        R_max: 端点最大曲率半径
        R_min: 中点最小曲率半径
        samples: 积分采样点数

    Returns:
        R_eff - 等效半径
    """
    if R_max <= 0 or R_min <= 0 or R_min >= R_max:
        return R_max if R_max > 0 else 0.0

    # 估算总弧长（用平均曲率近似）
    kappa_avg = 0.5 * (1.0 / R_max + 1.0 / R_min)
    L_total = (math.pi / 2.0) / kappa_avg if kappa_avg > 0 else math.pi * R_max / 2.0

    # 迭代求解使总转角 = π/2 的弧长
    for _ in range(20):
        L0 = L_total / 2.0
        ds = L0 / samples

        # 数值积分计算单段总转角
        theta_total = 0.0
        for i in range(samples):
            s = i * ds
            kappa = euler_curvature_half(s, R_max, R_min, L0)
            theta_total += kappa * ds

        # 两段拼接，总转角应为 π/2
        total_theta = 2.0 * theta_total

        if abs(total_theta - math.pi / 2.0) < 1e-7:
            break

        # 调整弧长
        L_total *= (math.pi / 2.0) / total_theta if total_theta > 0 else 1.0

    # 数值积分计算 x 坐标（第一段）
    L0 = L_total / 2.0
    ds = L0 / samples
    x1, y1, theta = 0.0, 0.0, 0.0

    for i in range(samples):
        s = i * ds
        kappa = euler_curvature_half(s, R_max, R_min, L0)
        x1 += math.cos(theta) * ds
        y1 += math.sin(theta) * ds
        theta += kappa * ds

    # 第一段终点
    x_end, y_end = x1, y1

    # 第二段关于中点对称拼接
    # 变换公式：x' = x_end + y_end - y; y' = y_end + x_end - x
    # 终点坐标：x_final = x_end + y_end - 0 = x_end + y_end
    R_eff = x_end + y_end

    return R_eff


def euler_curve_points(R_max, R_min, turn_angle, samples=100):
    """生成 Euler 弯曲的局部中心线点列。

    使用改进型 Euler 曲线：曲率沿弧长线性分布。
    两段 45° 曲线关于中点对称拼接。

    Args:
        R_max: 端点最大曲率半径
        R_min: 中点最小曲率半径
        turn_angle: 转角（弧度），通常为 π/2
        samples: 单段采样点数

    Returns:
        [(x, y), ...] - 点列，起点 (0, 0)
    """
    if R_max <= 0 or R_min <= 0 or R_min >= R_max:
        # 退化为直线
        return [(0.0, 0.0)]

    # 估算总弧长
    kappa_avg = 0.5 * (1.0 / R_max + 1.0 / R_min)
    L_total = turn_angle / kappa_avg if kappa_avg > 0 else turn_angle * R_max

    # 迭代求解使总转角 = turn_angle 的弧长
    for _ in range(20):
        L0 = L_total / 2.0
        ds = L0 / samples

        # 数值积分计算单段总转角
        theta_total = 0.0
        for i in range(samples):
            s = i * ds
            kappa = euler_curvature_half(s, R_max, R_min, L0)
            theta_total += kappa * ds

        total_theta = 2.0 * theta_total

        if abs(total_theta - turn_angle) < 1e-7:
            break

        L_total *= turn_angle / total_theta if total_theta > 0 else 1.0

    # 生成第一段点
    L0 = L_total / 2.0
    ds = L0 / samples
    pts = [(0.0, 0.0)]
    x, y, theta = 0.0, 0.0, 0.0

    for i in range(samples):
        s = i * ds
        kappa = euler_curvature_half(s, R_max, R_min, L0)
        x += math.cos(theta) * ds
        y += math.sin(theta) * ds
        pts.append((x, y))
        theta += kappa * ds

    # 第一段终点
    x_end, y_end = x, y

    # 第二段关于中点对称拼接
    for i in range(samples - 1, -1, -1):
        # 逆序取第一段点，做轴对称反射
        px, py = pts[i]
        # 变换：x' = x_end + y_end - y; y' = y_end + x_end - x
        new_x = x_end + y_end - py
        new_y = y_end + x_end - px
        pts.append((new_x, new_y))

    return pts


__all__ = [
    "bezier_curvature_90deg",
    "bezier_Rmax_Rmin",
    "euler_curvature_half",
    "euler_Reff",
    "euler_curve_points",
]
