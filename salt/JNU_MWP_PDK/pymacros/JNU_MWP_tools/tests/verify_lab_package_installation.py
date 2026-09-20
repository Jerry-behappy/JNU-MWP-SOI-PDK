# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

"""用真实 Salt 安装与两次独立 KLayout 启动验证完整实验室包。"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import traceback
import xml.etree.ElementTree as ET


def probe():
    import pya

    home = Path(os.environ["KLAYOUT_HOME"])
    package = home / "salt" / "JNU_MWP_PDK"
    assert not (home / "tech").exists(), "测试环境不应依赖外部 tech"
    assert not (package / "tech").exists(), "测试包不应依赖内部 tech"
    assert pya.Technology.has_technology("JNU_MWP_PDK"), "未自动注册技术"
    technology = pya.Technology.technology_by_name("JNU_MWP_PDK")
    assert Path(technology.eff_layer_properties_file()).resolve() == (package / "layers.lyp").resolve()
    assert not any("_v1." in name for name in pya.Library.library_names())
    white = pya.Library.library_by_name("JNULib")
    black = pya.Library.library_by_name("JNULib_BlackBox")
    assert white and black, "未自动注册器件库"
    expected_pcells = {
        "Bend_90deg", "Microring_DoubleBus", "Archimedean_Spiral",
        "Paperclip_Spiral", "Paperclip_Spiral_with_Composite_Waveguide",
        "Taper", "S_Bend", "Straight_Waveguide",
    }
    assert set(white.layout().pcell_names()) == expected_pcells
    assert not black.layout().pcell_names(), "黑盒库不应注册 PCell"
    is_public = os.environ.get("JNU_EXPECT_PUBLIC") == "1"
    private = home / "jnu_private" / "JNU_MWP_gds"
    directory = private if os.environ.get("JNU_EXPECT_PRIVATE") == "1" else package / "pymacros" / "JNU_MWP_gds"
    gdss = sorted(directory.glob("*.gds"))
    if is_public:
        assert not (package / "pymacros" / "JNU_MWP_gds").exists(), "公开包包含白盒 GDS"
        assert not (package / "pymacros" / "JNU_MWP_skill").exists()
        for relative in ("JNU_MWP_tools/release", "JNU_MWP_tools/tests"):
            assert not (package / "pymacros" / relative).exists()
        import JNULib
        if os.environ.get("JNU_EXPECT_PRIVATE") == "1":
            assert Path(JNULib.GDS_DIR).resolve() == private.resolve()
            assert gdss, "私有 GDS 未安装"
        else:
            assert not gdss and not white.layout().top_cells(), "公开安装意外加载白盒器件"
        blackboxes = sorted((package / "pymacros" / "JNU_MWP_blackbox_gds").glob("*.gds"))
        assert blackboxes, "公开黑盒数据缺失"
        for path in blackboxes:
            source = pya.Layout()
            source.read(str(path))
            for cell in source.top_cells():
                si = list(cell.shapes(source.layer(1, 0)).each())
                assert len(si) == 1 and si[0].is_box(), "黑盒泄露内部几何"
                assert black.layout().cell(cell.name), "黑盒器件未加载"
    else:
        assert gdss, "固定 GDS 缺失"
    for path in gdss:
        source = pya.Layout()
        source.read(str(path))
        for cell in source.top_cells():
            assert white.layout().cell(cell.name), "固定器件未加载：" + cell.name
            # 公开黑盒与授权 GDS 独立发布，不能假定两个版本的顶层名称一致。
            if not is_public:
                assert black.layout().cell(cell.name), "黑盒器件未加载：" + cell.name

    app = pya.Application.instance()
    window = app.main_window()
    if os.environ.get("JNU_EXPECT_SIEPIC") == "1":
        # 必须自然启动成功，不能在探针里导入或重载 SiEPIC 来掩盖早期加载错误。
        state = sys.modules.get("SiEPIC._globals")
        assert state and state.Python_Env == "KLayout_GUI", "SiEPIC 被错误缓存为非 GUI 环境"
        assert "SiEPIC.setup" in sys.modules, "SiEPIC 菜单初始化被跳过"
        menu = window.menu()
        for item in ("siepic_menu", "siepic_menu.waveguides", "siepic_menu.layout",
                     "siepic_menu.exlayout", "siepic_menu.verification"):
            assert menu.is_menu(item), "SiEPIC 菜单缺失：" + item
        for parent, child in (
            ("siepic_menu.verification", "macro_in_menu_SiEPIC_EBeam_DRC"),
            ("siepic_menu.exlayout", "macro_in_menu_MZI"),
        ):
            assert parent + "." + child in menu.items(parent), "EBeam 宏未归入 SiEPIC 子菜单：%s；当前项：%s" % (child, menu.items(parent))
            assert child not in menu.items(""), "EBeam 宏错误地出现在顶层"
        assert pya.Library.library_by_name("EBeam", "EBeam"), "EBeam 原库缺失"
        assert pya.Library.library_by_name("EBeam", "JNU_MWP_PDK"), "JNU 技术下的 EBeam 桥接缺失"
    actions = getattr(window, "_jnu_menu_actions_by_id", {})
    assert len(actions) == 10, "JNU 菜单未完整加载"
    expected_shortcuts = {
        "jnu_action_path_to_waveguide": "9",
        "jnu_action_waveguide_to_path": "8",
        "jnu_action_sbend_connect_between_two_cells": "6",
        "jnu_action_snap_components": "7",
    }
    for key, value in expected_shortcuts.items():
        assert str(actions[key].shortcut) == value, "默认快捷键错误：" + key
    assert (package / "drc" / "JNU_MWP_DRC.lydrc").is_file()

    # 不手动加载 JNU 代码，验证新视图经过正常事件循环后获得内部 PCell 声明。
    layout = window.current_view().active_cellview().layout()
    assert {"Waveguide", "Composite_Waveguide"} <= set(layout.pcell_names())
    top = layout.create_cell("LAB_SMOKE_TEST")
    for i, name in enumerate(sorted(expected_pcells)):
        cell = layout.create_cell(name, "JNULib", {})
        assert cell and not cell.bbox(layout.layer(1, 0)).empty(), "PCell 几何为空：" + name
        top.insert(pya.CellInstArray(cell.cell_index(), pya.Trans(i * 1000000, 0)))
    fixture = home / "lab_smoke.gds"
    layout.write(str(fixture))
    reloaded = pya.Layout()
    reloaded.read(str(fixture))
    assert not reloaded.cell("LAB_SMOKE_TEST").bbox().empty()
    result = {"technology": technology.name, "fixed_gds": len(gdss),
              "public_pcells": sorted(expected_pcells), "menus": len(actions),
              "no_external_tech": True, "gds_roundtrip": True}
    if os.environ.get("JNU_EXPECT_SIEPIC") == "1":
        result["siepic_coexistence"] = "GUI menus, nested EBeam macros and libraries OK"
    Path(os.environ["JNU_LAB_PROBE_REPORT"]).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("JNU_LAB_PROBE_OK")


def run_checked(command, env, cwd):
    result = subprocess.run(command, env=env, cwd=cwd, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=120)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if result.returncode:
        raise RuntimeError("命令失败：%s (exit=%s)" % (command[0], result.returncode))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True, help="含入口脚本的交付目录")
    parser.add_argument("--klayout", type=Path, required=True)
    parser.add_argument("--public", action="store_true")
    parser.add_argument("--index-url", help="验收已发布的真实 GitHub 索引")
    parser.add_argument("--private-gds-source", type=Path, help="测试授权白盒 GDS 独立安装")
    parser.add_argument("--peer-package", type=Path, action="append", default=[],
                        help="复制到隔离环境的已安装包；共存测试须同时提供 siepic_tools 和 siepic_ebeam_pdk")
    args = parser.parse_args()
    release = args.package.resolve()
    if not args.public:
        run_checked(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                     str(release / "Open_Lab_Package_Manager.ps1"), "-PrepareOnly"], os.environ.copy(), str(release))
    # 临时用户目录不读取开发机配置，测试后自动清理，不触碰已打开的版图。
    with tempfile.TemporaryDirectory(prefix="jnu-lab-install-") as directory:
        home = Path(directory)
        env = os.environ.copy()
        env["KLAYOUT_HOME"] = str(home)
        env["KLAYOUT_PATH"] = str(home)
        env.pop("KLAYOUT_PYTHONPATH", None)
        if args.public:
            grain = ET.parse(release / "JNU_MWP_PDK" / "grain.xml").getroot()
            grain.find("url").text = (release / "JNU_MWP_PDK").as_uri() + "/"
            index = ET.Element("salt-mine")
            index.append(grain)
            index_file = home / "repository.xml"
            ET.ElementTree(index).write(index_file, encoding="utf-8")
            env["KLAYOUT_SALT_MINE"] = args.index_url or index_file.as_uri()
            env["JNU_EXPECT_PUBLIC"] = "1"
        else:
            env["KLAYOUT_SALT_MINE"] = (release / "repository.local.xml").as_uri()
        env["PYTHONIOENCODING"] = "utf-8"
        for peer in args.peer_package:
            if not (peer / "grain.xml").is_file():
                raise ValueError("共存包缺少 grain.xml：%s" % peer)
            shutil.copytree(peer, home / "salt" / peer.name,
                            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "*.log"))
        if args.peer_package:
            env["JNU_EXPECT_SIEPIC"] = "1"
        print("INSTALL: isolated KLayout Salt package")
        run_checked([str(args.klayout), "-z", "-t", "-y", "JNU_MWP_PDK"], env, directory)
        assert (home / "salt" / "JNU_MWP_PDK" / "grain.xml").is_file(), "Salt 未实际安装包"
        # 避免 SiEPIC 的首次启用编辑模式提示框阻塞隐藏测试；不涉及真实用户配置。
        (home / "klayoutrc").write_text("<config><edit-mode>true</edit-mode></config>", encoding="utf-8")
        reports = []
        for attempt in range(2):
            report = home / ("probe-%d.json" % attempt)
            env["JNU_LAB_PROBE_REPORT"] = str(report)
            env["JNU_LAB_PROBE"] = "1"
            print("COLD START: %d" % (attempt + 1))
            run_checked([str(args.klayout), "-z", "-e", "-rr", str(Path(__file__).resolve())], env, directory)
            assert report.is_file(), "冷启动未完成验证，不能以进程退出代替成功"
            reports.append(json.loads(report.read_text(encoding="utf-8")))
        assert reports[0] == reports[1], "两次启动结果不一致"
        print(json.dumps(reports[0], indent=2))
        if args.public and args.private_gds_source:
            installer = home / "salt" / "JNU_MWP_PDK" / "Install_Private_GDS.ps1"
            command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                       str(installer), "-Source", str(args.private_gds_source), "-KLayoutHome", str(home)]
            run_checked(command, env, directory)
            private = home / "jnu_private" / "JNU_MWP_gds"
            before = {path.name: path.read_bytes() for path in private.glob("*.gds")}
            assert before
            run_checked(command, env, directory)
            assert list(private.parent.glob("JNU_MWP_gds.backup-*")), "更新前没有保留备份"
            # 无效输入必须在替换前失败，已安装 GDS 内容不变。
            invalid = home / "invalid"
            invalid.mkdir()
            (invalid / "invalid.gds").write_bytes(b"not a GDS")
            rejected = subprocess.run(command[:-4] + ["-Source", str(invalid), "-KLayoutHome", str(home)],
                                      env=env, capture_output=True, timeout=30)
            assert rejected.returncode != 0
            assert before == {path.name: path.read_bytes() for path in private.glob("*.gds")}
            # Package 安装器再次运行不应修改独立私有数据目录。
            run_checked([str(args.klayout), "-z", "-t", "-y", "JNU_MWP_PDK"], env, directory)
            assert before == {path.name: path.read_bytes() for path in private.glob("*.gds")}
            env["JNU_EXPECT_PRIVATE"] = "1"
            report = home / "private-probe.json"
            env["JNU_LAB_PROBE_REPORT"] = str(report)
            run_checked([str(args.klayout), "-z", "-e", "-rr", str(Path(__file__).resolve())], env, directory)
            assert report.is_file() and json.loads(report.read_text())["fixed_gds"] == len(before)
            print("PRIVATE_GDS_OK: install, backup, invalid input rollback, independent data and cold start")
        print("LAB_PACKAGE_INSTALLATION_OK: install + 2 cold starts")


if os.environ.get("JNU_LAB_PROBE") == "1":
    import pya

    def _finish_probe():
        try:
            probe()
        except Exception:
            traceback.print_exc()
            pya.Application.instance().exit(1)
        else:
            pya.Application.instance().exit(0)

    # 等启动结束、宏菜单完成挂载后再检查，而非只看初始菜单框架。
    _technology = "EBeam" if os.environ.get("JNU_EXPECT_SIEPIC") == "1" else "JNU_MWP_PDK"
    pya.Application.instance().main_window().create_layout(_technology, 1)
    _probe_timer = pya.QTimer()
    _probe_timer.setSingleShot(True)
    _probe_timer.timeout(_finish_probe)
    _probe_timer.start(200)
elif __name__ == "__main__":
    main()
