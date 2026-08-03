# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-08

"""在不重启 KLayout 的情况下重新加载 JNU_MWP_PDK 运行时代码。"""

import importlib
import os
import sys

import pya


LIBRARY_NAME = "JNULib"
BLACKBOX_LIBRARY_NAME = "JNULib_BlackBox"
INTERNAL_WAVEGUIDE_PCELLS = ("Waveguide", "Composite_Waveguide")
_THIS_MODULE = __name__
_PYMACROS_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_MENU_MACRO = os.path.join(_PYMACROS_DIR, "JNU_MWP_PDK_Menu.lym")
# importlib.reload 会复用模块字典；保留尚未触发的 timer，避免重复菜单回调。
_PENDING_RELOAD_TIMER = globals().get("_PENDING_RELOAD_TIMER", None)


def _property_or_call(obj, name, *args):
    """兼容 KLayout Python 属性和方法两种绑定形式。"""

    value = getattr(obj, name)
    return value(*args) if callable(value) else value


def _append_unique_object(items, value):
    """按底层对象相等关系去重，包装器不支持比较时退回对象标识。"""

    if value is None:
        return
    for existing in items:
        try:
            if existing == value:
                return
        except Exception:
            if id(existing) == id(value):
                return
    items.append(value)


def _open_views(main_window):
    """取得全部 LayoutView；旧版绑定不支持枚举时至少返回当前视图。"""

    views = []
    try:
        view_count_or_list = _property_or_call(main_window, "views")
        if isinstance(view_count_or_list, int):
            for index in range(int(view_count_or_list)):
                _append_unique_object(
                    views,
                    _property_or_call(main_window, "view", index),
                )
        else:
            for view in view_count_or_list:
                _append_unique_object(views, view)
    except Exception:
        pass

    try:
        _append_unique_object(
            views,
            _property_or_call(main_window, "current_view"),
        )
    except Exception:
        pass
    return views


def _view_layouts(view):
    """取得一个 LayoutView 中的全部 layout。"""

    layouts = []
    try:
        cellview_count = _property_or_call(view, "cellviews")
        for index in range(int(cellview_count)):
            cellview = _property_or_call(view, "cellview", index)
            _append_unique_object(
                layouts,
                _property_or_call(cellview, "layout"),
            )
    except Exception:
        try:
            cellview = _property_or_call(view, "active_cellview")
            _append_unique_object(
                layouts,
                _property_or_call(cellview, "layout"),
            )
        except Exception:
            pass
    return layouts


def _open_layouts(main_window):
    """取得当前 KLayout 会话中已打开的全部 layout。"""

    layouts = []
    for view in _open_views(main_window):
        for layout in _view_layouts(view):
            _append_unique_object(layouts, layout)
    return layouts


def _purge_runtime_modules():
    """移除 JNU 运行时模块，使后续 import 从磁盘重新执行。"""

    prefixes = ("JNU_MWP_pcells", "JNU_MWP_tools", "JNU_MWP_blackbox")
    removed = []
    for module_name in sorted(tuple(sys.modules), key=len, reverse=True):
        is_jnu_module = module_name in ("JNULib", "JNULib_BlackBox") or any(
            module_name == prefix or module_name.startswith(prefix + ".")
            for prefix in prefixes
        )
        if not is_jnu_module or module_name == _THIS_MODULE:
            continue
        removed.append(module_name)
        sys.modules.pop(module_name, None)
    importlib.invalidate_caches()
    return removed


def _replace_internal_waveguide_declarations(layout):
    """替换已存在的工具内部 PCell 声明，并保留原有 PCell ID。"""
    from JNU_MWP_tools.core.internal_waveguide_registry import (
        ensure_internal_waveguide_pcells,
    )

    return ensure_internal_waveguide_pcells(layout, replace=True)


def _reload_runtime(layouts):
    """重建公开器件库，并刷新已打开版图中的公开及内部 PCell。"""

    try:
        _purge_runtime_modules()
        importlib.import_module("JNULib")
        importlib.import_module("JNULib_BlackBox")
        library = pya.Library.library_by_name(LIBRARY_NAME)
        if library is None:
            raise RuntimeError("重新导入后未找到 %s。" % LIBRARY_NAME)
        blackbox_library = pya.Library.library_by_name(BLACKBOX_LIBRARY_NAME)
        if blackbox_library is None:
            raise RuntimeError("重新导入后未找到 %s。" % BLACKBOX_LIBRARY_NAME)
    except Exception as error:
        raise RuntimeError("重新导入 Python/PCell 模块阶段失败：%s" % error) from error

    # Library.refresh 更新所有引用公开库的 client layout。
    for public_library in (library, blackbox_library):
        try:
            public_library.refresh()
        except Exception as error:
            raise RuntimeError(
                "刷新公开库 %s 阶段失败：%s" % (public_library.name(), error)
            ) from error
    internal_refresh_count = 0
    for layout_index, layout in enumerate(layouts, 1):
        try:
            internal_refresh_count += len(
                _replace_internal_waveguide_declarations(layout)
            )
        except Exception as error:
            raise RuntimeError(
                "刷新第 %d 个已打开 layout 的内部波导阶段失败：%s"
                % (layout_index, error)
            ) from error
    return {
        "library": library,
        "blackbox_library": blackbox_library,
        "layout_count": len(layouts),
        "internal_refresh_count": internal_refresh_count,
    }


def _reload_menu_macro():
    """重新执行菜单宏，使菜单结构和回调代码同步更新。"""

    if not os.path.isfile(_MENU_MACRO):
        raise RuntimeError("未找到菜单宏：%s" % _MENU_MACRO)
    pya.Macro(_MENU_MACRO).run()


def reload_jnu_pdk(main_window=None, reload_menu=True):
    """同步重载 JNU PDK；测试可传入 main_window=None 并关闭菜单重载。"""

    if main_window is None:
        try:
            main_window = pya.Application.instance().main_window()
        except Exception:
            main_window = None

    views = _open_views(main_window) if main_window is not None else []
    layouts = _open_layouts(main_window) if main_window is not None else []
    result = _reload_runtime(layouts)
    if main_window is not None:
        from JNU_MWP_tools.core.internal_waveguide_registry import (
            install_internal_waveguide_registration,
        )

        install_internal_waveguide_registration(main_window)
    if reload_menu and main_window is not None:
        try:
            _reload_menu_macro()
        except Exception as error:
            raise RuntimeError("重新注册 JNU 菜单阶段失败：%s" % error) from error
    for view in views:
        try:
            _property_or_call(view, "redraw")
        except Exception:
            pass
    return result


def _run_reload_with_feedback(main_window):
    """执行热重载，并把成功状态或失败阶段反馈给用户。"""

    try:
        result = reload_jnu_pdk(main_window=main_window, reload_menu=True)
        main_window.message(
            "JNU_MWP_PDK 已重新加载；刷新 %d 个内部波导声明。"
            % result["internal_refresh_count"],
            4000,
        )
    except Exception as error:
        pya.MessageBox.warning(
            "JNU_MWP_PDK",
            "Reload JNU PDK 失败：\n%s" % error,
            pya.MessageBox.Ok,
        )
    finally:
        _clear_pending_reload_timer()


def _clear_pending_reload_timer(timer=None):
    """清除模块级 timer 引用，不依赖 MainWindow 的动态 Python 属性。"""
    global _PENDING_RELOAD_TIMER
    if timer is None or _PENDING_RELOAD_TIMER is timer:
        _PENDING_RELOAD_TIMER = None


def _schedule_reload(main_window, timer_factory):
    """创建单次延时重载；已有活跃 timer 时合并重复触发。"""
    global _PENDING_RELOAD_TIMER
    existing = _PENDING_RELOAD_TIMER
    if existing is not None:
        try:
            if existing.isActive():
                return False
        except Exception:
            # 已被 Qt 删除的 timer 不能再复用，直接替换为新的单次 timer。
            _PENDING_RELOAD_TIMER = None

    timer = timer_factory(main_window)
    timer.setSingleShot(True)
    timer.timeout(lambda: _run_reload_with_feedback(main_window))
    _PENDING_RELOAD_TIMER = timer
    timer.start(0)
    return True


def schedule_reload_jnu_pdk():
    """在当前菜单回调返回后执行重载，避免销毁正在触发的 Action。"""

    app = pya.Application.instance()
    main_window = app.main_window() if app is not None else None
    if main_window is None:
        raise RuntimeError("当前没有可用的 KLayout 主窗口。")

    _schedule_reload(main_window, pya.QTimer)


__all__ = [
    "reload_jnu_pdk",
    "schedule_reload_jnu_pdk",
]
