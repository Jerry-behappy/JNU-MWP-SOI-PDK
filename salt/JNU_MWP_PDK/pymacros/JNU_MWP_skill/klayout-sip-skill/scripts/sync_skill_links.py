# -*- coding: utf-8 -*-
"""将 Codex/Claude 的 klayout-sip-skill 入口链接到规范源。"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


CANONICAL = Path(__file__).resolve().parents[1]
SKILL_NAME = "klayout-sip-skill"
TARGETS = (
    Path.home() / ".codex" / "skills" / SKILL_NAME,
    Path.home() / ".claude" / "skills" / SKILL_NAME,
)
REQUIRED = (
    Path("SKILL.md"),
    Path("agents/openai.yaml"),
    Path("references/layout-conventions.md"),
    Path("references/editing-workflows.md"),
    Path("references/selection-and-hierarchy.md"),
    Path("references/verification.md"),
    Path("scripts/inspect_layout.py"),
    Path("scripts/sync_skill_links.py"),
)


def is_link(path):
    """兼容判断符号链接和 Windows 目录联接。"""
    is_junction = getattr(os.path, "isjunction", lambda _path: False)
    return path.is_symlink() or is_junction(path)


def assert_safe_target(path):
    """只允许操作固定的 skill 入口。"""
    expected = {target.absolute() for target in TARGETS}
    if path.absolute() not in expected or path.name != SKILL_NAME:
        raise RuntimeError("拒绝操作非预期 skill 路径: %s" % path)


def remove_target(path):
    """删除入口；目录联接只删除联接本身。"""
    assert_safe_target(path)
    if is_link(path):
        os.rmdir(str(path))
    elif path.is_dir():
        shutil.rmtree(str(path))
    elif path.exists():
        path.unlink()


def create_junction(path):
    """创建无需管理员权限的 Windows 目录联接。"""
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
        raise RuntimeError(
            "创建目录联接失败: %s" % (completed.stderr or completed.stdout)
        )


def check_required():
    """检查规范源包含全部必要文件。"""
    return [relative for relative in REQUIRED if not (CANONICAL / relative).is_file()]


def sync():
    """同步 Codex/Claude 两个入口。"""
    missing = check_required()
    if missing:
        raise RuntimeError("canonical skill 缺少文件: %s" % missing)
    for target in TARGETS:
        if target.exists() or is_link(target):
            try:
                if is_link(target) and target.resolve() == CANONICAL.resolve():
                    print("OK:", target)
                    continue
            except OSError:
                pass
            remove_target(target)
        create_junction(target)
        print("LINK:", target, "->", CANONICAL)
    return check()


def check():
    """检查两个入口均指向 canonical skill。"""
    failures = []
    for relative in check_required():
        failures.append("canonical 缺少 %s" % relative)
    for target in TARGETS:
        if not is_link(target):
            failures.append("不是目录联接: %s" % target)
            continue
        try:
            if target.resolve() != CANONICAL.resolve():
                failures.append("联接目标错误: %s" % target)
        except OSError as error:
            failures.append("联接不可解析: %s (%s)" % (target, error))
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
