# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""隔离冷启动验证菜单版本、技术改名、旧状态迁移和黑盒独立加载。"""

import argparse
import builtins
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import traceback

import pya


SOURCE = Path(__file__).resolve().parents[3]


def _probe():
    home = Path(os.environ["KLAYOUT_HOME"])
    package = home / "salt" / "JNU_MWP_PDK"
    if str(package / "pymacros") not in sys.path:
        sys.path.insert(0, str(package / "pymacros"))
    from JNU_MWP_tools.core.pdk_identity import (
        LEGACY_TECHNOLOGY_NAME, MENU_TITLE, TECHNOLOGY_NAME, load_jnu_technology,
    )
    from JNU_MWP_tools.core import ui_language

    app = pya.Application.instance()
    window = app.main_window()
    assert MENU_TITLE == "JNU_MWP_SOI_PDK V1.8"
    assert pya.Technology.has_technology(TECHNOLOGY_NAME)
    assert not pya.Technology.has_technology(LEGACY_TECHNOLOGY_NAME)
    assert app.get_config("initial-technology") == TECHNOLOGY_NAME
    technology = pya.Technology.technology_by_name(TECHNOLOGY_NAME)
    assert Path(technology.eff_layer_properties_file()).resolve() == (package / "layers.lyp").resolve()
    black = pya.Library.library_by_name("JNULib_BlackBox")
    assert black and len(list(black.layout().each_top_cell())) == 31
    assert TECHNOLOGY_NAME in black.description
    white = pya.Library.library_by_name("JNULib")
    black_only = os.environ["JNU_IDENTITY_MODE"] == "black"
    assert (white is None) == black_only
    if white:
        assert len(list(white.layout().pcell_names())) == 9
        assert TECHNOLOGY_NAME in white.description

    cellview = window.create_layout(TECHNOLOGY_NAME, 1)
    layout = cellview.layout()
    top = layout.create_cell("IDENTITY_TEST")
    cellview.cell = top
    if white:
        child = layout.create_cell("Pcell_Straight_Waveguide", "JNULib", {"length": 50.0, "width": 0.5})
    else:
        child = layout.create_cell("1550_crossing4", "JNULib_BlackBox")
    assert child and not child.bbox().empty()
    top.insert(pya.CellInstArray(child.cell_index(), pya.Trans()))
    area = pya.Region(top.begin_shapes_rec(layout.layer(1, 0))).area()
    assert area > 0

    # 模拟升级前已打开的旧技术版图，以及旧 JNU 桥接库；不替换原 EBeam 库。
    pya.Technology.create_technology(LEGACY_TECHNOLOGY_NAME)
    cellview.technology = LEGACY_TECHNOLOGY_NAME
    bridge = pya.Library()
    bridge.add_technology(LEGACY_TECHNOLOGY_NAME)
    bridge.add_technology("OtherTechnology")
    bridge.register("IdentityBridge")
    original = pya.Library()
    original.technology = "EBeam"
    original.register("IdentityOriginal")
    app.set_config("initial-technology", LEGACY_TECHNOLOGY_NAME)
    mru = "'C:\\\\demo\\\\JNU_MWP_PDK.gds'@'JNU_MWP_PDK' 'other.gds'@'EBeam'"
    app.set_config("mru", mru)
    load_jnu_technology(package)
    load_jnu_technology(package)
    assert not pya.Technology.has_technology(LEGACY_TECHNOLOGY_NAME)
    assert cellview.technology == TECHNOLOGY_NAME and layout.technology_name == TECHNOLOGY_NAME
    assert app.get_config("initial-technology") == TECHNOLOGY_NAME
    assert app.get_config("mru") == mru.replace("@'JNU_MWP_PDK'", "@'JNU_MWP_SOI_PDK'")
    assert set(bridge.technologies()) == {TECHNOLOGY_NAME, "OtherTechnology"}
    assert original.technology == "EBeam"
    assert pya.Region(top.begin_shapes_rec(layout.layer(1, 0))).area() == area

    # 改名后重跑菜单时仍按原 Action ID 恢复快捷键，中英文根标题均带版本。
    macro = pya.Macro(str(package / "pymacros" / "JNU_MWP_PDK_Menu.lym"))
    action_id = "jnu_action_snap_components"
    window._jnu_menu_actions_by_id[action_id].shortcut = "Ctrl+Alt+K"
    for language in ("en", "zh_CN"):
        setattr(builtins, ui_language._SESSION_KEY, language)
        macro.run()
        macro.run()
        assert window.menu().action("jnu_mwp_pdk_menu").title == MENU_TITLE
        assert len(window._jnu_menu_actions) == 14
        assert window._jnu_menu_actions_by_id[action_id].title == "吸附器件 / Snap components"
        assert not window.menu().is_menu("jnu_mwp_pdk_menu.language")
        assert window._jnu_menu_actions_by_id[action_id].shortcut == "Ctrl+Alt+K"
    path = home / "identity.gds"
    layout.write(str(path))
    reread = pya.Layout()
    reread.technology_name = TECHNOLOGY_NAME
    reread.read(str(path))
    assert pya.Region(reread.cell(top.name).begin_shapes_rec(reread.layer(1, 0))).area() == area
    if white:
        assert any(cell.is_pcell_variant() for cell in reread.each_cell())
    (home / "passed.txt").write_text("cold start, migration, libraries, menus, shortcuts, GDS", encoding="utf-8")
    print("PASS: %s cold start, technology migration, versioned bilingual menu, shortcuts and GDS" %
          os.environ["JNU_IDENTITY_MODE"], flush=True)


def _finish():
    try:
        _probe()
    except Exception:
        traceback.print_exc()
        pya.Application.instance().exit(1)
    else:
        pya.Application.instance().exit(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--klayout", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(SOURCE / "pymacros"))
    from JNU_MWP_tools.release.package_blackbox_pdk import _write_blackbox_pymacros_init

    with tempfile.TemporaryDirectory(prefix="jnu-identity-") as directory:
        for mode in ("white", "black"):
            home = Path(directory) / mode
            package = home / "salt" / "JNU_MWP_PDK"
            package.mkdir(parents=True)
            for filename in ("__init__.py", "grain.xml", "JNU_MWP_PDK.lyt", "layers.lyp"):
                shutil.copy2(SOURCE / filename, package / filename)
            macros = package / "pymacros"
            macros.mkdir()
            for filename in ("__init__.py", "JNULib_BlackBox.py", "JNU_MWP_PDK_Menu.lym",
                             "JNU_MWP_PDK_Startup.lym", "JNU_MWP_InternalWaveguideRegistry.lym"):
                shutil.copy2(SOURCE / "pymacros" / filename, macros / filename)
            ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")
            for name in ("JNU_MWP_blackbox", "JNU_MWP_blackbox_gds"):
                shutil.copytree(SOURCE / "pymacros" / name, macros / name, ignore=ignore)
            tools = macros / "JNU_MWP_tools"
            tools.mkdir()
            shutil.copy2(SOURCE / "pymacros/JNU_MWP_tools/__init__.py", tools / "__init__.py")
            for name in ("core", "actions"):
                shutil.copytree(SOURCE / "pymacros/JNU_MWP_tools" / name, tools / name, ignore=ignore)
            if mode == "white":
                shutil.copy2(SOURCE / "pymacros/JNULib.py", macros / "JNULib.py")
                shutil.copytree(SOURCE / "pymacros/JNU_MWP_pcells", macros / "JNU_MWP_pcells", ignore=ignore)
            else:
                _write_blackbox_pymacros_init(macros)
            (home / "klayoutrc").write_text(
                "<config><edit-mode>true</edit-mode><initial-technology>JNU_MWP_PDK</initial-technology></config>",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.update(KLAYOUT_HOME=str(home), KLAYOUT_PATH=str(home), JNU_IDENTITY_MODE=mode)
            env.pop("KLAYOUT_PYTHONPATH", None)
            result = subprocess.run(
                [str(args.klayout), "-z", "-e", "-rr", str(Path(__file__).resolve())],
                env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if result.returncode != 0 or not (home / "passed.txt").is_file():
                raise AssertionError("冷启动未完成：%s\n%s\n%s" % (mode, result.stdout, result.stderr))
            for line in result.stdout.splitlines():
                if line.startswith("PASS:"):
                    print(line)
            if result.stderr:
                print(result.stderr)


if hasattr(pya, "Application"):
    _timer = pya.QTimer()
    _timer.setSingleShot(True)
    _timer.timeout(_finish)
    _timer.start(200)
elif __name__ == "__main__":
    main()
