# -*- coding: utf-8 -*-
# 创建者: Junyi Zhang
# 时间: 2026-10

"""JNU 界面语言偏好及 PCell 显示文字。"""

import builtins
import json
import os
from pathlib import Path


LANGUAGE_EN = "en"
LANGUAGE_ZH = "zh_CN"
_SESSION_KEY = "_jnu_mwp_pdk_active_ui_language"
_PREFERENCE_FILE = "jnu_ui_language.json"


def _language_path():
    """语言文件放在当前 KLayout 用户目录，兼容自定义 KLayoutHome。"""
    try:
        import pya

        app = pya.Application.instance()
        location = app.application_data_path()
        if location:
            return Path(str(location)) / _PREFERENCE_FILE
    except Exception:
        pass
    return Path(os.environ.get("KLAYOUT_HOME") or Path.home() / "KLayout") / _PREFERENCE_FILE


def _saved_language():
    try:
        data = json.loads(_language_path().read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("language") == LANGUAGE_ZH:
            return LANGUAGE_ZH
    except (OSError, ValueError, TypeError):
        pass
    return LANGUAGE_EN


def active_language():
    """同一 KLayout 进程始终使用首次读取的语言，重载 PDK 也不提前切换。"""
    language = getattr(builtins, _SESSION_KEY, None)
    if language not in (LANGUAGE_EN, LANGUAGE_ZH):
        language = _saved_language()
        setattr(builtins, _SESSION_KEY, language)
    return language


def set_next_language(language):
    """只保存下次启动的语言，不修改当前进程使用的语言。"""
    if language not in (LANGUAGE_EN, LANGUAGE_ZH):
        raise ValueError("Unsupported JNU UI language: %s" % language)
    path = _language_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(
            json.dumps({"language": language}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


# 这里只改变界面说明文字；PCell 参数键、选择值和器件注册名保持英文。
PARAMETER_LABELS_ZH = {
    "Bend arc length": "弯曲弧长",
    "Actual incremental length": "实际增量长度",
    "Bend points per 90 deg": "每 90° 弯曲采样点数",
    "Bend radius": "弯曲半径",
    "Bend radius (calculated)": "弯曲半径（计算值）",
    "Bend type": "弯曲类型",
    "Bend width": "弯曲波导宽度",
    "Bend waveguide width": "弯曲波导宽度",
    "Bezier": "贝塞尔参数",
    "Bezier Rmax": "贝塞尔最大曲率半径",
    "Bezier Rmin": "贝塞尔最小曲率半径",
    "Bezier control": "贝塞尔控制参数",
    "Bezier max radius": "贝塞尔最大曲率半径",
    "Bezier min radius": "贝塞尔最小曲率半径",
    "Bezier parameter": "贝塞尔参数",
    "Bezier shape factor": "贝塞尔形状参数",
    "Bus waveguide length": "总线波导长度",
    "Calculated centerline length": "中心线计算长度",
    "Calculated full turns": "完整圈数（计算值）",
    "Center bend points per 90°": "中心弯曲每 90° 采样点数",
    "Center bend type": "中心弯曲类型",
    "Coupling gap": "耦合间隙",
    "Curve sample points": "曲线采样点数",
    "DevRec layer": "器件识别层",
    "Device length": "器件长度",
    "Drop bus position": "下方总线位置",
    "Effective ring points": "实际圆环采样点数",
    "Effective bend radius": "有效弯曲半径",
    "End waveguide width": "末端波导宽度",
    "Estimated centerline length": "中心线估计长度",
    "Euler Reff": "欧拉有效半径 Reff",
    "Euler Rmax": "欧拉最大半径 Rmax",
    "Euler Rmin": "欧拉最小半径 Rmin",
    "Euler effective radius": "欧拉有效半径",
    "Euler max radius (endpoint)": "欧拉最大半径（端点）",
    "Euler min radius (midpoint)": "欧拉最小半径（中点）",
    "Gap": "间隙",
    "Horizontal length": "水平长度",
    "Inner length": "内侧长度",
    "Incremental length": "增量长度",
    "Inner length (min 2× bend radius)": "内侧长度（至少为弯曲半径的 2 倍）",
    "Internal name suffix": "内部名称后缀",
    "Loops": "圈数",
    "Minimum / center bend radius": "最小／中心弯曲半径",
    "Maximum angle": "最大弯曲角度",
    "Number of loops": "圈数",
    "Offset height": "偏移高度",
    "Output port vertical": "输出端口竖直",
    "Path": "路径",
    "Pin layer": "端口层",
    "Pin recognition layer": "端口识别层",
    "Points per 90°": "每 90° 采样点数",
    "Points/90°": "每 90° 采样点数",
    "Port 1 straight extension length": "端口 1 直波导延伸长度",
    "Port 2 straight extension length": "端口 2 直波导延伸长度",
    "Ports on opposite sides": "端口位于两侧",
    "Ports type": "端口类型",
    "Ring center radius": "圆环中心半径",
    "Ring points (0=auto)": "圆环采样点数（0 为自动）",
    "Straight width": "直波导宽度",
    "Straight waveguide width": "直波导宽度",
    "Start waveguide width": "起始端波导宽度",
    "Taper length": "渐变段长度",
    "Target waveguide length": "目标波导长度",
    "Total length": "总长度",
    "Transition length": "过渡段长度",
    "Vertical stretch": "竖直拉伸量",
    "Waveguide gap": "波导间隙",
    "Waveguide layer": "波导层",
    "Waveguide length": "波导长度",
    "Waveguide width": "波导宽度",
    "Width at port 1": "端口 1 宽度",
    "Width at port 2": "端口 2 宽度",
    "delta_L": "增量长度 delta_L",
    "delta_length": "增量长度",
}

CHOICE_LABELS_ZH = {
    "Circular": "圆弧",
    "Bezier": "贝塞尔",
    "Euler": "欧拉",
    "Si - waveguide layer (1/0)": "硅波导层 (1/0)",
    "Waveguide - raw path (1/99)": "波导原始路径层 (1/99)",
    "PinRec - optical pin layer (1/10)": "光学端口层 (1/10)",
    "DevRec (68/0)": "器件识别层 (68/0)",
    "Right vertical": "右侧竖直",
    "Top horizontal": "上方水平",
    "type1 - ports on same side": "类型 1：端口位于同侧",
    "type1 - ports on same sides": "类型 1：端口位于同侧",
    "type2 - ports on opposite sides": "类型 2：端口位于异侧",
    "type3 - opposite sides, aligned y": "类型 3：端口异侧且等高",
}


def localize_pcell_declaration(declaration):
    """只改声明中的描述和选项标题，保留内部参数名及选项值。"""
    if active_language() != LANGUAGE_ZH:
        return declaration
    for parameter in declaration.get_parameters():
        description = str(parameter.description)
        suffix = " [uneditable]"
        is_readonly_label = description.endswith(suffix)
        base = description[:-len(suffix)] if is_readonly_label else description
        translated = PARAMETER_LABELS_ZH.get(base)
        if translated is not None:
            parameter.description = translated + (" [不可编辑]" if is_readonly_label else "")
        titles = parameter.choice_descriptions()
        values = parameter.choice_values()
        choices = list(zip(titles, values))
        if choices:
            parameter.clear_choices()
            for title, value in choices:
                parameter.add_choice(CHOICE_LABELS_ZH.get(str(title), str(title)), value)
    return declaration
