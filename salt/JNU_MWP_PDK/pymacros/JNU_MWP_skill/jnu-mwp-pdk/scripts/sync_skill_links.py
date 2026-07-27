# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-06

"""把 Codex/Claude 的 JNU skill 入口联接到项目内唯一规范源。"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


CANONICAL = Path(__file__).resolve().parents[1]
TARGETS = (
    Path.home() / ".codex" / "skills" / "jnu-mwp-pdk",
    Path.home() / ".claude" / "skills" / "jnu-mwp-pdk",
)
REQUIRED = (
    Path("SKILL.md"),
    Path("agents/openai.yaml"),
    Path("references/project-map.md"),
    Path("references/workflows.md"),
    Path("scripts/sync_skill_links.py"),
)


def _is_link(path):
    """兼容判断符号链接和 Windows 目录联接。"""
    is_junction = getattr(os.path, "isjunction", lambda _path: False)
    return path.is_symlink() or is_junction(path)


def _assert_safe_target(path):
    """只允许操作两个固定的 jnu-mwp-pdk 入口。"""
    expected = {target.absolute() for target in TARGETS}
    if path.absolute() not in expected or path.name != "jnu-mwp-pdk":
        raise RuntimeError("拒绝操作非预期 skill 路径：%s" % path)


def _remove_target(path):
    """删除旧入口；目录联接只删除联接本身，不触碰 canonical 内容。"""
    _assert_safe_target(path)
    if _is_link(path):
        os.rmdir(str(path))
    elif path.is_dir():
        shutil.rmtree(str(path))
    elif path.exists():
        path.unlink()


def _create_junction(path):
    """使用 Windows mklink 创建无需管理员权限的目录联接。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(path), str(CANONICAL)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError("创建目录联接失败：%s" % (completed.stderr or completed.stdout))


def sync():
    """以项目源覆盖旧入口并创建目录联接。"""
    for relative in REQUIRED:
        if not (CANONICAL / relative).is_file():
            raise RuntimeError("canonical skill 缺少文件：%s" % relative)
    for target in TARGETS:
        if target.exists() or _is_link(target):
            try:
                if _is_link(target) and target.resolve() == CANONICAL.resolve():
                    print("OK:", target)
                    continue
            except OSError:
                pass
            _remove_target(target)
        _create_junction(target)
        print("LINK:", target, "->", CANONICAL)
    return check()


def check():
    """检查两个入口均为指向 canonical 的目录联接。"""
    failures = []
    for relative in REQUIRED:
        if not (CANONICAL / relative).is_file():
            failures.append("canonical 缺少 %s" % relative)
    for target in TARGETS:
        if not _is_link(target):
            failures.append("不是目录联接：%s" % target)
            continue
        try:
            if target.resolve() != CANONICAL.resolve():
                failures.append("联接目标错误：%s" % target)
        except OSError as error:
            failures.append("联接不可解析：%s (%s)" % (target, error))
    if failures:
        for failure in failures:
            print("ERROR:", failure, file=sys.stderr)
        return 1
    print("OK: Codex/Claude 均直接使用", CANONICAL)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("sync", "check"))
    args = parser.parse_args()
    return sync() if args.command == "sync" else check()


if __name__ == "__main__":
    raise SystemExit(main())
