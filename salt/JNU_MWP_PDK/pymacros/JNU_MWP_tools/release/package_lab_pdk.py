# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

"""生成仅在实验室内分发的完整 Salt Package，含白盒固定 GDS。"""

import argparse
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET


PDK_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = Path(__file__).resolve().parent / "lab_package"
PACKAGE_NAME = "JNU_MWP_PDK"


def _copy_tree(source, destination):
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", "*.pyo", "*.log", "klayoutrc*",
    ))


def build_package(output, source=PDK_ROOT, gds_source=None):
    """使用白名单构建新目录；已有交付物由用户另选版本保存。"""
    source = Path(source).resolve()
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("输出目录已存在，请指定新目录：%s" % output)
    if output == source or source in output.parents:
        raise ValueError("交付目录必须位于 PDK 源码之外。")
    fixed_gds = Path(gds_source).resolve() if gds_source else source / "pymacros" / "JNU_MWP_gds"
    gds_count = len(list(fixed_gds.glob("*.gds")))
    if not gds_count:
        raise RuntimeError("完整实验室包需要本机白盒 GDS 目录：%s" % fixed_gds)
    license_file = source.parents[1] / "LICENSE.md"
    if not license_file.is_file():
        raise FileNotFoundError("未找到项目 LICENSE.md：%s" % license_file)

    package = output / PACKAGE_NAME
    package.mkdir(parents=True)
    for filename in ("grain.xml", "__init__.py", "layers.lyp", "JNU_MWP_PDK.lyt"):
        shutil.copy2(source / filename, package / filename)
    shutil.copy2(license_file, package / "LICENSE.md")
    for name in ("drc", "d25", "lvs", "macros", "xsect"):
        if (source / name).is_dir():
            _copy_tree(source / name, package / name)

    macros = package / "pymacros"
    macros.mkdir()
    for filename in (
        "__init__.py", "JNULib.py", "JNULib_BlackBox.py",
        "JNU_MWP_PDK_Startup.lym", "JNU_MWP_PDK_Menu.lym",
        "JNU_MWP_InternalWaveguideRegistry.lym",
    ):
        shutil.copy2(source / "pymacros" / filename, macros / filename)
    for name in ("JNU_MWP_pcells", "JNU_MWP_blackbox", "Keybindings"):
        _copy_tree(source / "pymacros" / name, macros / name)
    # 独立私有器件库只提取 GDS，不携带 Git 元数据、维护脚本或账户凭据。
    destination_gds = macros / "JNU_MWP_gds"
    destination_gds.mkdir()
    for path in sorted(fixed_gds.glob("*.gds")):
        shutil.copy2(path, destination_gds / path.name)
    tools = macros / "JNU_MWP_tools"
    tools.mkdir()
    shutil.copy2(source / "pymacros" / "JNU_MWP_tools" / "__init__.py", tools / "__init__.py")
    for name in ("core", "actions"):
        _copy_tree(source / "pymacros" / "JNU_MWP_tools" / name, tools / name)

    # 保留 pymacros/__init__.py 的普通 autorun，在主窗口建立后统一加载库。
    # 其他库入口取消独立 autorun，避免重复注册以及早期导入第三方 GUI。
    for filename in ("JNULib.py", "JNULib_BlackBox.py", "JNU_MWP_blackbox/__init__.py"):
        path = macros / filename
        code = path.read_text(encoding="utf-8")
        path.write_text(code.replace("# $autorun\n", "", 1), encoding="utf-8")

    tree = ET.parse(package / "JNU_MWP_PDK.lyt")
    for name, value in (("base-path", ""), ("original-base-path", ""),
                        ("layer-properties_file", "layers.lyp")):
        tree.getroot().find(name).text = value
    tree.write(package / "JNU_MWP_PDK.lyt", encoding="utf-8", xml_declaration=True)

    # 完整包的更新来源由接收方入口脚本绑定到内部交付目录。
    grain = ET.parse(package / "grain.xml")
    grain.getroot().find("title").text = "JNU MWP PDK - Laboratory Full Edition"
    grain.getroot().find("doc").text = "Complete laboratory package with fixed GDS, PCells, menus and DRC. Internal distribution."
    grain.getroot().find("url").text = ""
    grain.write(package / "grain.xml", encoding="utf-8", xml_declaration=True)

    for name in ("Open_Lab_Package_Manager.ps1", "README_LAB_INSTALL.md"):
        shutil.copy2(TEMPLATES / name, output / name)
    shutil.copy2(TEMPLATES / "README_LAB_INSTALL.md", package / "README_LAB_INSTALL.md")
    if (package / "tech").exists():
        raise RuntimeError("实验室包不应依赖 tech 副本。")
    print("完整实验室 Package：%s" % output)
    print("白盒固定 GDS：%d 个；请仅在实验室内部发放。" % gds_count)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--gds-source", type=Path, help="私有器件库 checkout 中的 JNU_MWP_gds 目录")
    parser.add_argument("--zip", action="store_true", help="同时生成便于内部分发的 ZIP")
    args = parser.parse_args()
    version = ET.parse(PDK_ROOT / "grain.xml").getroot().findtext("version")
    output = args.output or Path.home() / "Desktop" / ("JNU_MWP_PDK_lab_package_v" + version)
    if args.zip and Path(str(output) + ".zip").exists():
        raise FileExistsError("同名交付 ZIP 已存在，请指定新的 --output。")
    build_package(output, gds_source=args.gds_source)
    if args.zip:
        archive = shutil.make_archive(str(output), "zip", root_dir=output.parent, base_dir=output.name)
        print("内部交付压缩包：%s" % archive)


if __name__ == "__main__":
    main()
