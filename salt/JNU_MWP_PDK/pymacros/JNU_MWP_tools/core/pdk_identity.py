# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""统一界面名称、版本及技术注册，并迁移旧技术选择。"""

from pathlib import Path

import pya


TECHNOLOGY_NAME = "JNU_MWP_SOI_PDK"
LEGACY_TECHNOLOGY_NAME = "JNU_MWP_PDK"
PDK_VERSION = "V1.5"
MENU_TITLE = "%s %s" % (TECHNOLOGY_NAME, PDK_VERSION)
PDK_ROOT = Path(__file__).resolve().parents[3]
TECHNOLOGY_FILE = "JNU_MWP_PDK.lyt"


def _value(obj, name, *args):
    """兼容 KLayout 的属性和方法两种绑定形式。"""
    value = getattr(obj, name)
    return value(*args) if callable(value) else value


def _migrate_technology_state():
    """保留器件库对象及用户设置，只替换旧 JNU 技术关联。"""
    for library_id in pya.Library.library_ids():
        library = pya.Library.library_by_id(library_id)
        technologies = list(_value(library, "technologies"))
        if LEGACY_TECHNOLOGY_NAME in technologies:
            library.clear_technologies()
            for name in dict.fromkeys(
                TECHNOLOGY_NAME if name == LEGACY_TECHNOLOGY_NAME else name for name in technologies
            ):
                library.add_technology(name)

    if not hasattr(pya, "Application"):
        return
    app = pya.Application.instance()
    if app.get_config("initial-technology") == LEGACY_TECHNOLOGY_NAME:
        app.set_config("initial-technology", TECHNOLOGY_NAME)
    # MRU 中只替换技术字段，文件路径和其他技术记录保持原值。
    mru = app.get_config("mru") or ""
    migrated = mru.replace("@'%s'" % LEGACY_TECHNOLOGY_NAME, "@'%s'" % TECHNOLOGY_NAME)
    if migrated != mru:
        app.set_config("mru", migrated)

    window = app.main_window()
    if window is None:
        return
    views = _value(window, "views")
    if isinstance(views, int):
        views = [_value(window, "view", index) for index in range(views)]
    for view in views:
        for index in range(_value(view, "cellviews")):
            cellview = view.cellview(index)
            if _value(cellview, "technology") == LEGACY_TECHNOLOGY_NAME:
                cellview.technology = TECHNOLOGY_NAME


def load_jnu_technology(pdk_root=PDK_ROOT):
    """加载包内唯一技术配置；旧注册改名，重复调用保持单一技术入口。"""
    tech_file = Path(pdk_root) / TECHNOLOGY_FILE
    if not tech_file.is_file():
        raise FileNotFoundError("未找到 JNU Technology 配置：%s" % tech_file)
    if pya.Technology.has_technology(TECHNOLOGY_NAME):
        technology = pya.Technology.technology_by_name(TECHNOLOGY_NAME)
    elif pya.Technology.has_technology(LEGACY_TECHNOLOGY_NAME):
        technology = pya.Technology.technology_by_name(LEGACY_TECHNOLOGY_NAME)
        technology.name = TECHNOLOGY_NAME
    else:
        technology = pya.Technology.create_technology(TECHNOLOGY_NAME)
    technology.load(str(tech_file))
    technology.name = TECHNOLOGY_NAME
    _migrate_technology_state()
    if pya.Technology.has_technology(LEGACY_TECHNOLOGY_NAME):
        pya.Technology.remove_technology(LEGACY_TECHNOLOGY_NAME)
    return technology
