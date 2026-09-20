# JNU-MWP-SOI-PDK

## 中文说明

`JNU-MWP-SOI-PDK` 是暨南大学微波光子方向使用的 KLayout 光子 PDK 工程。当前仓库以开发源码形式发布，包含 `JNU_MWP_PDK` technology、KLayout 菜单、DRC、PCell、工具脚本和图层配置。

### 仓库内容

- `salt/JNU_MWP_PDK/`：KLayout salt 包主体，包含菜单、PCell、工具、DRC 和图层配置。
- `tech/JNU_MWP_PDK/`：KLayout technology 注册目录，用于让 KLayout 识别 `JNU_MWP_PDK` 技术。
- `salt/JNU_MWP_PDK/JNU_MWP_PDK.lyt`：salt 包内的 technology 配置。
- `tech/JNU_MWP_PDK/JNU_MWP_PDK.lyt`：用户 technology 目录中的 technology 配置。
- `salt/JNU_MWP_PDK/layers.lyp`：JNU PDK 图层显示配置。
- `salt/JNU_MWP_PDK/drc/JNU_MWP_DRC.lydrc`：JNU DRC 规则入口。
- `salt/JNU_MWP_PDK/pymacros/JNU_MWP_pcells/`：JNU PCell 源码。
- `salt/JNU_MWP_PDK/pymacros/JNU_MWP_blackbox_gds/`：随仓库提供的 25 个固定黑盒器件 GDS。
- `salt/JNU_MWP_PDK/pymacros/JNU_MWP_tools/`：JNU 菜单功能和公共工具源码。
- `salt/JNU_MWP_PDK/pymacros/JNU_MWP_skill/`：项目内部维护用 skill，不用于黑盒发布包。

### 手动安装方式

将当前仓库内容复制到：

```text
C:\Users\<用户名>\KLayout
```

复制完成后，应满足以下目录结构：

```text
C:\Users\<用户名>\KLayout\salt\JNU_MWP_PDK
C:\Users\<用户名>\KLayout\tech\JNU_MWP_PDK
```

请复制仓库内的 `salt/` 与 `tech/` 内容，不要把最外层 `JNU-MWP-SOI-PDK` 文件夹再嵌套为 `KLayout\JNU-MWP-SOI-PDK\`。KLayout 只会扫描 `KLayout\salt`、`KLayout\tech` 与 `KLayout\pymacros`。两份 `JNU_MWP_PDK.lyt` 均使用相对路径，不依赖作者电脑的 `C:\Users\zjy\...` 目录。

然后重启 KLayout，或在 Macro Development 中重新加载宏。正常加载后，KLayout 中应能看到：

- Technology：`JNU_MWP_PDK`
- 顶部功能菜单：`JNU_MWP_PDK`
- 器件库：`JNULib`、`JNULib_BlackBox`

`JNULib` 提供 8 类可编辑 PCell；`JNULib_BlackBox` 自动加载仓库自带的 25 个固定黑盒器件，无需另行取得白盒 GDS。选择 `Instance → JNULib_BlackBox` 即可放置器件。黑盒覆盖 1310/1550 nm 的光栅耦合器、端面耦合器、MMI、分光器、偏振分束器、偏振旋转器、偏振器、光开关和终端器件。

黑盒只保留器件占位矩形、PinRec 端口、DevRec 边界和名称标签，不包含内部物理结构。这些占位图形用于布局与连接，不能直接作为最终流片的器件结构。

### 重要说明

本项目基于 Lukas Chrostowski 及贡献者的原始项目开发。原始 MIT 许可证及版权声明已被保留，详见根目录的 `LICENSE.md`。

本仓库没有上传固定白盒器件 GDS 目录：

```text
salt/JNU_MWP_PDK/pymacros/JNU_MWP_gds/
```

该白盒目录已在 `.gitignore` 中排除。仓库中的黑盒 GDS 可独立加载，PCell 源码继续保留。维护者可运行 `salt/JNU_MWP_PDK/pymacros/JNU_MWP_tools/release/export_blackbox_gds.py --source <本地白盒目录> --output <新的黑盒目录>` 更新黑盒数据。若只需分发黑盒器件而不携带 PCell 源码，请使用独立黑盒打包流程。

运行过程中生成的 `klayoutrc*`、`__pycache__`、`.pyc`、`.pyo`、日志文件等不会纳入版本控制。

---

## English Description

`JNU-MWP-SOI-PDK` is a KLayout photonic PDK project for Jinan University microwave photonics work. This repository is published as a source/development package and contains the `JNU_MWP_PDK` technology, KLayout menu integration, DRC, PCells, utility scripts, and layer configuration.

### Repository Contents

- `salt/JNU_MWP_PDK/`: main KLayout salt package, including menus, PCells, tools, DRC, and layer configuration.
- `tech/JNU_MWP_PDK/`: KLayout technology registration directory for the `JNU_MWP_PDK` technology.
- `salt/JNU_MWP_PDK/JNU_MWP_PDK.lyt`: technology configuration inside the salt package.
- `tech/JNU_MWP_PDK/JNU_MWP_PDK.lyt`: technology configuration under the user technology directory.
- `salt/JNU_MWP_PDK/layers.lyp`: JNU PDK layer display configuration.
- `salt/JNU_MWP_PDK/drc/JNU_MWP_DRC.lydrc`: JNU DRC entry script.
- `salt/JNU_MWP_PDK/pymacros/JNU_MWP_pcells/`: JNU PCell source code.
- `salt/JNU_MWP_PDK/pymacros/JNU_MWP_blackbox_gds/`: 25 bundled fixed blackbox device GDS files.
- `salt/JNU_MWP_PDK/pymacros/JNU_MWP_tools/`: JNU menu actions and shared utility code.
- `salt/JNU_MWP_PDK/pymacros/JNU_MWP_skill/`: internal project skill used for maintenance, not included in blackbox release packages.

### Manual Installation

Copy the contents of this repository to:

```text
C:\Users\<username>\KLayout
```

After copying, the directory structure should include:

```text
C:\Users\<username>\KLayout\salt\JNU_MWP_PDK
C:\Users\<username>\KLayout\tech\JNU_MWP_PDK
```

Copy the repository's `salt/` and `tech/` contents; do not nest the outer `JNU-MWP-SOI-PDK` folder as `KLayout\JNU-MWP-SOI-PDK\`. KLayout scans `KLayout\salt`, `KLayout\tech`, and `KLayout\pymacros`. Both `JNU_MWP_PDK.lyt` files use relative paths and do not depend on the author's `C:\Users\zjy\...` directory.

Then restart KLayout, or reload macros from Macro Development. After successful loading, KLayout should show:

- Technology: `JNU_MWP_PDK`
- Top-level menu: `JNU_MWP_PDK`
- Libraries: `JNULib`, `JNULib_BlackBox`

`JNULib` provides eight editable PCell types. `JNULib_BlackBox` automatically loads 25 bundled fixed blackbox devices without requiring whitebox GDS. Use `Instance → JNULib_BlackBox` to place them. The devices cover 1310/1550 nm grating and edge couplers, MMIs, splitters, polarization beam splitters, a polarization rotator, polarizers, optical switches, and a terminator.

Blackboxes retain only a rectangular footprint, PinRec ports, DevRec bounds, and a name label. They omit internal physical geometry and are layout/connectivity placeholders, not final fabrication geometry.

### Notes

This project is based on the original project by Lukas Chrostowski and contributors. The original MIT license and copyright notices have been retained. See `LICENSE.md` in the repository root.

The fixed whitebox GDS directory is intentionally not committed:

```text
salt/JNU_MWP_PDK/pymacros/JNU_MWP_gds/
```

The whitebox directory is excluded by `.gitignore`. Bundled blackbox GDS loads independently, and PCell source code remains included. Maintainers can run `salt/JNU_MWP_PDK/pymacros/JNU_MWP_tools/release/export_blackbox_gds.py --source <local-whitebox-directory> --output <new-blackbox-directory>` to refresh the blackbox data. To distribute blackboxes without PCell source code, use the separate blackbox packaging workflow.

Generated files such as `klayoutrc*`, `__pycache__`, `.pyc`, `.pyo`, and log files are not tracked by version control.
