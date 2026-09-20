# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-08

"""在版图文件解析前注册 Path to Waveguide 使用的本地 PCell 声明。"""

import builtins
import importlib

import pya


INTERNAL_WAVEGUIDE_PCELL_NAMES = ("Waveguide", "Composite_Waveguide")
_STATE_KEY = "_jnu_mwp_internal_waveguide_registry_state"
_REGISTRATION_STATE = getattr(builtins, _STATE_KEY, None)
if _REGISTRATION_STATE is None:
    _REGISTRATION_STATE = {
        "view_file_open_hooks": [],
        "view_cellviews_hooks": [],
        "main_window_hooks": [],
        "main_window_timers": [],
    }
    setattr(builtins, _STATE_KEY, _REGISTRATION_STATE)
else:
    # 兼容旧版本已经写入 builtins 的状态结构。
    _REGISTRATION_STATE.setdefault("view_file_open_hooks", [])
    _REGISTRATION_STATE.setdefault("view_cellviews_hooks", [])
    _REGISTRATION_STATE.setdefault("main_window_hooks", [])
    _REGISTRATION_STATE.setdefault("main_window_timers", [])


def _property_or_call(obj, name, *args):
    value = getattr(obj, name)
    return value(*args) if callable(value) else value


def _has_hook(owner, hook_key):
    """判断长期状态中是否已保存指定 Qt 对象的回调引用。"""
    for existing_owner, _callback in _REGISTRATION_STATE[hook_key]:
        try:
            if existing_owner == owner:
                return True
        except Exception:
            if id(existing_owner) == id(owner):
                return True
    return False


def _remember_hook(owner, callback, hook_key):
    """持有 Qt 回调引用，避免 autorun 结束或模块热重载后被垃圾回收。"""
    _REGISTRATION_STATE[hook_key].append((owner, callback))


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
    try:
        factories = _declaration_factories()
    except ImportError:
        # 黑盒发布包不携带 JNU_MWP_pcells，注册器在该环境只跳过内部 PCell。
        return []
    registered = []
    for name in INTERNAL_WAVEGUIDE_PCELL_NAMES:
        if not replace and layout.pcell_declaration(name) is not None:
            continue
        layout.register_pcell(name, factories[name]())
        registered.append(name)
    # 若 GDS 已在声明注册前读入，refresh 会将保存的 PCell 参数重新关联到
    # 新声明；预注册场景下调用 refresh 也不会改变版图几何。
    if registered:
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
    """注册当前 CellView，并在文件读取或 CellView 创建后恢复内部 PCell。"""
    if view is None:
        return 0
    count = register_view_layouts(view)
    if not _has_hook(view, "view_file_open_hooks"):
        callback = lambda __view=view: _dynamic_register_view(__view)
        # GDS 读取可能快于本地 PCell 声明注册。on_file_open 在读入完成后
        # 调用 ensure_internal_waveguide_pcells()，其 Layout.refresh() 会恢复 variant。
        view.on_file_open = callback
        _remember_hook(view, callback, "view_file_open_hooks")
    if not _has_hook(view, "view_cellviews_hooks"):
        callback = lambda __view=view: _dynamic_register_view(__view)
        # 启动时可能已存在空的 LayoutView，而 create_layout()
        # 只是向它增加 CellView，不会触发 MainWindow 的新视图事件。
        # 监听此事件使内部 PCell 在 GDS 解析前即完成注册。
        view.on_cellviews_changed = callback
        _remember_hook(view, callback, "view_cellviews_hooks")
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
        pass
    # 部分 KLayout 版本在启动初期 views() 返回 0，但已经存在可供
    # create_layout() 复用的空视图。因此始终额外注册 current_view。
    try:
        view = _property_or_call(main_window, "current_view")
        if view is not None:
            views.append(view)
    except Exception:
        pass
    return [view for index, view in enumerate(views) if view is not None and view not in views[:index]]


def _dynamic_attach_view(main_window, index_or_view):
    """兼容不同 KLayout 版本的 on_view_created 回调参数形式。"""
    module = importlib.import_module(
        "JNU_MWP_tools.core.internal_waveguide_registry"
    )
    view = None
    try:
        # 常规情形下回调传入视图索引。
        view = _property_or_call(main_window, "view", int(index_or_view))
    except Exception:
        try:
            # 个别版本直接传入 LayoutView 对象。
            if _property_or_call(index_or_view, "cellviews") is not None:
                view = index_or_view
        except Exception:
            pass
    if view is None:
        try:
            view = _property_or_call(main_window, "current_view")
        except Exception:
            view = None
    module.attach_view(view)


def _on_view_created(main_window, *args):
    """处理 KLayout 视图创建事件。不同版本可能不传参数、传索引或直接传入视图对象。"""
    index_or_view = args[0] if args else None
    _dynamic_attach_view(main_window, index_or_view)


def _dynamic_attach_all_views(main_window):
    """周期扫描主窗口中的视图，作为 KLayout 视图事件的兼容保护。"""
    module = importlib.import_module(
        "JNU_MWP_tools.core.internal_waveguide_registry"
    )
    for view in module._main_window_views(main_window):
        module.attach_view(view)


def _install_view_sync_timer(main_window):
    """安装轻量定时器，确保无论空视图何时变为已打开版图都能补注册 PCell。"""
    if _has_hook(main_window, "main_window_timers"):
        return
    timer = pya.QTimer(main_window)
    timer.setInterval(100)
    callback = lambda __window=main_window: _dynamic_attach_all_views(__window)
    timer.timeout(callback)
    timer.start()
    # 回调与 QTimer 需要在 autorun 结束后继续存活，统一由 builtins 状态持有。
    _remember_hook(main_window, (timer, callback), "main_window_timers")


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
    if not _has_hook(main_window, "main_window_hooks"):
        callback = lambda *args, __window=main_window: _on_view_created(__window, *args)
        main_window.on_view_created(callback)
        _remember_hook(main_window, callback, "main_window_hooks")
    _install_view_sync_timer(main_window)
    return registered


__all__ = [
    "INTERNAL_WAVEGUIDE_PCELL_NAMES",
    "ensure_internal_waveguide_pcells",
    "register_view_layouts",
    "attach_view",
    "install_internal_waveguide_registration",
]
