# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""把已安装 EBeam PDK 的器件库同时注册到 JNU 技术视图。"""

import os

import pya


JNU_TECHNOLOGY_NAME = "JNU_MWP_PDK"
EBEAM_TECHNOLOGY_NAME = "EBeam"

# 每项都与 EBeam PDK 的启动加载器使用的目录对应。Library 名称保持不变，
# 仅在 JNU 技术下额外注册一个同名库，使 KLayout 依据当前 Technology 筛选时
# 仍能列出相同的 EBeam 器件集合。
EBEAM_LIBRARY_SPECS = (
    ("EBeam", "v0.4.53, Components with models", "gds/EBeam", "pymacros/pcells_EBeam"),
    ("EBeam_Beta", "v0.4.53, Beta components", "gds/EBeam_Beta", "pymacros/pcells_EBeam_Beta"),
    ("EBeam-Dream", "v0.4.53, Dream Photonics", "gds/EBeam_Dream", "pymacros/pcells_EBeam_Dream"),
    ("EBeam-SiN", "v0.4.53, Silicon Nitride", "gds/EBeam_SiN", "pymacros/pcells_SiN"),
    ("EBeam-ANT", "v0.4.53, ANT components", "gds/ANT", ""),
)


def _library_description(library_name, fallback):
    """优先复用当前 EBeam 库的说明，以跟随已安装 PDK 的发行版本。"""

    library = pya.Library.library_by_name(library_name, EBEAM_TECHNOLOGY_NAME)
    if library is None:
        return fallback
    description = str(library.description or "").strip()
    return description or fallback


def _ebeam_base_path():
    """取得 EBeam Technology 的安装根目录；未安装时返回空字符串。"""

    technology = pya.Technology.technology_by_name(EBEAM_TECHNOLOGY_NAME)
    if technology is None:
        return ""
    return str(technology.default_base_path or "")


def register_ebeam_libraries_for_jnu():
    """为 JNU_MWP_PDK 技术注册已安装 EBeam PDK 的同名 Library 视图。

    该函数不改变原 EBeam Technology 或其已注册 Library。若 EBeam PDK 尚未
    安装或尚未加载，静默跳过；JNU PDK 仍可以独立工作。
    """

    if pya.Technology.technology_by_name(JNU_TECHNOLOGY_NAME) is None:
        raise RuntimeError("未加载 %s Technology。" % JNU_TECHNOLOGY_NAME)

    ebeam_root = _ebeam_base_path()
    if not ebeam_root or not os.path.isdir(ebeam_root):
        return {"available": False, "created": (), "existing": ()}

    try:
        from SiEPIC.scripts import load_klayout_library
    except ImportError:
        return {"available": False, "created": (), "existing": ()}

    created = []
    existing = []
    for library_name, fallback_description, gds_folder, pcell_folder in EBEAM_LIBRARY_SPECS:
        if pya.Library.library_by_name(library_name, JNU_TECHNOLOGY_NAME) is not None:
            existing.append(library_name)
            continue

        gds_path = os.path.join(ebeam_root, gds_folder)
        pcell_path = os.path.join(ebeam_root, pcell_folder) if pcell_folder else ""
        load_klayout_library(
            JNU_TECHNOLOGY_NAME,
            library_name,
            _library_description(library_name, fallback_description),
            gds_path,
            pcell_path,
            verbose=False,
        )
        if pya.Library.library_by_name(library_name, JNU_TECHNOLOGY_NAME) is None:
            raise RuntimeError("未能注册 EBeam Library: %s" % library_name)
        created.append(library_name)

    return {
        "available": True,
        "created": tuple(created),
        "existing": tuple(existing),
    }


__all__ = [
    "EBEAM_LIBRARY_SPECS",
    "EBEAM_TECHNOLOGY_NAME",
    "JNU_TECHNOLOGY_NAME",
    "register_ebeam_libraries_for_jnu",
]
