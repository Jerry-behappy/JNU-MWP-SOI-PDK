# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""优先读取已同步的白盒目录，兼容独立授权器件目录。"""

import os
from pathlib import Path

def fixed_gds_directory(pymacros):
    """优先读取安装器同步的白盒；公开安装不要求固定 GDS。"""
    import pya

    bundled = Path(pymacros) / "JNU_MWP_gds"
    if bundled.is_dir() and any(
            path.suffix.lower() == ".gds"
            for path in bundled.iterdir()):
        return str(bundled)

    app = pya.Application.instance() if hasattr(pya, "Application") else None
    home = (Path(app.application_data_path()) if app else
            Path(os.environ.get("KLAYOUT_HOME") or
                 (Path.home() / ("KLayout" if os.name == "nt" else ".klayout"))))
    private = home / "jnu_private" / "JNU_MWP_gds"
    if private.is_dir() and any(p.suffix.lower() == ".gds" for p in private.iterdir()):
        return str(private)
    return str(bundled)
