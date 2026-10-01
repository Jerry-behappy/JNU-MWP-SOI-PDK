# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""在临时 Git 仓库与 KLayout GUI 中验证安装、更新、保护及后台任务。"""

from pathlib import Path
import importlib.util
import builtins
import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

import pya


PYMACROS = Path(__file__).resolve().parents[2]
if str(PYMACROS) not in sys.path:
    sys.path.insert(0, str(PYMACROS))
SOURCE = PYMACROS / "JNU_MWP_tools/actions/install_pdk.py"
spec = importlib.util.spec_from_file_location("jnu_installer_test", SOURCE)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def git(directory, *arguments):
    result = subprocess.run([installer.find_git(), "-C", str(directory), *arguments],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def reject(function, fragment):
    try:
        function()
    except RuntimeError as error:
        assert fragment in str(error), str(error)
    else:
        raise AssertionError("Expected refusal: " + fragment)


def seed(path, private=False):
    path.mkdir()
    git(path, "init", "-b", "main")
    git(path, "config", "user.name", "Installer Test")
    git(path, "config", "user.email", "installer@example.invalid")
    relative = Path("JNU_MWP_gds/test.gds") if private else installer.PDK_RELATIVE / "JNU_MWP_PDK.lyt"
    target = path / relative
    target.parent.mkdir(parents=True)
    if private:
        layout = pya.Layout()
        layout.create_cell("TEST")
        layout.write(str(target))
    else:
        target.write_text("<technology><name>JNU_MWP_PDK</name></technology>", encoding="utf-8")
        public_gds = path / installer.PDK_RELATIVE / "pymacros/JNU_MWP_gds"
        public_gds.mkdir(parents=True)
        (public_gds / "NOTICE.md").write_text("public fixture", encoding="utf-8")
        for filename in installer.PUBLIC_EBEAM_GDS:
            (public_gds / filename).write_bytes(b"public fixture")
        (path / ".gitignore").write_text(
            "salt/JNU_MWP_PDK/pymacros/JNU_MWP_gds/*.gds\n"
            "salt/JNU_MWP_PDK/pymacros/JNU_MWP_gds/.jnu_private_gds_sync.json\n",
            encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-m", "Initial fixture")


def main():
    root = PYMACROS.parents[2]
    macro = root / "Install_JNU_PDK.lym"
    if macro.exists():
        assert ET.parse(macro).findtext("text") == SOURCE.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="jnu-install-") as temporary:
        directory = Path(temporary)
        public = directory / "public"
        private = directory / "private"
        seed(public)
        seed(private, True)
        installer.PUBLIC_URL = str(public)
        installer.PRIVATE_URL = str(private)
        home = directory / "用户目录 with space ' test"
        installer.install_public(home)
        checkout = home / "jnu_repositories/JNU-MWP-SOI-PDK"
        linked = home / "salt/JNU_MWP_PDK"
        assert linked.resolve() == checkout / installer.PDK_RELATIVE
        installer.install_public(home)
        assert installer.probe_main_update(home) is None
        (public / "update.txt").write_text("new version", encoding="utf-8")
        git(public, "add", ".")
        git(public, "commit", "-m", "Update fixture")
        revisions = installer.probe_main_update(home)
        assert revisions == (git(checkout, "rev-parse", "HEAD"), git(public, "rev-parse", "HEAD"))
        installer.update_public(home)
        assert installer.probe_main_update(home) is None
        assert (checkout / "update.txt").read_text() == "new version"
        missing_remote = directory / "missing-public"
        git(checkout, "remote", "set-url", "origin", str(missing_remote))
        installer.PUBLIC_URL = str(missing_remote)
        assert installer.probe_main_update(home) is None, "远端不可用时应静默跳过"
        git(checkout, "remote", "set-url", "origin", str(public))
        installer.PUBLIC_URL = str(public)
        (checkout / "update.txt").write_text("user edit", encoding="utf-8")
        reject(lambda: installer.update_public(home), "本地修改")
        assert (checkout / "update.txt").read_text() == "user edit"
        # 仅恢复测试夹具，由测试自行创建，不触碰用户源码。
        (checkout / "update.txt").write_text("new version", encoding="utf-8")
        git(checkout, "switch", "-c", "work")
        reject(lambda: installer.update_public(home), "main 分支")
        (public / "branch-update.txt").write_text("branch remains local", encoding="utf-8")
        git(public, "add", ".")
        git(public, "commit", "-m", "Remote update while developing")
        assert installer.probe_main_update(home) is None, "开发分支不应触发更新提示"
        git(checkout, "switch", "main")
        assert installer.probe_main_update(home) is not None
        installer.update_public(home)
        git(checkout, "config", "user.name", "Installer Test")
        git(checkout, "config", "user.email", "installer@example.invalid")
        git(checkout, "commit", "--allow-empty", "-m", "Unpublished change")
        reject(lambda: installer.update_public(home), "未发布提交")
        installer.install_private(home)
        assert (home / "jnu_private/JNU_MWP_gds/test.gds").is_file()
        synced = checkout / installer.PDK_RELATIVE / "pymacros/JNU_MWP_gds/test.gds"
        assert synced.is_file()
        assert synced.read_bytes() == (home / "jnu_private/JNU_MWP_gds/test.gds").read_bytes()
        installer.install_private(home)
        assert synced.is_file()
        replacement = private / "JNU_MWP_gds/new.gds"
        replacement.write_bytes((private / "JNU_MWP_gds/test.gds").read_bytes())
        (private / "JNU_MWP_gds/test.gds").unlink()
        git(private, "add", "-A")
        git(private, "commit", "-m", "Replace fixture GDS")
        installer.install_private(home)
        assert not synced.exists(), "已删除的受管 GDS 不应留在原白盒目录"
        synced_new = synced.with_name("new.gds")
        assert synced_new.is_file()
        synced_new.write_bytes(b"user edited")
        layout = pya.Layout()
        layout.create_cell("UPDATED")
        layout.write(str(replacement))
        git(private, "add", "-A")
        git(private, "commit", "-m", "Update fixture GDS")
        installer.install_private(home)
        assert synced_new.read_bytes() == b"user edited", "用户修改不得被同步覆盖"
        legacy = directory / "legacy"
        target = legacy / "salt/JNU_MWP_PDK"
        target.mkdir(parents=True)
        (target / "keep.txt").write_text("keep", encoding="utf-8")
        reject(lambda: installer.install_public(legacy), "旧版手动安装")
        assert (target / "keep.txt").read_text() == "keep"
        manual_private = legacy / "jnu_private"
        manual_private.mkdir()
        (manual_private / "keep.gds").write_text("keep", encoding="utf-8")
        reject(lambda: installer.install_private(legacy), "不是 Git 克隆")
        assert (manual_private / "keep.gds").read_text() == "keep"
        # 清理临时目录前只移除测试创建的联接，避免递归跨入其目标。
        if os.name == "nt":
            os.rmdir(linked)
        else:
            linked.unlink()

    app = pya.Application.instance()
    installer.install_public = lambda home, notify: (notify("fixture progress") or "fixture complete")
    dialog = installer.show_installer(execute=False, auto_start=True)
    dialog.show()
    assert dialog.busy, "一键更新应自动开始后台任务"
    deadline = time.monotonic() + 10
    while dialog.busy and time.monotonic() < deadline:
        app.process_events()
        time.sleep(0.02)
    assert not dialog.busy, "Background task or GUI timer did not finish"
    assert "fixture complete" in dialog.output.toPlainText()
    dialog.close()

    from JNU_MWP_tools.actions import startup_update
    deadline = time.monotonic() + 10
    while startup_update._ACTIVE_CHECK is not None and time.monotonic() < deadline:
        app.process_events()
        time.sleep(0.02)
    assert startup_update._ACTIVE_CHECK is None, "启动检查的后台线程未结束"
    if hasattr(builtins, startup_update._SESSION_KEY):
        delattr(builtins, startup_update._SESSION_KEY)
    prompted = []
    startup_update.probe_main_update = lambda _home: ("a" * 40, "b" * 40)
    startup_update._confirm_update = lambda _window, revisions: prompted.append(revisions)
    menu = pya.Macro(str(PYMACROS / "JNU_MWP_PDK_Menu.lym"))
    menu.run()
    assert not startup_update.schedule_startup_update_check(), "同一进程只应检查一次"
    deadline = time.monotonic() + 10
    while not prompted and time.monotonic() < deadline:
        app.process_events()
        time.sleep(0.02)
    assert prompted == [("a" * 40, "b" * 40)], "后台结果应转交 GUI 主线程"

    menu.run()
    assert prompted == [("a" * 40, "b" * 40)], "重载菜单不得重复提示"
    actions = app.main_window()._jnu_menu_actions_by_id
    assert "jnu_action_update_pdk" in actions
    assert "jnu_action_install_private" in actions
    assert len(actions) == 14
    print("PASS: install/update, startup branch/offline guards, one-click GUI worker, menu reload", flush=True)


if __name__ == "__main__":
    main()
