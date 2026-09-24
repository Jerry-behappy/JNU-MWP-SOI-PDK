# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

"""由共享安装器生成可独立分发的 KLayout 宏，避免维护两套安装逻辑。"""

from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "salt/JNU_MWP_PDK/pymacros/JNU_MWP_tools/actions/install_pdk.py"


def build():
    macro = ET.Element("klayout-macro")
    fields = {"description": "Install JNU PDK", "version": "1.0", "category": "pymacros",
              "prolog": "", "epilog": "", "doc": "", "autorun": "false",
              "autorun-early": "false", "shortcut": "", "show-in-menu": "false",
              "group-name": "", "menu-path": "", "interpreter": "python",
              "dsl-interpreter-name": "", "text": SOURCE.read_text(encoding="utf-8")}
    for name, value in fields.items():
        ET.SubElement(macro, name).text = value
    ET.indent(macro, space=" ")
    ET.ElementTree(macro).write(ROOT / "Install_JNU_PDK.lym", encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    build()
