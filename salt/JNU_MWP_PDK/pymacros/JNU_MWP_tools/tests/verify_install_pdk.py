# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

"""在临时 Git 仓库与 KLayout GUI 中验证安装、更新、保护及后台任务。"""

from pathlib import Path
import importlib.util
import os
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

import pya


PYMACROS = Path(__file__).resolve().parents[2]
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
        (public / "update.txt").write_text("new version", encoding="utf-8")
        git(public, "add", ".")
        git(public, "commit", "-m", "Update fixture")
        installer.update_public(home)
        assert (checkout / "update.txt").read_text() == "new version"
        (checkout / "update.txt").write_text("user edit", encoding="utf-8")
        reject(lambda: installer.update_public(home), "本地修改")
        assert (checkout / "update.txt").read_text() == "user edit"
        # 仅恢复测试夹具，由测试自行创建，不触碰用户源码。
        (checkout / "update.txt").write_text("new version", encoding="utf-8")
        git(checkout, "switch", "-c", "work")
        reject(lambda: installer.update_public(home), "main 分支")
        git(checkout, "switch", "main")
        git(checkout, "config", "user.name", "Installer Test")
        git(checkout, "config", "user.email", "installer@example.invalid")
        git(checkout, "commit", "--allow-empty", "-m", "Unpublished change")
        reject(lambda: installer.update_public(home), "未发布提交")
        installer.install_private(home)
        assert (home / "jnu_private/JNU_MWP_gds/test.gds").is_file()
        installer.install_private(home)
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
    dialog = installer.show_installer(execute=False)
    dialog.show()
    dialog.start()
    deadline = time.monotonic() + 10
    while dialog.busy and time.monotonic() < deadline:
        app.process_events()
        time.sleep(0.02)
    assert not dialog.busy, "Background task or GUI timer did not finish"
    assert "fixture complete" in dialog.output.toPlainText()
    dialog.close()

    menu = pya.Macro(str(PYMACROS / "JNU_MWP_PDK_Menu.lym"))
    for _ in range(2):
        menu.run()
        actions = app.main_window()._jnu_menu_actions_by_id
        assert "jnu_action_update_pdk" in actions
        assert "jnu_action_install_private" in actions
        assert len(actions) == 12
    print("PASS: install/reinstall/update, dirty/branch/legacy guards, private library, GUI worker, menu reload")


if __name__ == "__main__":
    main()
