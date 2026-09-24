# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

"""拖入安装宏与菜单共用的 Git 安装器；后台任务不接触 KLayout 对象。"""

import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading


PUBLIC_URL = "https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK.git"
PRIVATE_URL = "https://github.com/Jerry-behappy/JNU-MWP-SOI-Library.git"
PDK_RELATIVE = Path("salt/JNU_MWP_PDK")


def find_git():
    candidates = [shutil.which("git")]
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(variable)
        if base:
            candidates.extend(str(Path(base) / suffix) for suffix in (
                "Git/cmd/git.exe", "Programs/Git/cmd/git.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise RuntimeError("未找到 Git。请点击 Install Git，安装后重新打开 KLayout。")


def _run(arguments, cwd=None):
    environment = os.environ.copy()
    # 凭据交给用户的 Git Credential Manager；禁止等待隐藏终端输入密码。
    environment["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(
        [str(arg) for arg in arguments], cwd=cwd, env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace", timeout=600,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        # Git 的原始错误可能包含凭据 URL，不把原文展示或写入日志。
        raise RuntimeError(
            "命令执行失败（退出码 %d）。请检查网络、目录权限和 GitHub 授权。"
            "私有器件库需要实验室授权；已有文件已保留。" % result.returncode)
    return result.stdout.strip()


def _git(git, directory, *arguments):
    return _run([git, "-C", directory, *arguments])


def _repo_identity(url):
    return url.strip().removesuffix(".git").replace(
        "git@github.com:", "https://github.com/").rstrip("/")


def check_checkout(git, directory, url):
    directory = Path(directory)
    if not (directory / ".git").exists():
        raise RuntimeError("已有目录不是 Git 克隆，保留原内容：%s" % directory)
    if _repo_identity(_git(git, directory, "remote", "get-url", "origin")) != _repo_identity(url):
        raise RuntimeError("已有目录的 origin 不属于目标仓库：%s" % directory)
    if _git(git, directory, "branch", "--show-current") != "main":
        raise RuntimeError("当前克隆不在 main 分支，请先处理工作分支：%s" % directory)
    if _git(git, directory, "status", "--porcelain"):
        raise RuntimeError("检测到本地修改或未跟踪文件，请先保存并处理：%s" % directory)


def checkout(git, directory, url, notify):
    """仅克隆新目录，或把干净 main 快进至远端；失败保留所有数据。"""
    directory = Path(directory)
    if directory.exists():
        check_checkout(git, directory, url)
        notify("检查远端更新……")
        _git(git, directory, "fetch", "origin", "main")
        local = _git(git, directory, "rev-parse", "HEAD")
        remote = _git(git, directory, "rev-parse", "refs/remotes/origin/main")
        base = _git(git, directory, "merge-base", "HEAD", "refs/remotes/origin/main")
        if base != local:
            raise RuntimeError("本地 main 有未发布提交或已分歧，请人工处理：%s" % directory)
        if local == remote:
            notify("已是最新版本。")
        else:
            notify("正在更新……")
            _git(git, directory, "merge", "--ff-only", "refs/remotes/origin/main")
    else:
        directory.parent.mkdir(parents=True, exist_ok=True)
        notify("正在克隆仓库，请稍候……")
        _run([git, "clone", "--branch", "main", "--single-branch", url, directory])
        check_checkout(git, directory, url)
    return directory


def _existing_public_checkout(home):
    target = Path(home) / "salt" / "JNU_MWP_PDK"
    if not os.path.lexists(target):
        return None
    resolved = target.resolve()
    repository = resolved.parent.parent
    if (repository / ".git").exists() and resolved == repository / PDK_RELATIVE:
        return repository
    raise RuntimeError(
        "检测到旧版手动安装，已保留：%s\n"
        "请关闭 KLayout，将此目录及旧 tech/JNU_MWP_PDK 备份到配置目录外，"
        "保留白盒 GDS，再重新运行安装宏。" % target)


def _check_legacy(home):
    for relative in ("tech/JNU_MWP_PDK", "pymacros/JNU_MWP_PDK_loader.py",
                     "pymacros/JNU_MWP_PDK_blackbox_loader.py"):
        if os.path.lexists(Path(home) / relative):
            raise RuntimeError("检测到旧技术文件或 loader，请先关闭 KLayout 并移至配置目录外备份：%s"
                               % (Path(home) / relative))


def _link_directory(source, target):
    source, target = Path(source).resolve(), Path(target)
    if os.path.lexists(target):
        if target.resolve() == source:
            return
        raise RuntimeError("安装目标已存在，原文件保留：%s" % target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        # 使用环境变量传路径，避免空格、中文或引号被 PowerShell 解释为代码。
        environment = os.environ.copy()
        environment["JNU_LINK_SOURCE"] = str(source)
        environment["JNU_LINK_TARGET"] = str(target)
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             "$ErrorActionPreference='Stop'; New-Item -ItemType Junction "
             "-Path $env:JNU_LINK_TARGET -Target $env:JNU_LINK_SOURCE | Out-Null"],
            env=environment, capture_output=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode:
            raise RuntimeError("无法创建目录联接，请检查目标目录权限：%s" % target)
    else:
        target.symlink_to(source, target_is_directory=True)
    if target.resolve() != source:
        raise RuntimeError("目录联接核验失败：%s" % target)


def install_public(home, notify=lambda _message: None):
    home = Path(home).resolve()
    _check_legacy(home)
    repository = _existing_public_checkout(home)
    if repository is None:
        repository = home / "jnu_repositories" / "JNU-MWP-SOI-PDK"
    repository = checkout(find_git(), repository, PUBLIC_URL, notify)
    source = repository / PDK_RELATIVE
    if not (source / "JNU_MWP_PDK.lyt").is_file():
        raise RuntimeError("克隆中缺少 JNU_MWP_PDK.lyt，未建立安装联接。")
    _link_directory(source, home / "salt" / "JNU_MWP_PDK")
    return "安装/更新完成。请保存版图并重启 KLayout。\n源码：%s" % repository


def update_public(home, notify=lambda _message: None):
    if _existing_public_checkout(home) is None:
        raise RuntimeError("尚未安装 Git 克隆版 PDK，请先运行 Install_JNU_PDK.lym。")
    return install_public(home, notify)


def install_private(home, notify=lambda _message: None):
    # 私有仓库放在独立目录，完全沿用 fixed_gds.py 的读取路径。
    repository = checkout(find_git(), Path(home) / "jnu_private", PRIVATE_URL, notify)
    if not list((repository / "JNU_MWP_gds").glob("*.gds")):
        raise RuntimeError("私有仓库内没有找到 JNU_MWP_gds/*.gds。")
    return "白盒器件库安装/更新完成，请重启 KLayout。"


def show_installer(mode="install", execute=True):
    import pya

    app = pya.Application.instance()
    home = str(app.application_data_path())
    task = {"install": install_public, "update": update_public, "private": install_private}[mode]

    class InstallerDialog(pya.QDialog):
        def __init__(self):
            super().__init__(app.main_window())
            self.busy = False
            self.events = queue.Queue()
            self.setWindowTitle("JNU PDK Installer")
            self.resize(640, 330)
            layout = pya.QVBoxLayout(self)
            title = {"install": "安装 JNU PDK", "update": "检查并更新 JNU PDK",
                     "private": "安装/更新授权白盒器件库"}[mode]
            label = pya.QLabel(title, self)
            layout.addWidget(label)
            location = pya.QLineEdit(home, self)
            location.setReadOnly(True)
            layout.addWidget(location)
            self.output = pya.QPlainTextEdit(self)
            self.output.setReadOnly(True)
            if mode == "private":
                self.output.setPlainText("需要实验室授予私有仓库访问权。认证由 Git/Git Credential Manager 完成。")
            layout.addWidget(self.output)
            row = pya.QHBoxLayout()
            self.start_button = pya.QPushButton("安装" if mode == "install" else "检查并更新", self)
            self.close_button = pya.QPushButton("关闭", self)
            git_button = pya.QPushButton("Install Git", self)
            git_button.clicked(lambda _checked=False: pya.QDesktopServices.openUrl(pya.QUrl("https://git-scm.com/downloads")))
            self.start_button.clicked(lambda _checked=False: self.start())
            self.close_button.clicked(lambda _checked=False: self.reject())
            for button in (git_button, self.start_button, self.close_button):
                row.addWidget(button)
            layout.addLayout(row)
            self.timer = pya.QTimer(self)
            self.timer.setInterval(100)
            self.timer.timeout(self.poll)

        def reject(self):
            if not self.busy:
                super().reject()

        def closeEvent(self, event):
            if self.busy:
                event.ignore()
            else:
                super().closeEvent(event)

        def start(self):
            if self.busy:
                return
            self.busy = True
            self.start_button.setEnabled(False)
            self.close_button.setEnabled(False)
            self.output.setPlainText("正在检查安装环境……")

            def worker():
                try:
                    result = task(home, lambda message: self.events.put(("progress", message)))
                    self.events.put(("done", result))
                except Exception as error:
                    self.events.put(("error", str(error)))

            self.worker = threading.Thread(target=worker, daemon=True)
            self.worker.start()
            self.timer.start()

        def poll(self):
            while not self.events.empty():
                kind, message = self.events.get_nowait()
                self.output.appendPlainText(message)
                if kind != "progress":
                    self.timer.stop()
                    self.busy = False
                    self.close_button.setEnabled(True)
                    self.start_button.setEnabled(kind == "error")

    dialog = InstallerDialog()
    if execute:
        dialog.exec_()
    return dialog


if __name__ == "__main__":
    show_installer()
