# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

"""验证目录联接安装、已有目录保护与真实 KLayout 冷启动。"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import traceback


def probe():
    import pya

    home = Path(os.environ["KLAYOUT_HOME"])
    assert not (home / "tech").exists()
    assert pya.Technology.has_technology("JNU_MWP_PDK")
    white = pya.Library.library_by_name("JNULib")
    black = pya.Library.library_by_name("JNULib_BlackBox")
    assert white and black
    expected = {"Bend_90deg", "Microring_DoubleBus", "Archimedean_Spiral",
                "Paperclip_Spiral", "Paperclip_Spiral_with_Composite_Waveguide",
                "Taper", "S_Bend", "Straight_Waveguide"}
    assert set(white.layout().pcell_names()) == expected
    assert not black.layout().pcell_names()
    source = home / "salt" / "JNU_MWP_PDK"
    files = sorted((source / "pymacros" / "JNU_MWP_blackbox_gds").glob("*.gds"))
    assert files
    for path in files:
        layout = pya.Layout()
        layout.read(str(path))
        assert all(black.layout().cell(cell.name) for cell in layout.top_cells())
    window = pya.Application.instance().main_window()
    assert len(getattr(window, "_jnu_menu_actions_by_id", {})) == 10
    layout = window.current_view().active_cellview().layout()
    assert {"Waveguide", "Composite_Waveguide"} <= set(layout.pcell_names())
    top = layout.create_cell("CLONE_SMOKE")
    for i, name in enumerate(sorted(expected)):
        cell = layout.create_cell(name, "JNULib", {})
        assert cell and not cell.bbox(layout.layer(1, 0)).empty(), name
        top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans(i * 1000000, 0)))
    path = home / "smoke.gds"
    layout.write(str(path))
    reloaded = pya.Layout()
    reloaded.read(str(path))
    assert not reloaded.cell("CLONE_SMOKE").bbox().empty()
    report = {"pcells": len(expected), "blackbox_files": len(files), "menu_actions": 10,
              "no_external_tech": True, "gds_roundtrip": True}
    (home / "probe.json").write_text(json.dumps(report), encoding="utf-8")
    print("CLONE_PROBE_OK", report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--klayout", type=Path, required=True)
    parser.add_argument("--temp-root", type=Path, help="临时测试目录的父目录，可指定非 C 盘验证跨盘安装")
    args = parser.parse_args()
    installer = args.repo.resolve() / "Install_Cloned_PDK.ps1"
    with tempfile.TemporaryDirectory(prefix="jnu-clone-check-", dir=args.temp_root) as directory:
        home = Path(directory) / "KLayout 用户目录 with spaces"
        env = os.environ.copy()
        env.update(KLAYOUT_HOME=str(home), KLAYOUT_PATH=str(home), JNU_CLONE_PROBE="1")
        env.pop("KLAYOUT_PYTHONPATH", None)
        command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(installer)]

        def run(command, success=True, environment=None):
            result = subprocess.run(command, env=environment or env, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=120)
            if success:
                print(result.stdout, result.stderr)
                assert result.returncode == 0, result.stderr
            else:
                assert result.returncode != 0, "没有阻止覆盖现有安装"
            return result.stdout

        preview = run(command + ["-WhatIf"])
        assert "CLONE_INSTALLED" not in preview
        assert not home.exists(), "预览不得创建目标目录"
        assert "CLONE_INSTALLED" in run(command)
        assert "ALREADY_LINKED" in run(command)
        target = home / "salt" / "JNU_MWP_PDK"
        assert target.resolve() == (args.repo / "salt" / "JNU_MWP_PDK").resolve()
        # 显式路径优先于环境变量；默认目录从用户配置文件路径推导，不固定盘符。
        explicit = Path(directory) / "explicit user home"
        assert "CLONE_INSTALLED" in run(command + ["-KLayoutHome", str(explicit)])
        assert (explicit / "salt" / "JNU_MWP_PDK").resolve() == target.resolve()
        profile = Path(directory) / "test-profile"
        default_env = env.copy()
        default_env.pop("KLAYOUT_HOME", None)
        default_env.pop("KLAYOUT_PATH", None)
        default_env["USERPROFILE"] = str(profile)
        assert "CLONE_INSTALLED" in run(command, environment=default_env)
        assert (profile / "KLayout" / "salt" / "JNU_MWP_PDK").resolve() == target.resolve()
        run(command + ["-KLayoutHome", str(args.klayout)], success=False)
        blocked = Path(directory) / "existing"
        old = blocked / "salt" / "JNU_MWP_PDK"
        old.mkdir(parents=True)
        sentinel = old / "user-data.txt"
        sentinel.write_text("preserve user data", encoding="utf-8")
        run(command + ["-KLayoutHome", str(blocked)], success=False)
        assert sentinel.read_text(encoding="utf-8") == "preserve user data"
        (home / "klayoutrc").write_text("<config><edit-mode>true</edit-mode></config>", encoding="utf-8")
        run([str(args.klayout), "-z", "-e", "-t", "-rr", str(Path(__file__).resolve())])
        assert (home / "probe.json").is_file(), "冷启动未完成，不能用退出码替代验收"
        print("CLONE_INSTALLATION_OK: preview, path precedence, spaced/unicode home, junction, existing data protection, GUI cold start")


if os.environ.get("JNU_CLONE_PROBE") == "1":
    import pya

    def finish():
        try:
            probe()
        except Exception:
            traceback.print_exc()
            pya.Application.instance().exit(1)
        else:
            pya.Application.instance().exit(0)

    pya.Application.instance().main_window().create_layout("JNU_MWP_PDK", 1)
    timer = pya.QTimer()
    timer.setSingleShot(True)
    timer.timeout(finish)
    timer.start(200)
elif __name__ == "__main__":
    main()
