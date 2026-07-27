# -*- coding: utf-8 -*-
# 创建者: Codex
# 时间: 2026-07

"""导出 JNU_MWP_PDK Euler 90° 弯曲中心线 CSV。

本脚本是独立建模辅助工具，不依赖 KLayout 的 pya 模块。公式镜像
JNU_MWP_tools.core.bend_curvature 与 bend_90deg.py 的 Euler 路径生成逻辑，
便于把中心线导入 FDTD/EME 环境。
"""

import argparse
import csv
import math
from pathlib import Path


PORT_STRAIGHT_UM = 0.010
MIN_POINTS_PER_90 = 4


def euler_curvature_half(s, r_max, r_min, l0):
    """计算 45° 半段 Euler 曲线在弧长 s 处的曲率。"""
    if r_max <= 0 or r_min <= 0 or r_min >= r_max:
        return 1.0 / r_max if r_max > 0 else 0.0
    delta_kappa = 1.0 / r_min - 1.0 / r_max
    if delta_kappa <= 1e-12:
        return 1.0 / r_max
    a2 = l0 / delta_kappa
    return s / a2 + 1.0 / r_max


def solve_total_length(r_max, r_min, turn_angle, samples):
    """迭代求解使总转角等于 turn_angle 的 Euler 总弧长。"""
    kappa_avg = 0.5 * (1.0 / r_max + 1.0 / r_min)
    total_length = turn_angle / kappa_avg if kappa_avg > 0 else turn_angle * r_max
    for _ in range(20):
        l0 = total_length / 2.0
        ds = l0 / samples
        theta_half = 0.0
        for i in range(samples):
            theta_half += euler_curvature_half(i * ds, r_max, r_min, l0) * ds
        theta_total = 2.0 * theta_half
        if abs(theta_total - turn_angle) < 1e-7:
            break
        if theta_total > 0:
            total_length *= turn_angle / theta_total
    return total_length


def euler_reff(r_max, r_min, samples=1000):
    """计算 PDK 定义的 Euler effective radius。"""
    if r_max <= 0 or r_min <= 0 or r_min >= r_max:
        return r_max if r_max > 0 else 0.0
    total_length = solve_total_length(r_max, r_min, math.pi / 2.0, samples)
    l0 = total_length / 2.0
    ds = l0 / samples
    x, y, theta = 0.0, 0.0, 0.0
    for i in range(samples):
        kappa = euler_curvature_half(i * ds, r_max, r_min, l0)
        x += math.cos(theta) * ds
        y += math.sin(theta) * ds
        theta += kappa * ds
    return x + y


def euler_curve_points(r_max, r_min, turn_angle, samples):
    """生成未强制端口直段的 Euler 曲线点列。"""
    if r_max <= 0 or r_min <= 0 or r_min >= r_max:
        return [(0.0, 0.0)]
    total_length = solve_total_length(r_max, r_min, turn_angle, samples)
    l0 = total_length / 2.0
    ds = l0 / samples
    points = [(0.0, 0.0)]
    x, y, theta = 0.0, 0.0, 0.0
    for i in range(samples):
        kappa = euler_curvature_half(i * ds, r_max, r_min, l0)
        x += math.cos(theta) * ds
        y += math.sin(theta) * ds
        points.append((x, y))
        theta += kappa * ds

    x_mid, y_mid = x, y
    for i in range(samples - 1, -1, -1):
        px, py = points[i]
        points.append((x_mid + y_mid - py, y_mid + x_mid - px))
    return points


def points_per_circle(radius_um, dbu=0.001):
    """按不超过半个 DBU 的弦高误差计算整圆采样点数。"""
    radius = abs(float(radius_um))
    if radius <= 0:
        return MIN_POINTS_PER_90 * 4
    if radius <= 1.0:
        return 10
    error = abs(float(dbu) if dbu else 0.001) / 2.0
    ratio = 1.0 - error / radius
    ratio = max(-1.0, min(0.999999999999999, ratio))
    return int(math.ceil(math.pi / math.acos(ratio)))


def points_per_90(radius_um, dbu=0.001):
    """计算 PDK 自动采样模式下的 90° 弯曲采样点数。"""
    return max(MIN_POINTS_PER_90, int(math.ceil(points_per_circle(radius_um, dbu) / 4.0)))


def with_port_straights(points, radius, straight_length=PORT_STRAIGHT_UM):
    """镜像 bend_90deg.py 的端口 10 nm 直段插入和采样点清理。"""
    if radius <= straight_length:
        raise ValueError("有效弯曲半径必须大于端口直段长度。")
    eps = 1e-12
    cleaned = [(0.0, 0.0), (straight_length, 0.0)]
    last_x, last_y = cleaned[-1]
    for raw_x, raw_y in list(points)[1:-1]:
        x = float(raw_x)
        y = float(raw_y)
        if x <= straight_length + eps or y >= radius - straight_length - eps:
            continue
        if x < last_x - eps or y < last_y - eps:
            continue
        if x > radius + eps or y < -eps:
            continue
        if abs(x - last_x) <= eps and abs(y - last_y) <= eps:
            continue
        cleaned.append((x, y))
        last_x, last_y = x, y
    exit_start = (radius, radius - straight_length)
    if abs(cleaned[-1][0] - exit_start[0]) > eps or abs(cleaned[-1][1] - exit_start[1]) > eps:
        cleaned.append(exit_start)
    cleaned.append((radius, radius))
    return cleaned


def centerline_points(r_max, r_min, dbu, requested_points=0, port_straight=PORT_STRAIGHT_UM):
    """生成与 PDK Bend_90deg Euler 分支一致的中心线点列。"""
    reff = euler_reff(r_max, r_min)
    npoints = points_per_90(reff, dbu) if requested_points <= 0 else max(MIN_POINTS_PER_90, requested_points)
    half_samples = max(10, npoints // 2)
    raw = euler_curve_points(r_max, r_min, math.pi / 2.0, half_samples)
    x_end = raw[-1][0]
    scale = reff / x_end if x_end > 1e-9 else 1.0
    scaled = [(x * scale, y * scale) for x, y in raw]
    scaled[0] = (0.0, 0.0)
    scaled[-1] = (reff, reff)
    return reff, npoints, with_port_straights(scaled, reff, port_straight)


def cumulative_lengths(points):
    """计算中心线累计弧长。"""
    values = [0.0]
    total = 0.0
    for i in range(1, len(points)):
        total += math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1])
        values.append(total)
    return values


def tangent_angle(points, index):
    """用相邻点估算切线角。"""
    if index <= 0:
        p0, p1 = points[0], points[1]
    elif index >= len(points) - 1:
        p0, p1 = points[-2], points[-1]
    else:
        p0, p1 = points[index - 1], points[index + 1]
    return math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))


def discrete_curvature(points, index):
    """用三点外接圆估算离散曲率，端点返回 0。"""
    if index <= 0 or index >= len(points) - 1:
        return 0.0
    ax, ay = points[index - 1]
    bx, by = points[index]
    cx, cy = points[index + 1]
    ab = math.hypot(bx - ax, by - ay)
    bc = math.hypot(cx - bx, cy - by)
    ca = math.hypot(ax - cx, ay - cy)
    area2 = abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax))
    denom = ab * bc * ca
    if denom <= 1e-18:
        return 0.0
    return 2.0 * area2 / denom


def write_csv(path, points, r_max, r_min, reff, width, npoints):
    """写出中心线 CSV。"""
    lengths = cumulative_lengths(points)
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "index",
            "x_um",
            "y_um",
            "s_um",
            "theta_deg",
            "kappa_1_per_um_discrete",
            "radius_um_discrete",
            "width_um",
            "Euler_Rmax_um",
            "Euler_Rmin_um",
            "Euler_Reff_um",
            "points_per_90",
        ])
        for i, (x, y) in enumerate(points):
            kappa = discrete_curvature(points, i)
            radius = 1.0 / kappa if kappa > 1e-15 else ""
            writer.writerow([
                i,
                "%.9f" % x,
                "%.9f" % y,
                "%.9f" % lengths[i],
                "%.9f" % tangent_angle(points, i),
                "%.12g" % kappa,
                "%.9f" % radius if radius != "" else "",
                "%.9f" % width,
                "%.9f" % r_max,
                "%.9f" % r_min,
                "%.9f" % reff,
                npoints,
            ])


def parse_args():
    parser = argparse.ArgumentParser(description="导出 JNU_MWP_PDK Euler 90° bend 中心线。")
    parser.add_argument("--rmax", type=float, default=30.0, help="Euler_Rmax，单位 um。")
    parser.add_argument("--rmin", type=float, default=10.0, help="Euler_Rmin，单位 um。")
    parser.add_argument("--width", type=float, default=0.5, help="波导宽度，单位 um，仅写入 CSV 供 FDTD 建模使用。")
    parser.add_argument("--dbu", type=float, default=0.001, help="KLayout DBU，单位 um。")
    parser.add_argument("--points", type=int, default=0, help="90° 采样点数；0 表示按 PDK 自动采样。")
    parser.add_argument("--port-straight", type=float, default=PORT_STRAIGHT_UM, help="端口直段长度，单位 um。")
    parser.add_argument("--output", required=True, help="输出 CSV 路径。")
    return parser.parse_args()


def main():
    args = parse_args()
    if not (args.rmax > args.rmin > 0.0):
        raise ValueError("必须满足 rmax > rmin > 0。")
    reff, npoints, points = centerline_points(
        args.rmax,
        args.rmin,
        args.dbu,
        args.points,
        args.port_straight,
    )
    write_csv(args.output, points, args.rmax, args.rmin, reff, args.width, npoints)
    length = cumulative_lengths(points)[-1]
    print(
        "OK: output=%s points=%d points_per_90=%d Reff=%.9f um length=%.9f um"
        % (args.output, len(points), npoints, reff, length)
    )


if __name__ == "__main__":
    main()

