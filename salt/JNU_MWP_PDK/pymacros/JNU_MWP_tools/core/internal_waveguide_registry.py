# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""在版图文件解析前注册 Path to Waveguide 使用的本地 PCell 声明。"""

import importlib

import pya


INTERNAL_WAVEGUIDE_PCELL_NAMES = ("Waveguide", "Composite_Waveguide")


def _property_or_call(obj, name, *args):
    value = getattr(obj, name)
    return value(*args) if callable(value) else value


def _declaration_factories():
    from JNU_MWP_pcells.composite_waveguide import CompositeWaveguide
    from JNU_MWP_pcells.waveguide import Waveguide

    return {
        "Waveguide": Waveguide,
        "Composite_Waveguide": CompositeWaveguide,
    }


def ensure_internal_waveguide_pcells(layout, replace=False):
    """在指定 Layout 中注册内部 PCell；replace 用于热重载后替换声明。"""
    if layout is None:
        return []
    factories = _declaration_factories()
    registered = []
    for name in INTERNAL_WAVEGUIDE_PCELL_NAMES:
        if not replace and layout.pcell_declaration(name) is not None:
            continue
        layout.register_pcell(name, factories[name]())
        registered.append(name)
    if replace and registered:
        layout.refresh()
    return registered


def _view_layouts(view):
    layouts = []
    try:
        count = int(_property_or_call(view, "cellviews"))
        for index in range(count):
            cellview = _property_or_call(view, "cellview", index)
            layout = _property_or_call(cellview, "layout")
            if layout is not None and all(layout != item for item in layouts):
                layouts.append(layout)
    except Exception:
        try:
            cellview = _property_or_call(view, "active_cellview")
            layout = _property_or_call(cellview, "layout")
            if layout is not None:
                layouts.append(layout)
        except Exception:
            pass
    return layouts


def register_view_layouts(view):
    """给视图现有的全部 CellView 注册内部 PCell。"""
    count = 0
    for layout in _view_layouts(view):
        count += len(ensure_internal_waveguide_pcells(layout))
    return count


def _dynamic_register_view(view):
    """通过动态导入调用最新模块，避免热重载后事件持有旧函数。"""
    module = importlib.import_module(
        "JNU_MWP_tools.core.internal_waveguide_registry"
    )
    module.register_view_layouts(view)


def attach_view(view):
    """注册当前 CellView，并监听同一视图后续创建的 CellView。"""
    if view is None:
        return 0
    count = register_view_layouts(view)
    if getattr(view, "_jnu_internal_waveguide_cellview_hook", None) is None:
        callback = lambda __view=view: _dynamic_register_view(__view)
        view.on_cellviews_changed = callback
        view._jnu_internal_waveguide_cellview_hook = callback
    return count


def _main_window_views(main_window):
    views = []
    try:
        count_or_views = _property_or_call(main_window, "views")
        if isinstance(count_or_views, int):
            for index in range(int(count_or_views)):
                views.append(_property_or_call(main_window, "view", index))
        else:
            views.extend(list(count_or_views))
    except Exception:
        try:
            view = _property_or_call(main_window, "current_view")
            if view is not None:
                views.append(view)
        except Exception:
            pass
    return [view for index, view in enumerate(views) if view is not None and view not in views[:index]]


def _dynamic_attach_view(main_window, index):
    module = importlib.import_module(
        "JNU_MWP_tools.core.internal_waveguide_registry"
    )
    view = _property_or_call(main_window, "view", index)
    module.attach_view(view)


def install_internal_waveguide_registration(main_window=None):
    """安装一次全局 View 创建监听，并处理当前已经打开的视图。"""
    if main_window is None:
        try:
            main_window = pya.Application.instance().main_window()
        except Exception:
            main_window = None
    if main_window is None:
        return 0

    registered = sum(attach_view(view) for view in _main_window_views(main_window))
    if getattr(main_window, "_jnu_internal_waveguide_view_hook", None) is None:
        callback = lambda index, __window=main_window: _dynamic_attach_view(__window, index)
        main_window.on_view_created(callback)
        main_window._jnu_internal_waveguide_view_hook = callback
    return registered


__all__ = [
    "INTERNAL_WAVEGUIDE_PCELL_NAMES",
    "ensure_internal_waveguide_pcells",
    "register_view_layouts",
    "attach_view",
    "install_internal_waveguide_registration",
]
