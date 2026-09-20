# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

"""验证 JNU Technology 配置可复制到任意用户目录后直接加载。"""

from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET

import pya


PDK_ROOT = Path(__file__).resolve().parents[2]
KLAYOUT_ROOT = PDK_ROOT.parents[1]
TECH_ROOT = KLAYOUT_ROOT / "tech" / "JNU_MWP_PDK"
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
    """复制 salt/tech 配置到临时安装根并用 KLayout API 加载。"""
    with tempfile.TemporaryDirectory(prefix="jnu_pdk_portable_") as temporary_directory:
        install_root = Path(temporary_directory) / "another-user" / "KLayout"
        salt_copy = install_root / "salt" / "JNU_MWP_PDK"
        tech_copy = install_root / "tech" / "JNU_MWP_PDK"
        _copy_technology(PDK_ROOT, salt_copy)
        _copy_technology(TECH_ROOT, tech_copy)

        for lyt_path in (salt_copy / LYT_NAME, tech_copy / LYT_NAME):
            _verify_portable_fields(lyt_path)

        tech = pya.Technology().create_technology(TECH_NAME)
        tech.load(str(tech_copy / LYT_NAME))

    print("OK: portable JNU_MWP_PDK technology loads after relocation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
