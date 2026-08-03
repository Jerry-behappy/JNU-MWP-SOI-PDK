# JNU 微波光子 PDK

> 英文名称：JNU Microwave Photonics PDK  
> 创建者：Junyi Zhang  
> 更新时间：2026 年 6 月

## 中文说明

### 项目简介

`JNU_MWP_PDK` 是面向硅基微波光子芯片版图设计与流片的 KLayout 光子器件设计包。安装后将注册以下技术与器件库：

- KLayout 技术：`JNU_MWP_PDK`
- 白盒器件库：`JNULib_v1.1`
- 黑盒器件库：`JNULib_BlackBox_v1.1`

器件库包含固定 GDS 单元、参数化单元（PCell）、波导转换工具、端口生成工具和版图检查脚本。光学端口采用 `PinRec` 路径与文本标记，可被兼容的光子版图工具识别。

### 安装

#### 推荐方式：安装为 Salt 包

将完整的 `JNU_MWP_PDK` 文件夹放入：

```text
%USERPROFILE%\KLayout\salt\
```

确认安装后的主目录为：

```text
%USERPROFILE%\KLayout\salt\JNU_MWP_PDK
```

随后重启 KLayout，并将当前版图的技术切换为 `JNU_MWP_PDK`。正常加载后，Library 面板中应出现 `JNULib_v1.1` 和 `JNULib_BlackBox_v1.1`，顶部菜单中应出现 `JNU_MWP_PDK`。

#### 仅安装技术文件

如果只需要图层名称、颜色和显示样式，可将 `JNU_MWP_PDK.lyt` 与 `layers.lyp` 复制到：

```text
%USERPROFILE%\KLayout\tech\JNU_MWP_PDK\
```

这种方式不会单独安装 PCell、器件库和菜单工具；完整功能仍建议使用 Salt 包安装方式。

### 目录结构

下列路径均相对于 `JNU_MWP_PDK` 主目录：

| 路径 | 作用 |
|---|---|
| `__init__.py` | 注册技术并加载 Python 宏 |
| `JNU_MWP_PDK.lyt` | 定义数据库单位、图层映射及版图读写选项 |
| `layers.lyp` | 定义图层名称、颜色、线型和默认可见性 |
| `pymacros/JNULib.py` | 加载固定 GDS 单元并注册白盒 PCell |
| `pymacros/JNULib_BlackBox.py` | 注册黑盒器件库 |
| `pymacros/JNU_MWP_gds/` | 存放 23 个固定版图单元 |
| `pymacros/JNU_MWP_pcells/` | 存放参数化器件实现 |
| `pymacros/JNU_MWP_tools/` | 存放波导转换、端口生成、图层处理及回归脚本 |
| `pymacros/JNU_MWP_PDK_Menu.lym` | 注册 KLayout 顶部菜单及工具入口 |
| `pymacros/JNU_MWP_blackbox/` | 存放黑盒器件资源 |
| `drc/` | 存放设计规则检查脚本 |
| `lvs/` | 存放版图与原理图一致性检查脚本 |
| `d25/` | 存放二维半版图可视化脚本 |
| `xsect/` | 存放截面定义与相关脚本 |
| `python_deps/` | 存放项目随附的 Python 依赖 |

### 器件库

#### 固定版图单元

`JNULib_v1.1` 从 `pymacros/JNU_MWP_gds/` 加载 23 个固定 GDS 单元，包括：

- 1310 nm 与 1550 nm 光栅耦合器
- MMI 耦合器与功率分束器
- 偏振分束器、偏振旋转器与偏振器
- 边缘耦合器、光开关和终端器件

#### 参数化单元

当前注册 9 个 PCell：

| PCell 名称 | 源文件 | 功能 |
|---|---|---|
| `Bend_90deg` | `bend_90deg.py` | 支持 Circular、Bezier 和 Euler 的 90° 波导弯曲 |
| `Microring_DoubleBus` | `microring_doublebus.py` | 双总线微环谐振器 |
| `Archimedean_Spiral` | `Archimedean_spiral.py` | 双臂阿基米德螺旋延迟线，支持三种端口布局和可配置输出转角 |
| `Paperclip_Spiral` | `paperclip_spiral.py` | 回形针螺旋延迟线，支持三种端口布局 |
| `Paperclip_Spiral_with_Composite_Waveguide` | `paperclip_spiral_composite.py` | 采用复合波导截面的回形针螺旋延迟线 |
| `Taper` | `taper.py` | 线性锥形波导 |
| `Waveguide` | `waveguide.py` | 根据 Manhattan 路径生成带端口和器件识别区域的波导 |
| `Composite_Waveguide` | `composite_waveguide.py` | 直段与弯曲采用不同宽度、并以直段内taper过渡的可逆波导 |
| `S_Bend_Waveguide` | `s_bend_waveguide.py` | S 形波导连接器 |

所有 JNU PCell 的设置面板均先显示可编辑参数，再在底部集中显示带 `[uneditable]` 标记的只读计算参数。

### 波导与图层约定

常用图层如下：

| 图层 | 用途 |
|---|---|
| `1/0` | 硅波导几何 |
| `1/10` | 光学端口路径与端口名称 |
| `68/0` | 器件识别区域 |
| `10/0` | 器件说明文本 |
| `1/99` | 输入引导路径及旧版波导恢复兼容层（默认隐藏） |

`Waveguide` 与 `Composite_Waveguide` PCell 的器件识别区域在硅波导两侧各扩展 `1 µm`。新生成波导的原始 Manhattan 路径保存在 PCell 的 `path` 参数和无图形恢复属性中，不再向 `1/99` 写入 Path。`1/99` 继续用于输入引导路径和读取旧版文件，默认隐藏且可在 Layer 面板中手动显示。

### 菜单工具

安装完成后，KLayout 顶部的 `JNU_MWP_PDK` 菜单提供以下工具：

| 菜单 | 工具 | 功能 |
|---|---|---|
| `Waveguides` | `Path to Waveguide` | 通过“单一宽度波导/复合宽度波导”页签生成对应的可逆 PCell |
| `Waveguides` | `Waveguide to Path` | 从 `Waveguide` PCell 恢复原始路径 |
| `Waveguides` | `SBend connect` | 在两个选定端口之间生成 S 弯连接；默认使用 Bezier、B=0.3、R=30 µm |
| `Layout` | `Make Pins for Cell` | 为当前单元生成光学端口 |
| `Layout` | `Layer Exclude` | 展平版图时排除指定图层 |
| `Layout` | `Numerical text array` | 按编号序列生成由 `Basic.Text` 实例组成的横向或纵向文本阵列 Cell，并进入鼠标跟随放置模式 |
| `DRC` | `JNU_MWP_DRC` | 启动 JNU 微波光子版图设计规则检查 |

复合宽度页默认直段宽度 `2.0 µm`、弯曲宽度 `0.5 µm`、taper长度 `20 µm`，弯曲默认为 Bezier、`B=0.3`、`R=30 µm`。当Path长度不足时，工具列出问题线段并询问是否继续；继续后按每条Path的最大统一可行半径生成，固定taper仍无法容纳的Path保持不变。

`Numerical text array` 可设置起始编号、结束编号、步长、排列方向、目标层、相邻文字 bbox 的中心距以及 `Basic.Text` 的 Magnification 参数。横向阵列沿 `+X` 排列，纵向阵列沿 `+Y` 排列且文字自身不旋转。

### 在 KLayout Python 中读取固定 GDS

```python
from pathlib import Path

import pya

# 创建版图对象。
layout = pya.Layout()

# 读取固定器件版图。
layout.read(
    str(
        Path.home()
        / "KLayout"
        / "salt"
        / "JNU_MWP_PDK"
        / "pymacros"
        / "JNU_MWP_gds"
        / "1550_1_2_MMI.gds"
    )
)

# 输出顶层单元名称。
print([cell.name for cell in layout.top_cells()])
```

### 使用提示

- 如果切换到 `JNU_MWP_PDK` 后仍只显示 `1/0` 等原始图层号，请确认 `JNU_MWP_PDK.lyt` 和 `layers.lyp` 均已加载，然后重启 KLayout。
- 如果 Library 面板中没有器件库，请检查 `pymacros` 目录是否完整，并查看 KLayout Macro Development 窗口或控制台中的加载信息。
- 白盒库和黑盒库名称带有版本号；脚本实例化器件时应使用 `JNULib_v1.1` 或 `JNULib_BlackBox_v1.1`。
- `1/99` 默认隐藏，仅承担输入引导和旧版文件读取兼容。新 Waveguide 的恢复数据位于 PCell 参数与无图形属性中，因此转换不会额外显示一条 Waveguide Path。
- 流片前应根据目标工艺重新核对图层映射、设计规则和器件适用波长。

---

## English Documentation

### Overview

`JNU_MWP_PDK` is a KLayout photonic design kit for the layout and tape-out of silicon microwave-photonic integrated circuits. The package registers:

- KLayout technology: `JNU_MWP_PDK`
- White-box library: `JNULib_v1.1`
- Black-box library: `JNULib_BlackBox_v1.1`

The package includes fixed GDS cells, parameterized cells (PCells), waveguide conversion tools, optical-pin utilities, and layout verification scripts. Optical ports are represented by `PinRec` paths and labels so that compatible photonic-layout tools can recognize them.

### Installation

#### Recommended: install as a Salt package

Place the complete `JNU_MWP_PDK` directory under:

```text
%USERPROFILE%\KLayout\salt\
```

The resulting package path should be:

```text
%USERPROFILE%\KLayout\salt\JNU_MWP_PDK
```

Restart KLayout and assign the `JNU_MWP_PDK` technology to the active layout. After a successful load, the Library panel should contain `JNULib_v1.1` and `JNULib_BlackBox_v1.1`, and the top menu bar should contain `JNU_MWP_PDK`.

#### Install only the technology files

If only the layer names, colors, and display styles are required, copy `JNU_MWP_PDK.lyt` and `layers.lyp` to:

```text
%USERPROFILE%\KLayout\tech\JNU_MWP_PDK\
```

This method alone does not install the PCells, device libraries, or menu tools. Use the Salt-package method for the complete feature set.

### Directory Structure

All paths below are relative to the `JNU_MWP_PDK` package root:

| Path | Purpose |
|---|---|
| `__init__.py` | Registers the technology and loads the Python macros |
| `JNU_MWP_PDK.lyt` | Defines the database unit, layer mapping, and layout I/O options |
| `layers.lyp` | Defines layer names, colors, line styles, and default visibility |
| `pymacros/JNULib.py` | Loads fixed GDS cells and registers the white-box PCells |
| `pymacros/JNULib_BlackBox.py` | Registers the black-box library |
| `pymacros/JNU_MWP_gds/` | Contains 23 fixed layout cells |
| `pymacros/JNU_MWP_pcells/` | Contains the PCell implementations |
| `pymacros/JNU_MWP_tools/` | Contains waveguide conversion, pin, layer-processing, and regression tools |
| `pymacros/JNU_MWP_PDK_Menu.lym` | Registers the KLayout menu and tool actions |
| `pymacros/JNU_MWP_blackbox/` | Contains black-box device resources |
| `drc/` | Contains design-rule checking scripts |
| `lvs/` | Contains layout-versus-schematic scripts |
| `d25/` | Contains 2.5D layout-visualization scripts |
| `xsect/` | Contains cross-section definitions and scripts |
| `python_deps/` | Contains the bundled Python dependencies |

### Device Libraries

#### Fixed layout cells

`JNULib_v1.1` loads 23 fixed GDS cells from `pymacros/JNU_MWP_gds/`, including:

- 1310 nm and 1550 nm grating couplers
- MMI couplers and power splitters
- Polarization beam splitters, rotators, and polarizers
- Edge couplers, optical switches, and terminators

#### Parameterized cells

Nine PCells are currently registered:

| PCell | Source | Function |
|---|---|---|
| `Bend_90deg` | `bend_90deg.py` | 90-degree waveguide bend with Circular, Bezier, and Euler options |
| `Microring_DoubleBus` | `microring_doublebus.py` | Double-bus microring resonator |
| `Archimedean_Spiral` | `Archimedean_spiral.py` | Dual-arm Archimedean delay line with three port layouts and configurable output bends |
| `Paperclip_Spiral` | `paperclip_spiral.py` | Paperclip spiral delay line with three port layouts |
| `Paperclip_Spiral_with_Composite_Waveguide` | `paperclip_spiral_composite.py` | Paperclip spiral delay line using a composite waveguide cross-section |
| `Taper` | `taper.py` | Linear waveguide taper |
| `Waveguide` | `waveguide.py` | Waveguide generated from a Manhattan path, including optical pins and a device-recognition region |
| `Composite_Waveguide` | `composite_waveguide.py` | Reversible waveguide with separate straight/bend widths and tapers placed on straight sections |
| `S_Bend_Waveguide` | `s_bend_waveguide.py` | S-bend waveguide connector |

Every JNU PCell dialog lists editable parameters first and groups read-only derived parameters marked `[uneditable]` at the bottom.

### Waveguide and Layer Conventions

Common layers are listed below:

| Layer | Purpose |
|---|---|
| `1/0` | Silicon waveguide geometry |
| `1/10` | Optical-pin paths and names |
| `68/0` | Device-recognition region |
| `10/0` | Device information text |
| `1/99` | Input guide paths and legacy waveguide-recovery compatibility; hidden by default |

The `Waveguide` and `Composite_Waveguide` PCells expand their device-recognition regions by `1 µm` on each side of the silicon waveguide. New waveguides retain the original Manhattan path in the PCell `path` parameter and non-geometric recovery properties, without writing a Path to layer `1/99`. Layer `1/99` remains available for input guides and legacy-file recovery; it is hidden by default but can be shown manually in the Layer panel.

### Menu Tools

After installation, the `JNU_MWP_PDK` menu in KLayout provides:

| Menu | Tool | Function |
|---|---|---|
| `Waveguides` | `Path to Waveguide` | Uses Single-width and Composite-width tabs to create the corresponding reversible PCell |
| `Waveguides` | `Waveguide to Path` | Restores the original paths from `Waveguide` PCells |
| `Waveguides` | `SBend connect` | Creates an S-bend connection between two selected ports; defaults to Bezier, B=0.3, and R=30 µm |
| `Layout` | `Make Pins for Cell` | Creates optical pins for the active cell |
| `Layout` | `Layer Exclude` | Excludes selected layers while flattening a layout |
| `Layout` | `Numerical text array` | Creates a horizontal or vertical cell of numbered `Basic.Text` instances and enters interactive mouse placement |
| `DRC` | `JNU_MWP_DRC` | Starts the JNU microwave-photonic design-rule check |

The Composite-width tab defaults to a `2.0 µm` straight width, `0.5 µm` bend width, `20 µm` taper, and a Bezier bend with `B=0.3` and `R=30 µm`. If a path is too short, the tool lists the affected segments and asks whether to continue. Continuing applies the largest uniform feasible radius to each path; paths that cannot accommodate the fixed taper remain unchanged.

`Numerical text array` accepts the start value, end value, step, arrangement direction, target layer, center-to-center bbox pitch, and the `Basic.Text` Magnification parameter. Horizontal arrays grow along `+X`; vertical arrays grow along `+Y` without rotating the individual text instances.

### Reading a Fixed GDS Cell with KLayout Python

```python
from pathlib import Path

import pya

# Create a layout object.
layout = pya.Layout()

# Read a fixed-device layout.
layout.read(
    str(
        Path.home()
        / "KLayout"
        / "salt"
        / "JNU_MWP_PDK"
        / "pymacros"
        / "JNU_MWP_gds"
        / "1550_1_2_MMI.gds"
    )
)

# Print the top-cell names.
print([cell.name for cell in layout.top_cells()])
```

### Notes

- If raw layer numbers such as `1/0` remain visible after assigning the `JNU_MWP_PDK` technology, verify that both `JNU_MWP_PDK.lyt` and `layers.lyp` are loaded, then restart KLayout.
- If the libraries do not appear in the Library panel, verify that the `pymacros` directory is complete and inspect the KLayout Macro Development window or console for load messages.
- The white-box and black-box library names include version suffixes. Use `JNULib_v1.1` or `JNULib_BlackBox_v1.1` when instantiating cells from scripts.
- Layer `1/99` is hidden by default and is retained for input guides and legacy-file recovery. New Waveguide recovery data is stored in PCell parameters and non-geometric properties, so conversion does not leave a visible Waveguide Path.
- Before tape-out, verify the layer mapping, design rules, and device wavelength against the target fabrication process.
