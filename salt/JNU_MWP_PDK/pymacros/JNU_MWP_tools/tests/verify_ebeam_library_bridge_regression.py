# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-07

"""验证 JNU Technology 下可见的 EBeam Library 镜像。"""

from pathlib import Path
import importlib
import sys

import pya


PYMACROS_DIR = Path(__file__).resolve().parents[2]
EBEAM_ROOT = Path(r"C:\Users\zjy\KLayout\salt\siepic_ebeam_pdk\EBeam")
SIEPIC_PYTHON_DIR = Path(r"C:\Users\zjy\KLayout\salt\siepic_tools\python")

for module_path in (PYMACROS_DIR, SIEPIC_PYTHON_DIR):
    if str(module_path) not in sys.path:
        sys.path.insert(0, str(module_path))

from JNU_MWP_tools.core.ebeam_library_bridge import (
    EBEAM_LIBRARY_SPECS,
    EBEAM_TECHNOLOGY_NAME,
    JNU_TECHNOLOGY_NAME,
    register_ebeam_libraries_for_jnu,
)


def _assert(condition, message):
    if not condition:
        raise RuntimeError(message)


def _ensure_technology(name, path):
    technology = pya.Technology.technology_by_name(name)
    if technology is not None:
        return technology
    technology = pya.Technology().create_technology(name)
    technology.load(str(path))
    return technology


def main():
    _ensure_technology(JNU_TECHNOLOGY_NAME, PYMACROS_DIR.parent / "JNU_MWP_PDK.lyt")
    _ensure_technology(EBEAM_TECHNOLOGY_NAME, EBEAM_ROOT / "EBeam.lyt")

    # JNULib 的启动路径必须自动触发桥接，不能只依赖测试手工调用。
    sys.modules.pop("JNULib", None)
    importlib.import_module("JNULib")

    first = register_ebeam_libraries_for_jnu()
    _assert(first["available"], "已安装 EBeam PDK 时 bridge 不应跳过。")

    expected_names = tuple(spec[0] for spec in EBEAM_LIBRARY_SPECS)
    for library_name in expected_names:
        library = pya.Library.library_by_name(library_name, JNU_TECHNOLOGY_NAME)
        _assert(library is not None, "%s 未注册到 JNU Technology。" % library_name)
        _assert(
            str(library.technology) == JNU_TECHNOLOGY_NAME,
            "%s Technology 绑定错误：%s" % (library_name, library.technology),
        )
        _assert(
            any(True for _cell in library.layout().each_cell()),
            "%s 未加载任何 EBeam 固定器件或 PCell。" % library_name,
        )

    second = register_ebeam_libraries_for_jnu()
    _assert(not second["created"], "重复注册不应新建 EBeam Library。")
    _assert(second["existing"] == expected_names, "重复注册未完整识别已有 Library。")
    print("OK: EBeam libraries are visible under JNU_MWP_PDK without replacing EBeam.")


if __name__ == "__main__":
    main()
