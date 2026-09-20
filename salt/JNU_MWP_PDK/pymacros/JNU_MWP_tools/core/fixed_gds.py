# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-09

"""读取独立授权器件目录，并兼容开发目录及离线实验室包。"""

import os
from pathlib import Path


def fixed_gds_directory(pymacros):
    """授权数据优先；兼容本机开发目录和完整离线实验室包。"""
    import pya

    app = pya.Application.instance() if hasattr(pya, "Application") else None
    home = (Path(app.application_data_path()) if app else
            Path(os.environ.get("KLAYOUT_HOME") or
                 (Path.home() / ("KLayout" if os.name == "nt" else ".klayout"))))
    private = home / "jnu_private" / "JNU_MWP_gds"
    if private.is_dir() and any(p.suffix.lower() == ".gds" for p in private.iterdir()):
        return str(private)
    return str(Path(pymacros) / "JNU_MWP_gds")
