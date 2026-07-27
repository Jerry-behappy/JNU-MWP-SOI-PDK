# $autorun
# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-06

# JNULib_BlackBox 黑盒器件库初始化脚本。
# 将固定 GDS 器件替换为 Si 实心矩形块，并保留 PinRec 端口供 SiEPIC 识别。

import os
import sys

import pya


# KLayout 启动宏时不一定包含当前目录，这里显式加入黑盒目录和 pymacros 目录。
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
PYMACROS_DIR = os.path.dirname(SCRIPT_DIR)
for directory in (SCRIPT_DIR, PYMACROS_DIR):
    if directory not in sys.path:
        sys.path.insert(0, directory)

# 固定 GDS 器件和识别层定义。
LIBRARY_DBU = 0.001                  # JNU_MWP_PDK 的数据库单位，1 nm。
# 与白盒库相同：稳定注册名保证版本升级后已放置器件仍可识别。
LIBRARY_NAME = "JNULib_BlackBox"
LEGACY_LIBRARY_NAMES = ("JNULib_BlackBox_v1.1", "JNULib_BlackBox_v1.0")
BLACKBOX_GDS_DIR = os.path.join(PYMACROS_DIR, "JNU_MWP_blackbox_gds")
WHITEBOX_GDS_DIR = os.path.join(PYMACROS_DIR, "JNU_MWP_gds")
SI_LAYER = pya.LayerInfo(1, 0)       # Si 波导层。
PIN_LAYER = pya.LayerInfo(1, 10)     # PinRec 端口识别层。
DEVREC_LAYER = pya.LayerInfo(68, 0)  # DevRec 器件识别层。
TEXT_LAYER = pya.LayerInfo(10, 0)    # 黑盒标签文字层。


def _directory_has_gds(directory):
    """判断目录中是否存在 GDS 文件。"""
    if not os.path.isdir(directory):
        return False
    return any(filename.lower().endswith(".gds") for filename in os.listdir(directory))


def _active_gds_dir():
    """优先使用预生成黑盒 GDS；开发环境中缺失时退回白盒 GDS 现场生成。"""
    if _directory_has_gds(BLACKBOX_GDS_DIR):
        return BLACKBOX_GDS_DIR
    if _directory_has_gds(WHITEBOX_GDS_DIR):
        return WHITEBOX_GDS_DIR
    return None


def _delete_existing_library(library_name):
    """删除同名旧库，避免 KLayout 热重载时保留旧的 PCell 或 cell 状态。"""
    for library_id in list(pya.Library.library_ids()):
        library = pya.Library.library_by_id(library_id)
        if library and library.name() == library_name:
            library.delete()


def _scale_length(value, src_dbu, dst_dbu):
    """把源布局整数长度转换到目标布局整数长度。"""
    return int(round(float(value) * src_dbu / dst_dbu))


def _scale_point(point, src_dbu, dst_dbu):
    """把源布局整数坐标点转换到目标布局整数坐标点。"""
    return pya.Point(
        _scale_length(point.x, src_dbu, dst_dbu),
        _scale_length(point.y, src_dbu, dst_dbu),
    )


def _scale_box(box, src_dbu, dst_dbu):
    """把源布局 bbox 转换到目标布局 bbox，保持物理尺寸不变。"""
    if box.empty():
        return pya.Box()

    return pya.Box(
        _scale_length(box.left, src_dbu, dst_dbu),
        _scale_length(box.bottom, src_dbu, dst_dbu),
        _scale_length(box.right, src_dbu, dst_dbu),
        _scale_length(box.top, src_dbu, dst_dbu),
    )


def _scale_path(path, src_dbu, dst_dbu):
    """把源布局 Path 转换到目标布局 Path，保持端口位置和宽度不变。"""
    width = max(1, _scale_length(path.width, src_dbu, dst_dbu))
    src_points = list(path.each_point())
    if len(src_points) == 2:
        p0, p1 = src_points
        dx = p1.x - p0.x
        dy = p1.y - p0.y
        length_dbu = max(2, int(round(max(abs(dx), abs(dy)) * src_dbu / dst_dbu)))
        half = max(1, length_dbu // 2)
        cx = _scale_length((p0.x + p1.x) * 0.5, src_dbu, dst_dbu)
        cy = _scale_length((p0.y + p1.y) * 0.5, src_dbu, dst_dbu)
        # PinRec 短 path 需要在黑盒边界内外各露出一半，避免 0.1 nm 到 1 nm dbu 时被舍入吞掉。
        if abs(dx) >= abs(dy) and dx != 0:
            if dx > 0:
                return pya.Path([pya.Point(cx - half, cy), pya.Point(cx + half, cy)], width)
            return pya.Path([pya.Point(cx + half, cy), pya.Point(cx - half, cy)], width)
        if dy != 0:
            if dy > 0:
                return pya.Path([pya.Point(cx, cy - half), pya.Point(cx, cy + half)], width)
            return pya.Path([pya.Point(cx, cy + half), pya.Point(cx, cy - half)], width)

    points = [_scale_point(point, src_dbu, dst_dbu) for point in src_points]
    bgn_ext = _scale_length(path.bgn_ext, src_dbu, dst_dbu)
    end_ext = _scale_length(path.end_ext, src_dbu, dst_dbu)
    return pya.Path(points, width, bgn_ext, end_ext)


def _scale_text(text, src_dbu, dst_dbu):
    """把源布局 Text 转换到目标布局 Text，保持文字位置不变。"""
    disp = _scale_point(text.trans.disp, src_dbu, dst_dbu)
    scaled = pya.Text(text.string, pya.Trans(text.trans.rot, False, disp.x, disp.y))
    scaled.size = _scale_length(text.size, src_dbu, dst_dbu)
    return scaled


def _copy_pin_layer_and_get_info(src_cell, dst_cell, src_layout, src_dbu, dst_dbu):
    """复制源 cell 的 PinRec 图形，并提取端口宽度和方向信息。"""
    pin_layer_index = src_layout.layer(PIN_LAYER)
    pin_bbox = pya.Box()
    max_path_width = 0
    has_horizontal = False
    has_vertical = False

    if pin_layer_index is None:
        return pin_bbox, max_path_width, has_horizontal, has_vertical

    dst_pin_index = dst_cell.layout().layer(PIN_LAYER)
    for shape in src_cell.each_shape(pin_layer_index):
        if shape.is_text():
            text = _scale_text(shape.text, src_dbu, dst_dbu)
            dst_cell.shapes(dst_pin_index).insert(text)
            pin_bbox += text.bbox()
        elif shape.is_path():
            path = _scale_path(shape.path, src_dbu, dst_dbu)
            dst_cell.shapes(dst_pin_index).insert(path)
            pin_bbox += path.bbox()
            max_path_width = max(max_path_width, path.width)

            # PinRec 短路径的端点方向就是 SiEPIC 识别的端口朝向。
            pts = list(path.each_point())
            if len(pts) >= 2:
                p0, p1 = pts[0], pts[-1]
                dx = abs(p1.x - p0.x)
                dy = abs(p1.y - p0.y)
                if dx >= dy:
                    has_horizontal = True
                else:
                    has_vertical = True
        elif shape.is_box():
            box = _scale_box(shape.box, src_dbu, dst_dbu)
            dst_cell.shapes(dst_pin_index).insert(box)
            pin_bbox += box

    return pin_bbox, max_path_width, has_horizontal, has_vertical


def _get_layer_bbox(src_cell, src_layout, layer_info):
    """递归读取指定图层的整体 bbox，用于保留原始器件边界。"""
    layer_index = src_layout.layer(layer_info)
    bbox = pya.Box()

    if layer_index is None:
        return bbox

    iterator = src_cell.begin_shapes_rec(layer_index)
    while not iterator.at_end():
        bbox += iterator.shape().bbox().transformed(iterator.itrans())
        iterator.next()

    return bbox


def _draw_si_block(cell, si_bbox, devrec_bbox, dbu, label_text):
    """绘制黑盒 Si 实心矩形、原始 DevRec 边界和文字标签。"""
    si_index = cell.layout().layer(SI_LAYER)
    devrec_index = cell.layout().layer(DEVREC_LAYER)
    text_index = cell.layout().layer(TEXT_LAYER)

    # 固定 GDS 黑盒的 Si 块直接采用原始 Si 图层 bbox，避免被 PinRec 端点或 DevRec 外框拉偏。
    x1 = int(si_bbox.left)
    y1 = int(si_bbox.bottom)
    x2 = int(si_bbox.right)
    y2 = int(si_bbox.top)

    if x1 >= x2:
        x1, x2 = x2 - 1, x1 + 1
    if y1 >= y2:
        y1, y2 = y2 - 1, y1 + 1

    box = pya.Box(x1, y1, x2, y2)
    cell.shapes(si_index).insert(box)

    orig_box = pya.Box(
        int(devrec_bbox.left),
        int(devrec_bbox.bottom),
        int(devrec_bbox.right),
        int(devrec_bbox.top),
    )
    cell.shapes(devrec_index).insert(orig_box)

    if not _insert_basic_text(cell, box, dbu, label_text):
        _insert_fallback_text(cell, text_index, box, dbu, label_text)


def _basic_text_mag(target_box, dbu, label_text):
    """按黑盒区域估算 Basic TEXT 放大倍数，并给文字边界留出余量。"""

    width_um = max(0.001, target_box.width() * dbu)
    height_um = max(0.001, target_box.height() * dbu)
    char_count = max(1, len(label_text))
    by_height = height_um * 0.45 / 0.7
    by_width = width_um / (char_count * 0.75)
    return max(0.02, min(by_height, by_width))


def _insert_basic_text(cell, target_box, dbu, label_text):
    """优先插入 Basic 库 TEXT PCell，使黑盒文字显示为 Basic layout object。"""

    layout = cell.layout()
    try:
        text_cell = layout.create_cell(
            "TEXT",
            "Basic",
            {
                "text": label_text,
                "layer": TEXT_LAYER,
                "mag": _basic_text_mag(target_box, dbu, label_text),
            },
        )
    except Exception:
        text_cell = None
    if text_cell is None:
        return False

    bbox = text_cell.bbox()
    if bbox.empty():
        return False

    cx = (target_box.left + target_box.right) // 2
    cy = (target_box.bottom + target_box.top) // 2
    text_cx = (bbox.left + bbox.right) // 2
    text_cy = (bbox.bottom + bbox.top) // 2
    cell.insert(
        pya.CellInstArray(
            text_cell.cell_index(),
            pya.Trans(pya.Trans.R0, cx - text_cx, cy - text_cy),
        )
    )
    return True


def _insert_fallback_text(cell, text_index, target_box, dbu, label_text):
    """Basic 库不可用时退回 primitive Text，保证黑盒库仍能加载。"""

    cx = (target_box.left + target_box.right) // 2
    cy = (target_box.bottom + target_box.top) // 2
    text = pya.Text(label_text, pya.Trans(pya.Trans.R0, cx, cy))
    shape = cell.shapes(text_index).insert(text)
    shape.text_halign = 1
    shape.text_valign = 1
    shape.text_dsize = _basic_text_mag(target_box, dbu, label_text) * 0.7


def _load_gds_blackbox(ly):
    """读取固定 GDS 器件，并生成对应黑盒 cell。"""
    gds_dir = _active_gds_dir()
    if gds_dir is None:
        print("%s: GDS directory not found: %s or %s" % (LIBRARY_NAME, BLACKBOX_GDS_DIR, WHITEBOX_GDS_DIR))
        return

    for filename in sorted(os.listdir(gds_dir)):
        if not filename.lower().endswith(".gds"):
            continue

        fullpath = os.path.join(gds_dir, filename)
        temp = pya.Layout()
        temp.read(fullpath)

        for top_cell in temp.each_top_cell():
            cell_obj = temp.cell(top_cell) if isinstance(top_cell, int) else top_cell
            cell_name = cell_obj.name
            cell_bbox = cell_obj.bbox()
            si_bbox = _get_layer_bbox(cell_obj, temp, SI_LAYER)
            devrec_bbox = _get_layer_bbox(cell_obj, temp, DEVREC_LAYER)
            dst_dbu = ly.dbu

            if cell_bbox.empty():
                print("%s: skipping empty cell: %s" % (LIBRARY_NAME, cell_name))
                continue

            # 若旧版 GDS 缺少对应图层，则退回到 cell bbox，保证库仍能加载。
            if si_bbox.empty():
                si_bbox = cell_bbox
            if devrec_bbox.empty():
                devrec_bbox = cell_bbox

            # 所有 bbox 都从源 GDS dbu 转换到黑盒库 dbu，避免 GUI 中出现 10 倍缩放。
            si_bbox = _scale_box(si_bbox, temp.dbu, dst_dbu)
            devrec_bbox = _scale_box(devrec_bbox, temp.dbu, dst_dbu)

            new_cell = ly.create_cell(cell_name)
            _copy_pin_layer_and_get_info(
                cell_obj, new_cell, temp, temp.dbu, dst_dbu
            )

            _draw_si_block(
                new_cell,
                si_bbox,
                devrec_bbox,
                dst_dbu,
                cell_name + " (black box)",
            )

            print("%s loaded: %s" % (LIBRARY_NAME, cell_name))


class JNULibBlackBox(pya.Library):
    """JNU 微波光子黑盒器件库。"""

    def __init__(self):
        # 黑盒库同样保持稳定身份，并在 Library 面板说明栏显示发行版本。
        self.description = "v1.1, JNU MWP PDK black-box components [Technology JNU_MWP_PDK]"

        ly = self.layout()

        # 显式固定黑盒库 dbu，避免 GUI 默认 dbu 造成固定 GDS 黑盒放大或缩小。
        ly.dbu = LIBRARY_DBU

        # 固定 GDS 器件仍生成黑盒 cell。
        _load_gds_blackbox(ly)

        # 黑盒器件库只包含固定黑盒 cell，不注册任何 PCell。

        self.register(LIBRARY_NAME)


for legacy_library_name in LEGACY_LIBRARY_NAMES:
    _delete_existing_library(legacy_library_name)
_delete_existing_library(LIBRARY_NAME)
JNULibBlackBox()
