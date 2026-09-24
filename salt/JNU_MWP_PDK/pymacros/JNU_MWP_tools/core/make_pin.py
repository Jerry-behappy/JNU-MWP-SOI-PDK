# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

# SiEPIC 兼容光学端口生成函数。
# 在指定 Cell 的 PinRec 图层上创建文字标签和短路径，
# 使 SiEPIC-Tools 能识别版图中的端口名称、位置和方向。

import pya


def make_pin(cell, name, center, w, layer, direction, debug=False):
    """创建 SiEPIC-Tools 可识别的光学 pin。

    参数：
        cell：pin 所在的 cell。
        name：pin 名称，例如 opt1、opt2。
        center：pin 中心坐标，可为 [x, y]、pya.Point 或 pya.DPoint。
        w：pin 宽度，通常等于波导宽度。
        layer：PinRec 图层，可为 layout.layer() 返回值，也可为技术文件中的图层名。
        direction：端口朝向，0 向右、90 向上、180 向左、270 向下。

    约定：
        浮点坐标/宽度按微米处理，整数坐标/宽度按数据库单位处理。
    """

    # 如果传入的是技术文件中的图层名，先转换为 KLayout 内部 layer index。
    if isinstance(layer, str):
        layer = cell.layout().layer(cell.layout().TECHNOLOGY[layer])

    # 将微米值按当前 dbu 量化为数据库整数单位。
    to_itype = lambda v, dbu: int(round(float(v) / dbu))
    # PinRec 短路径总长固定为 20 nm，中心点位于路径中点。
    # 使用物理长度换算，避免 dbu 为 0.1 nm 时错误退化成 2 nm。
    PIN_LENGTH_UM = 0.02

    try:
        import numpy

        float_types = (float, numpy.float64)
    except ImportError:
        float_types = (float,)

    dbu = cell.layout().dbu
    pin_length = max(1, int(round(PIN_LENGTH_UM / dbu)))

    # 宽度为浮点数时表示微米，需要转换为数据库整数单位。
    if isinstance(w, float_types):
        w = to_itype(w, dbu)
        if debug:
            print("make_pin: width converted to %s" % w)
    elif debug:
        print("make_pin: width %s" % w)

    # 兼容 pya.Point / pya.DPoint 坐标对象。
    if isinstance(center, (pya.Point, pya.DPoint)):
        center = [center.x, center.y]
    else:
        center = [center[0], center[1]]

    # 坐标为浮点数时表示微米，需要转换为数据库整数单位。
    if isinstance(center[0], float_types):
        center[0] = to_itype(center[0], dbu)
        center[1] = to_itype(center[1], dbu)
        if debug:
            print("make_pin: center converted to %s" % center)
    elif debug:
        print("make_pin: center %s" % center)

    center[0] = int(round(center[0]))
    center[1] = int(round(center[1]))
    w = max(1, int(round(w)))

    direction = direction % 360
    if direction not in [0, 90, 180, 270]:
        raise Exception(
            "error in make_pin: direction (%s) must be one of [0, 90, 180, 270]"
            % direction
        )

    # SiEPIC 通过 PinRec 文字标签识别端口名称，因此文字必须位于短路径 bbox 内。
    transform = pya.Trans(pya.Trans.R0, center[0], center[1])
    text = pya.Text(name, transform)
    shape = cell.shapes(layer).insert(text)
    shape.text_dsize = float(w * dbu / 2)
    shape.text_valign = 1

    half_length = int(round(pin_length / 2))

    # 根据端口方向生成 PinRec 短路径；路径端点顺序决定 SiEPIC 识别到的端口朝向。
    if direction == 0:
        p1 = pya.Point(center[0] - half_length, center[1])
        p2 = pya.Point(center[0] + half_length, center[1])
        shape.text_halign = 2
    elif direction == 90:
        p1 = pya.Point(center[0], center[1] - half_length)
        p2 = pya.Point(center[0], center[1] + half_length)
        shape.text_halign = 2
        shape.text_rot = 1
    elif direction == 180:
        p1 = pya.Point(center[0] + half_length, center[1])
        p2 = pya.Point(center[0] - half_length, center[1])
        shape.text_halign = 3
    else:
        p1 = pya.Point(center[0], center[1] + half_length)
        p2 = pya.Point(center[0], center[1] - half_length)
        shape.text_halign = 3
        shape.text_rot = 1

    # 插入真正的 PinRec 短路径；缺少这条路径时 SiEPIC 无法通过 find_pins/snap 识别端口。
    cell.shapes(layer).insert(pya.Path([p1, p2], w))
