# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

"""验证包内唯一的 JNU Technology 配置搬迁后仍可独立加载。"""

from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET

import pya


PDK_ROOT = Path(__file__).resolve().parents[3]
LYT_NAME = "JNU_MWP_PDK.lyt"
TECH_NAME = "JNU_MWP_PDK_PortabilityRegression"


def _assert(condition, message):
    if not condition:
        raise RuntimeError(message)


def _copy_technology(source_root, destination_root):
    """仅复制 Technology 加载所需的 .lyt 与同目录图层配置。"""
    destination_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_root / LYT_NAME, destination_root / LYT_NAME)
    shutil.copy2(source_root / "layers.lyp", destination_root / "layers.lyp")


def _verify_portable_fields(lyt_path):
    """确认配置没有把作者电脑目录带入发布文件。"""
    root = ET.parse(str(lyt_path)).getroot()
    _assert((root.findtext("base-path") or "") == "", "%s 包含 base-path。" % lyt_path)
    _assert((root.findtext("original-base-path") or "") == "", "%s 包含 original-base-path。" % lyt_path)
    _assert(
        (root.findtext("layer-properties_file") or "") == "layers.lyp",
        "%s 图层配置不是相对路径。" % lyt_path,
    )
    _assert("C:/Users/zjy" not in lyt_path.read_text(encoding="utf-8"), "%s 残留作者目录。" % lyt_path)


def main():
    """将包内配置搬迁到另一用户目录，验证技术及相对图层路径。"""
    with tempfile.TemporaryDirectory(prefix="jnu_pdk_portable_") as temporary_directory:
        install_root = Path(temporary_directory) / "another-user" / "KLayout"
        salt_copy = install_root / "salt" / "JNU_MWP_PDK"
        _copy_technology(PDK_ROOT, salt_copy)
        _verify_portable_fields(salt_copy / LYT_NAME)
        _assert(not (install_root / "tech").exists(), "不应依赖额外的 tech 目录。")

        tech = pya.Technology().create_technology(TECH_NAME)
        tech.load(str(salt_copy / LYT_NAME))
        layer_path = Path(tech.eff_layer_properties_file())
        _assert(layer_path.is_file(), "搬迁后的图层配置无法解析。")
        _assert(layer_path.resolve() == (salt_copy / "layers.lyp").resolve(), "图层配置未使用包内副本。")

    print("OK: portable JNU_MWP_PDK technology loads after relocation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
