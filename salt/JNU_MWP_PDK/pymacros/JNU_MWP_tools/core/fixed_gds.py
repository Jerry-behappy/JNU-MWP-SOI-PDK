# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""优先读取原有白盒目录，兼容独立授权器件目录。"""

import os
from pathlib import Path

from .public_ebeam_cells import PUBLIC_EBEAM_CELLS


def fixed_gds_directory(pymacros):
    """本地白盒优先；仅含公开器件时读取独立授权目录。"""
    import pya

    bundled = Path(pymacros) / "JNU_MWP_gds"
    public_names = {name for name, _ in PUBLIC_EBEAM_CELLS}
    if bundled.is_dir() and any(
            path.suffix.lower() == ".gds" and path.stem not in public_names
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
