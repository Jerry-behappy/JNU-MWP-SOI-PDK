# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

# 生成可分发的 JNU_MWP_PDK 黑盒版本。
# 输出目录默认在桌面：JNU_MWP_PDK_blackbox_v1.1。
# 发布包同时包含 salt/JNU_MWP_PDK 和 tech/JNU_MWP_PDK，便于 KLayout 原生识别 Technology。

import argparse
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET

import pya


PDK_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = Path.home() / "Desktop" / "JNU_MWP_PDK_blackbox_v1.1"

TECH_FOLDER_NAME = "JNU_MWP_PDK"
TECH_NAME = "JNU_MWP_PDK"
SALT_PACKAGE_NAME = "JNU_MWP_PDK"
LOADER_MACRO_NAME = "JNU_MWP_PDK_blackbox_loader.py"

SI_LAYER = pya.LayerInfo(1, 0)
PIN_LAYER = pya.LayerInfo(1, 10)
DEVREC_LAYER = pya.LayerInfo(68, 0)
TEXT_LAYER = pya.LayerInfo(10, 0)
LIBRARY_DBU = 0.001


def _safe_remove_output(path):
    """安全删除旧输出目录，避免误删非黑盒发布目录。"""
    resolved = path.resolve()
    desktop = (Path.home() / "Desktop").resolve()
    if resolved == desktop or desktop not in resolved.parents:
        raise RuntimeError("拒绝删除非桌面黑盒输出目录：%s" % resolved)
    if not resolved.name.startswith("JNU_MWP_PDK_blackbox"):
        raise RuntimeError("拒绝删除名称不符合黑盒输出规则的目录：%s" % resolved)
    if resolved.exists():
        shutil.rmtree(str(resolved))


def _copy_tree(src, dst):
    """复制目录，过滤缓存和临时文件。"""
    def ignore(_directory, names):
        ignored = []
        for name in names:
            lower = name.lower()
            if name == "__pycache__" or lower.endswith(".pyc") or lower.endswith(".pyo"):
                ignored.append(name)
            if lower.endswith(".log"):
                ignored.append(name)
        return ignored

    if src.exists():
        shutil.copytree(str(src), str(dst), ignore=ignore)


def _write_blackbox_pymacros_init(pymacros_dst):
    """写入黑盒包专用 autorun，只加载黑盒库。"""
    content = (
        "# $autorun\n"
        "# -*- coding: utf-8 -*-\n"
        "# 创建者: Junyi Zhang\n"
        "# 时间: 2026-06\n\n"
        "# 初始化 JNU MWP 黑盒器件库。Technology 主要由 tech/JNU_MWP_PDK 注册，"
        "这里保留 Salt 场景下的辅助加载逻辑。\n"
        "print(\"JNU MWP BlackBox PDK: load JNULib_BlackBox\")\n\n"
        "import os\n\n"
        "import xml.etree.ElementTree as ET\n\n"
        "import pya\n\n\n"
        "TECH_NAME = \"JNU_MWP_PDK\"\n"
        "SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if \"__file__\" in globals() else os.getcwd()\n"
        "PDK_ROOT = os.path.dirname(SCRIPT_DIR)\n"
        "KLAYOUT_ROOT = os.path.dirname(os.path.dirname(PDK_ROOT))\n"
        "TECH_ROOT = os.path.join(KLAYOUT_ROOT, \"tech\", \"JNU_MWP_PDK\")\n"
        "TECH_FILE = os.path.join(PDK_ROOT, \"JNU_MWP_PDK.lyt\")\n"
        "TECH_COPY = os.path.join(TECH_ROOT, \"JNU_MWP_PDK.lyt\")\n\n\n"
        "def _rewrite_technology_file(path, layer_path):\n"
        "    \"\"\"启动时把 .lyt 路径改成本机真实安装路径，减少手动安装出错。\"\"\"\n"
        "    if not os.path.isfile(path):\n"
        "        return\n"
        "    try:\n"
        "        tree = ET.parse(path)\n"
        "        root = tree.getroot()\n"
        "        for tag, value in (\n"
        "            (\"name\", TECH_NAME),\n"
        "            (\"base-path\", PDK_ROOT.replace(os.sep, \"/\")),\n"
        "            (\"original-base-path\", TECH_ROOT.replace(os.sep, \"/\")),\n"
        "            (\"layer-properties_file\", layer_path.replace(os.sep, \"/\")),\n"
        "        ):\n"
        "            node = root.find(tag)\n"
        "            if node is not None:\n"
        "                node.text = value\n"
        "        tree.write(path, encoding=\"utf-8\", xml_declaration=True)\n"
        "    except Exception as error:\n"
        "        print(\"JNU MWP BlackBox PDK: technology path rewrite failed:\", error)\n\n\n"
        "def _load_jnu_technology():\n"
        "    \"\"\"从 Salt 包目录辅助加载 Technology，避免只安装 salt 时完全不可用。\"\"\"\n"
        "    load_file = TECH_COPY if os.path.isfile(TECH_COPY) else TECH_FILE\n"
        "    if not os.path.isfile(load_file):\n"
        "        print(\"JNU MWP BlackBox PDK: technology file not found:\", load_file)\n"
        "        return\n"
        "    try:\n"
        "        _rewrite_technology_file(TECH_FILE, os.path.join(PDK_ROOT, \"layers.lyp\"))\n"
        "        _rewrite_technology_file(TECH_COPY, os.path.join(TECH_ROOT, \"layers.lyp\"))\n"
        "        if not pya.Technology().has_technology(TECH_NAME):\n"
        "            tech = pya.Technology().create_technology(TECH_NAME)\n"
        "        else:\n"
        "            tech = pya.Technology.technology_by_name(TECH_NAME)\n"
        "        tech.load(load_file)\n"
        "        print(\"JNU MWP BlackBox PDK: technology loaded from\", load_file)\n"
        "    except Exception as error:\n"
        "        print(\"JNU MWP BlackBox PDK: technology load failed:\", error)\n\n\n"
        "_load_jnu_technology()\n\n"
        "from . import JNULib_BlackBox  # 只加载黑盒器件库。\n"
    )
    (pymacros_dst / "__init__.py").write_text(content, encoding="utf-8", newline="\n")


def _copy_required_files(package_root):
    """复制黑盒 PDK 运行所需文件，排除白盒固定器件 GDS。"""
    package_root.mkdir(parents=True, exist_ok=True)

    for filename in ("__init__.py", "JNU_MWP_PDK.lyt", "layers.lyp"):
        shutil.copy2(str(PDK_ROOT / filename), str(package_root / filename))

    for dirname in ("drc", "d25", "lvs", "macros", "xsect"):
        src = PDK_ROOT / dirname
        if src.exists():
            _copy_tree(src, package_root / dirname)

    pymacros_src = PDK_ROOT / "pymacros"
    pymacros_dst = package_root / "pymacros"
    pymacros_dst.mkdir(parents=True, exist_ok=True)

    for filename in (
        "JNULib_BlackBox.py",
        "JNU_MWP_PDK_Menu.lym",
        "README.md",
    ):
        shutil.copy2(str(pymacros_src / filename), str(pymacros_dst / filename))

    for dirname in ("JNU_MWP_blackbox", "Keybindings"):
        _copy_tree(pymacros_src / dirname, pymacros_dst / dirname)

    # 发布包只携带菜单运行所需的 core/actions；release 与 tests 留在开发包。
    tools_src = pymacros_src / "JNU_MWP_tools"
    tools_dst = pymacros_dst / "JNU_MWP_tools"
    tools_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(tools_src / "__init__.py"), str(tools_dst / "__init__.py"))
    for dirname in ("core", "actions"):
        _copy_tree(tools_src / dirname, tools_dst / dirname)

    # 黑盒发布包不包含 JNU_MWP_gds，也不复制 JNULib.py，避免注册白盒固定器件库。
    _write_blackbox_pymacros_init(pymacros_dst)


def _loader_source():
    """返回发布包根目录 pymacros loader，用于触发 salt 包中的库和菜单加载。"""
    return (
        "# $autorun\n"
        "# -*- coding: utf-8 -*-\n"
        "# 创建者: Junyi Zhang\n"
        "# 时间: 2026-06\n\n"
        "# 根目录加载器：KLayout 会自动扫描 %USERPROFILE%/KLayout/pymacros。\n"
        "# 该文件负责把 salt/JNU_MWP_PDK 中的黑盒库和功能菜单加载出来。\n\n"
        "import os\n"
        "import sys\n\n"
        "import pya\n\n\n"
        "PACKAGE_NAME = \"JNU_MWP_PDK\"\n"
        "SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if \"__file__\" in globals() else os.getcwd()\n"
        "KLAYOUT_ROOT = os.path.dirname(SCRIPT_DIR)\n"
        "SALT_PARENT = os.path.join(KLAYOUT_ROOT, \"salt\")\n"
        "PDK_ROOT = os.path.join(SALT_PARENT, PACKAGE_NAME)\n"
        "PYMACROS_DIR = os.path.join(PDK_ROOT, \"pymacros\")\n"
        "MENU_MACRO = os.path.join(PYMACROS_DIR, \"JNU_MWP_PDK_Menu.lym\")\n\n\n"
        "for directory in (SALT_PARENT, PYMACROS_DIR):\n"
        "    if os.path.isdir(directory) and directory not in sys.path:\n"
        "        sys.path.insert(0, directory)\n\n\n"
        "def _load_blackbox_library():\n"
        "    \"\"\"导入黑盒 salt 包，注册 JNULib_BlackBox 和 Technology。\"\"\"\n"
        "    try:\n"
        "        import JNU_MWP_PDK.pymacros  # noqa: F401\n"
        "    except Exception as error:\n"
        "        print(\"JNU_MWP_PDK blackbox loader: library load failed:\", error)\n\n\n"
        "def _load_menu():\n"
        "    \"\"\"运行菜单宏，创建 JNU_MWP_PDK 顶部功能菜单。\"\"\"\n"
        "    if not os.path.isfile(MENU_MACRO):\n"
        "        print(\"JNU_MWP_PDK blackbox loader: menu macro not found:\", MENU_MACRO)\n"
        "        return\n"
        "    if not hasattr(pya, \"Application\"):\n"
        "        return\n"
        "    try:\n"
        "        main_window = pya.Application.instance().main_window()\n"
        "        if main_window is not None and main_window.menu().is_menu(\"jnu_mwp_pdk_menu\"):\n"
        "            return\n"
        "    except Exception:\n"
        "        pass\n"
        "    try:\n"
        "        pya.Macro(MENU_MACRO).run()\n"
        "    except Exception as error:\n"
        "        print(\"JNU_MWP_PDK blackbox loader: menu load failed:\", error)\n\n\n"
        "_load_blackbox_library()\n"
        "_load_menu()\n"
    )


def _write_root_loader(release_root):
    """在发布包根目录生成 pymacros loader，支持直接复制到 KLayout 根目录。"""
    loader_dir = release_root / "pymacros"
    loader_dir.mkdir(parents=True, exist_ok=True)
    (loader_dir / LOADER_MACRO_NAME).write_text(_loader_source(), encoding="utf-8", newline="\n")


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
    """把源布局 bbox 转换到目标布局 bbox。"""
    if box.empty():
        return pya.Box()
    return pya.Box(
        _scale_length(box.left, src_dbu, dst_dbu),
        _scale_length(box.bottom, src_dbu, dst_dbu),
        _scale_length(box.right, src_dbu, dst_dbu),
        _scale_length(box.top, src_dbu, dst_dbu),
    )


def _scale_path(path, src_dbu, dst_dbu):
    """把源布局 Path 转换到目标布局 Path。"""
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
    """把源布局 Text 转换到目标布局 Text。"""
    disp = _scale_point(text.trans.disp, src_dbu, dst_dbu)
    scaled = pya.Text(text.string, pya.Trans(text.trans.rot, False, disp.x, disp.y))
    scaled.size = _scale_length(text.size, src_dbu, dst_dbu)
    return scaled


def _get_layer_bbox(src_cell, src_layout, layer_info):
    """递归读取指定图层的整体 bbox。"""
    layer_index = src_layout.layer(layer_info)
    bbox = pya.Box()
    if layer_index is None:
        return bbox

    iterator = src_cell.begin_shapes_rec(layer_index)
    while not iterator.at_end():
        bbox += iterator.shape().bbox().transformed(iterator.itrans())
        iterator.next()
    return bbox


def _copy_pin_layer(src_cell, dst_cell, src_layout, dst_layout):
    """复制 PinRec 图形，保留端口位置、宽度和方向。"""
    src_pin_index = src_layout.layer(PIN_LAYER)
    if src_pin_index is None:
        return

    dst_pin_index = dst_layout.layer(PIN_LAYER)
    for shape in src_cell.each_shape(src_pin_index):
        if shape.is_text():
            dst_cell.shapes(dst_pin_index).insert(_scale_text(shape.text, src_layout.dbu, dst_layout.dbu))
        elif shape.is_path():
            dst_cell.shapes(dst_pin_index).insert(_scale_path(shape.path, src_layout.dbu, dst_layout.dbu))
        elif shape.is_box():
            dst_cell.shapes(dst_pin_index).insert(_scale_box(shape.box, src_layout.dbu, dst_layout.dbu))


def _draw_blackbox_cell(src_cell, src_layout, dst_layout):
    """从白盒 cell 生成单个黑盒 cell。"""
    dst_cell = dst_layout.create_cell(src_cell.name)
    src_bbox = src_cell.bbox()
    si_bbox = _get_layer_bbox(src_cell, src_layout, SI_LAYER)
    devrec_bbox = _get_layer_bbox(src_cell, src_layout, DEVREC_LAYER)

    if si_bbox.empty():
        si_bbox = src_bbox
    if devrec_bbox.empty():
        devrec_bbox = src_bbox

    si_bbox = _scale_box(si_bbox, src_layout.dbu, dst_layout.dbu)
    devrec_bbox = _scale_box(devrec_bbox, src_layout.dbu, dst_layout.dbu)

    _copy_pin_layer(src_cell, dst_cell, src_layout, dst_layout)

    si_index = dst_layout.layer(SI_LAYER)
    devrec_index = dst_layout.layer(DEVREC_LAYER)
    text_index = dst_layout.layer(TEXT_LAYER)

    dst_cell.shapes(si_index).insert(si_bbox)
    dst_cell.shapes(devrec_index).insert(devrec_bbox)

    label_text = src_cell.name + " (black box)"
    if not _insert_basic_text(dst_cell, si_bbox, dst_layout.dbu, label_text):
        _insert_fallback_text(dst_cell, text_index, si_bbox, dst_layout.dbu, label_text)


def _basic_text_mag(target_box, dbu, label_text):
    """按黑盒区域估算 Basic TEXT 放大倍数，并给文字边界留出余量。"""

    width_um = max(0.001, abs(target_box.width()) * dbu)
    height_um = max(0.001, abs(target_box.height()) * dbu)
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
    """Basic 库不可用时退回 primitive Text，保证黑盒包仍可生成。"""

    cx = (target_box.left + target_box.right) // 2
    cy = (target_box.bottom + target_box.top) // 2
    text = pya.Text(label_text, pya.Trans(pya.Trans.R0, cx, cy))
    shape = cell.shapes(text_index).insert(text)
    shape.text_halign = 1
    shape.text_valign = 1
    shape.text_dsize = _basic_text_mag(target_box, dbu, label_text) * 0.7


def _generate_blackbox_gds(package_root):
    """从白盒固定 GDS 生成黑盒固定 GDS。"""
    src_dir = PDK_ROOT / "pymacros" / "JNU_MWP_gds"
    dst_dir = package_root / "pymacros" / "JNU_MWP_blackbox_gds"
    dst_dir.mkdir(parents=True, exist_ok=True)

    if not src_dir.is_dir():
        raise RuntimeError("未找到白盒 GDS 目录：%s" % src_dir)

    count = 0
    for src_path in sorted(src_dir.glob("*.gds")):
        src_layout = pya.Layout()
        src_layout.read(str(src_path))

        dst_layout = pya.Layout()
        dst_layout.dbu = LIBRARY_DBU
        for top_cell in src_layout.each_top_cell():
            cell_obj = src_layout.cell(top_cell) if isinstance(top_cell, int) else top_cell
            if not cell_obj.bbox().empty():
                _draw_blackbox_cell(cell_obj, src_layout, dst_layout)

        if len(list(dst_layout.each_cell())) == 0:
            continue

        dst_layout.write(str(dst_dir / src_path.name))
        count += 1

    return count


def _rewrite_technology_file(lyt_root, base_path, original_base_path, layer_path):
    """把 .lyt 中的路径改成当前发布包路径。"""
    lyt_path = lyt_root / "JNU_MWP_PDK.lyt"
    tree = ET.parse(str(lyt_path))
    root = tree.getroot()

    for tag, value in (
        ("name", TECH_NAME),
        ("base-path", base_path.as_posix()),
        ("original-base-path", original_base_path.as_posix()),
        ("layer-properties_file", layer_path.as_posix()),
    ):
        node = root.find(tag)
        if node is not None:
            node.text = value

    tree.write(str(lyt_path), encoding="utf-8", xml_declaration=True)


def _copy_technology_folder(tech_root, package_root):
    """生成发布包中的 tech/JNU_MWP_PDK，用于 KLayout 原生注册 Technology。"""
    tech_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(PDK_ROOT / "JNU_MWP_PDK.lyt"), str(tech_root / "JNU_MWP_PDK.lyt"))
    shutil.copy2(str(PDK_ROOT / "layers.lyp"), str(tech_root / "layers.lyp"))

    _rewrite_technology_file(
        tech_root,
        base_path=package_root,
        original_base_path=tech_root,
        layer_path=tech_root / "layers.lyp",
    )


def _installer_source():
    """返回可选安装脚本源码，用于在接收方机器上重写 .lyt 绝对路径。"""
    return (
        "# -*- coding: utf-8 -*-\n"
        "# 创建者: Junyi Zhang\n"
        "# 时间: 2026-06\n\n"
        "# 可选安装脚本：把本发布包中的 salt 和 tech 目录安装到当前用户 KLayout 目录，"
        "并重写 Technology 路径。\n\n"
        "import shutil\n"
        "from pathlib import Path\n"
        "import xml.etree.ElementTree as ET\n\n\n"
        "TECH_NAME = \"JNU_MWP_PDK\"\n"
        "PACKAGE_NAME = \"JNU_MWP_PDK\"\n"
        "LOADER_MACRO_NAME = \"JNU_MWP_PDK_blackbox_loader.py\"\n\n\n"
        "def _rewrite_lyt(lyt_root, base_path, original_base_path, layer_path):\n"
        "    \"\"\"把安装后的 .lyt 路径写成当前用户机器上的真实路径。\"\"\"\n"
        "    lyt_path = lyt_root / \"JNU_MWP_PDK.lyt\"\n"
        "    tree = ET.parse(str(lyt_path))\n"
        "    root = tree.getroot()\n"
        "    for tag, value in (\n"
        "        (\"name\", TECH_NAME),\n"
        "        (\"base-path\", base_path.as_posix()),\n"
        "        (\"original-base-path\", original_base_path.as_posix()),\n"
        "        (\"layer-properties_file\", layer_path.as_posix()),\n"
        "    ):\n"
        "        node = root.find(tag)\n"
        "        if node is not None:\n"
        "            node.text = value\n"
        "    tree.write(str(lyt_path), encoding=\"utf-8\", xml_declaration=True)\n\n\n"
        "def _replace_dir(src, dst):\n"
        "    \"\"\"只替换 JNU_MWP_PDK 目标目录，避免影响 KLayout 其他文件。\"\"\"\n"
        "    if src.resolve() == dst.resolve():\n"
        "        return\n"
        "    if dst.exists():\n"
        "        shutil.rmtree(str(dst))\n"
        "    shutil.copytree(str(src), str(dst))\n\n\n"
        "def _copy_file(src, dst):\n"
        "    \"\"\"复制单个 loader 宏；源和目标相同时只保留原文件。\"\"\"\n"
        "    if not src.is_file():\n"
        "        return\n"
        "    if src.resolve() == dst.resolve():\n"
        "        return\n"
        "    dst.parent.mkdir(parents=True, exist_ok=True)\n"
        "    shutil.copy2(str(src), str(dst))\n\n\n"
        "def main():\n"
        "    release_root = Path(__file__).resolve().parent\n"
        "    klayout_root = Path.home() / \"KLayout\"\n"
        "    src_salt = release_root / \"salt\" / PACKAGE_NAME\n"
        "    src_tech = release_root / \"tech\" / PACKAGE_NAME\n"
        "    src_loader = release_root / \"pymacros\" / LOADER_MACRO_NAME\n"
        "    dst_salt = klayout_root / \"salt\" / PACKAGE_NAME\n"
        "    dst_tech = klayout_root / \"tech\" / PACKAGE_NAME\n"
        "    dst_loader = klayout_root / \"pymacros\" / LOADER_MACRO_NAME\n\n"
        "    if not src_salt.is_dir() or not src_tech.is_dir():\n"
        "        raise RuntimeError(\"发布包缺少 salt/JNU_MWP_PDK 或 tech/JNU_MWP_PDK。\")\n\n"
        "    (klayout_root / \"salt\").mkdir(parents=True, exist_ok=True)\n"
        "    (klayout_root / \"tech\").mkdir(parents=True, exist_ok=True)\n"
        "    (klayout_root / \"pymacros\").mkdir(parents=True, exist_ok=True)\n"
        "    _replace_dir(src_salt, dst_salt)\n"
        "    _replace_dir(src_tech, dst_tech)\n\n"
        "    _copy_file(src_loader, dst_loader)\n\n"
        "    _rewrite_lyt(dst_salt, dst_salt, dst_tech, dst_salt / \"layers.lyp\")\n"
        "    _rewrite_lyt(dst_tech, dst_salt, dst_tech, dst_tech / \"layers.lyp\")\n"
        "    print(\"JNU_MWP_PDK 黑盒 PDK 已安装到：%s\" % klayout_root)\n"
        "    print(\"请重启 KLayout 或执行 Reload Macros。\")\n\n\n"
        "if __name__ == \"__main__\":\n"
        "    main()\n"
    )


def _uninstaller_source():
    """返回卸载脚本源码，只删除 JNU_MWP_PDK 自己的 salt 和 tech 目录。"""
    return (
        "# -*- coding: utf-8 -*-\n"
        "# 创建者: Junyi Zhang\n"
        "# 时间: 2026-06\n\n"
        "# JNU_MWP_PDK 黑盒 PDK 卸载脚本。\n"
        "# 运行后会删除当前用户 KLayout 目录中的 salt/JNU_MWP_PDK 和 tech/JNU_MWP_PDK。\n\n"
        "import shutil\n"
        "from pathlib import Path\n\n\n"
        "PACKAGE_NAME = \"JNU_MWP_PDK\"\n"
        "LOADER_MACRO_NAME = \"JNU_MWP_PDK_blackbox_loader.py\"\n\n\n"
        "def _safe_remove_pdk_dir(path, expected_parent_name):\n"
        "    \"\"\"只允许删除 KLayout/salt 或 KLayout/tech 下的 JNU_MWP_PDK 目录。\"\"\"\n"
        "    resolved = path.resolve()\n"
        "    if resolved.name != PACKAGE_NAME or resolved.parent.name != expected_parent_name:\n"
        "        raise RuntimeError(\"拒绝删除非 JNU_MWP_PDK 目录：%s\" % resolved)\n"
        "    if resolved.exists():\n"
        "        shutil.rmtree(str(resolved))\n"
        "        print(\"已删除：%s\" % resolved)\n"
        "    else:\n"
        "        print(\"未找到，跳过：%s\" % resolved)\n\n\n"
        "def _safe_remove_loader(path):\n"
        "    \"\"\"删除 JNU 根目录 loader，不影响其他 pymacros。\"\"\"\n"
        "    resolved = path.resolve()\n"
        "    if resolved.name != LOADER_MACRO_NAME or resolved.parent.name != \"pymacros\":\n"
        "        raise RuntimeError(\"拒绝删除非 JNU loader：%s\" % resolved)\n"
        "    if resolved.exists():\n"
        "        resolved.unlink()\n"
        "        print(\"已删除：%s\" % resolved)\n"
        "    else:\n"
        "        print(\"未找到，跳过：%s\" % resolved)\n\n\n"
        "def main():\n"
        "    klayout_root = Path.home() / \"KLayout\"\n"
        "    salt_dir = klayout_root / \"salt\" / PACKAGE_NAME\n"
        "    tech_dir = klayout_root / \"tech\" / PACKAGE_NAME\n"
        "    loader_file = klayout_root / \"pymacros\" / LOADER_MACRO_NAME\n"
        "    _safe_remove_pdk_dir(salt_dir, \"salt\")\n"
        "    _safe_remove_pdk_dir(tech_dir, \"tech\")\n"
        "    _safe_remove_loader(loader_file)\n"
        "    print(\"JNU_MWP_PDK 已卸载。请重启 KLayout 或执行 Reload Macros。\")\n\n\n"
        "if __name__ == \"__main__\":\n"
        "    main()\n"
    )


def _write_install_note(release_root, package_root, tech_root):
    """写入安装说明，明确必须同时安装 salt 和 tech。"""
    note = (
        "JNU_MWP_PDK 黑盒发布包\n"
        "======================\n\n"
        "推荐安装方式：\n"
        "1. 在本目录运行：python install_blackbox_pdk.py\n"
        "2. 重启 KLayout 或执行 Reload Macros。\n"
        "3. Technology 下应显示 JNU_MWP_PDK，Library 面板中应显示 JNULib_BlackBox。\n\n"
        "手动安装方式：\n"
        "将当前文件夹内容复制到 C:\\Users\\<用户名>\\KLayout\n\n"
        "卸载方式：\n"
        "1. 运行 uninstall_blackbox_pdk.py。\n"
        "2. 重启 KLayout 或执行 Reload Macros。\n\n"
        "注意：\n"
        "- 本发布包不包含白盒固定器件 GDS。\n"
        "- 固定器件来自 salt/JNU_MWP_PDK/pymacros/JNU_MWP_blackbox_gds/。\n"
        "- 黑盒器件库只包含固定黑盒器件，不生成、不打包 PCell。\n"
    )
    (release_root / "README_BLACKBOX_INSTALL.txt").write_text(note, encoding="utf-8", newline="\n")
    (release_root / "install_blackbox_pdk.py").write_text(_installer_source(), encoding="utf-8", newline="\n")
    (release_root / "uninstall_blackbox_pdk.py").write_text(_uninstaller_source(), encoding="utf-8", newline="\n")
    print("Salt 安装目录：%s" % package_root)
    print("Technology 安装目录：%s" % tech_root)


def package_blackbox_pdk(output_root):
    """生成黑盒 PDK 发布文件夹。"""
    release_root = Path(output_root)
    package_root = release_root / "salt" / SALT_PACKAGE_NAME
    tech_root = release_root / "tech" / TECH_FOLDER_NAME

    _safe_remove_output(release_root)
    release_root.mkdir(parents=True, exist_ok=True)

    _copy_required_files(package_root)
    count = _generate_blackbox_gds(package_root)
    _copy_technology_folder(tech_root, package_root)
    _write_root_loader(release_root)

    # Salt 包内也保留一份 .lyt，供辅助加载和开发调试使用。
    _rewrite_technology_file(
        package_root,
        base_path=package_root,
        original_base_path=tech_root,
        layer_path=package_root / "layers.lyp",
    )

    _write_install_note(release_root, package_root, tech_root)
    _verify_blackbox_exclusions(release_root, package_root)
    return count, package_root, tech_root


def _verify_blackbox_exclusions(release_root, package_root):
    """生成后显式检查白盒源码、canonical skill 和 KLayout 配置未进入发布包。"""
    forbidden = (
        package_root / "pymacros" / "JNU_MWP_skill",
        package_root / "pymacros" / "JNU_MWP_skills",
        package_root / "pymacros" / "JNU_MWP_pcells",
        package_root / "pymacros" / "JNU_MWP_gds",
        package_root / "pymacros" / "JNULib.py",
        package_root / "pymacros" / "JNU_MWP_tools" / "release",
        package_root / "pymacros" / "JNU_MWP_tools" / "tests",
    )
    found = [str(path) for path in forbidden if path.exists()]
    found.extend(
        str(path)
        for path in Path(release_root).rglob("klayoutrc*")
        if path.is_file()
    )
    if found:
        raise RuntimeError("黑盒发布包包含禁止文件：%s" % ", ".join(found))


def main():
    parser = argparse.ArgumentParser(description="生成 JNU_MWP_PDK 黑盒发布文件夹")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="输出目录，默认：%(default)s",
    )
    args = parser.parse_args()

    output_root = Path(args.output)
    count, package_root, tech_root = package_blackbox_pdk(output_root)
    print("黑盒 PDK 发布目录已生成：%s" % output_root)
    print("可复制到 KLayout/salt 的目录：%s" % package_root)
    print("可复制到 KLayout/tech 的目录：%s" % tech_root)
    print("黑盒固定 GDS 数量：%d" % count)


if __name__ == "__main__":
    main()
