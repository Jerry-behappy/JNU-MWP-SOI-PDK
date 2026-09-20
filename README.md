# JNU-MWP-SOI-PDK

## 中文说明

`JNU-MWP-SOI-PDK` 是暨南大学光电混合集成实验室使用的硅光 PDK 项目。当前仓库以开发源码形式发布，包含 `JNU_MWP_PDK` technology、KLayout 菜单、DRC、PCell、固定黑盒器件和图层配置。白盒 GDS 保持私有，仅在实验室内授权分发。

> [!IMPORTANT]
> **使用过程中遇到 Bug，欢迎[提交 Issues](https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK/issues)。**

### 功能概览

该 PDK 支持在 KLayout 中进行硅光器件放置与参数化设计，包括直波导、90° 弯曲、S 弯、Taper、双总线微环和多种螺旋延迟线；提供 Circular、Bezier、Euler 弯曲，以及单宽度和复合宽度波导的路径转换。借助 PinRec 端口识别，可自动连接两个器件或进行端口吸附，并完成端口生成、编号文字阵列、图层筛选与展平、当前 Cell 及其子层级的 DRC 检查。功能菜单还支持自定义波导预设和 PDK 热重载；固定黑盒器件可用于布局与连线，实际器件内部结构需另行取得授权白盒 GDS。

### [点击查看详细使用说明](docs/USER_GUIDE.md)

包含入门步骤、PCell 功能、波导绘制与连接、菜单快捷键、DRC 和常见问题。

### 推荐安装与更新方式

使用能够访问本机文件并执行命令的 AI agent，按下文的克隆仓库流程完成安装或更新。

**推荐安装方式**：在 AI agent 中输入：

> 请在本机的 KLayout 中安装该项目：https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK

**推荐更新方式**：在 AI agent 中输入：

> 请在本机的 KLayout 中更新该项目：https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK

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

### 克隆仓库安装（Windows）

当前采用 Git 克隆安装，不需要配置在线 Package 索引。先安装 Git 和 KLayout，关闭 KLayout，在 PowerShell 执行：

```powershell
git clone https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK.git "$env:USERPROFILE\JNU-MWP-SOI-PDK"
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\JNU-MWP-SOI-PDK\Install_Cloned_PDK.ps1"
```

安装脚本创建目录联接，直接加载克隆目录中的源码，而不是再复制一份：

```text
C:\Users\<用户名>\KLayout\salt\JNU_MWP_PDK
  -> C:\Users\<用户名>\JNU-MWP-SOI-PDK\salt\JNU_MWP_PDK
```

已克隆过仓库时，只需从该仓库运行 `Install_Cloned_PDK.ps1`。自定义 KLayout 用户目录可用 `-KLayoutHome` 指定，或使用已有的 `KLAYOUT_HOME`。
不需要额外复制 `tech/`。请勿把整个仓库放入 `KLayout/salt/`，否则可能重复扫描源码。
若已有 `salt/JNU_MWP_PDK`、`tech/JNU_MWP_PDK` 或独立 JNU loader，脚本会停止并保留现有文件。
请关闭 KLayout，先把旧安装移至 KLayout 目录以外备份，再重试；不要删除白盒 GDS 或修改其他 PDK。
克隆目录需要长期保留，移动或删除它会使目录联接失效。

重启 KLayout 后，应能看到：

- Technology：`JNU_MWP_PDK`
- 顶部功能菜单：`JNU_MWP_PDK`
- 器件库：`JNULib`、`JNULib_BlackBox`

`JNULib` 提供 8 类可编辑 PCell；`JNULib_BlackBox` 自动加载仓库自带的 25 个固定黑盒器件，无需另行取得白盒 GDS。选择 `Instance → JNULib_BlackBox` 即可放置器件。黑盒覆盖 1310/1550 nm 的光栅耦合器、端面耦合器、MMI、分光器、偏振分束器、偏振旋转器、偏振器、光开关和终端器件。

黑盒只保留器件占位矩形、PinRec 端口、DevRec 边界和名称标签，不包含内部物理结构。这些占位图形用于布局与连接，不能直接作为最终流片的器件结构。

### 更新与白盒 GDS

GitHub 更新不会自动同步到本机。在克隆目录的 `main` 分支运行：

```powershell
git -C "$env:USERPROFILE\JNU-MWP-SOI-PDK" pull --ff-only origin main
```

随后重启 KLayout；仅修改 Python 功能时也可使用 `Reload JNU PDK`。目录联接使更新直接作用于实际安装，无需重复复制。
遇到本地修改或分支分歧时先处理并保留自己的修改，不要使用强制重置。重要版图在升级 PCell 代码前应备份。

白盒 GDS 来自私有仓库 `Jerry-behappy/JNU-MWP-SOI-Library`，需单独授权获取；不会随本仓库克隆或更新。
获授权后，将解压得到的 `JNU_MWP_gds` 内容放入 KLayout 用户目录的 `jnu_private/JNU_MWP_gds`，重启或重载即可在 `JNULib` 中使用。
既有源码目录中的 `pymacros/JNU_MWP_gds` 仍兼容加载。不要将任何白盒 GDS 提交到本仓库。

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

`JNU-MWP-SOI-PDK` is a silicon photonics PDK project used by the Optoelectronic Hybrid Integration Laboratory at Jinan University. This repository provides the development source, technology, menus, DRC, PCells, fixed blackbox devices and layer configuration. Whitebox GDS remains private and is distributed only to authorized laboratory users.

> [!IMPORTANT]
> **Found a bug? Please [submit an issue](https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK/issues).**

### Capabilities

The PDK supports silicon-photonic layout and parametric device design in KLayout, including straight waveguides, 90-degree bends, S-bends, tapers, double-bus microrings, and spiral delay lines. It provides Circular, Bezier, and Euler bends, reversible path conversion for single-width and composite-width waveguides, PinRec-based device connections and snapping, pin creation, numbered text arrays, layer filtering and flattening, and DRC of the active cell and its descendants. Saved waveguide presets and PDK hot reload support repeated design work. Bundled blackboxes provide placement and connectivity references; actual internal device geometry requires separately authorized whitebox GDS.

### [Read the detailed user guide](docs/USER_GUIDE.md#english-user-guide)

Covers getting started, PCells, waveguide routing, menu shortcuts, DRC, and troubleshooting.

### Recommended Installation and Updates

Use an AI agent that can access local files and run commands, following the Git clone workflow below.

**Recommended installation**: enter this prompt in the AI agent:

> Please install this project in KLayout on this computer: https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK

**Recommended update**: enter this prompt in the AI agent:

> Please update this project in KLayout on this computer: https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK

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

### Git Clone Installation (Windows)

The current installation method uses a Git clone, without an online package index.
Install Git and KLayout, close KLayout, then run in PowerShell:

```powershell
git clone https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK.git "$env:USERPROFILE\JNU-MWP-SOI-PDK"
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\JNU-MWP-SOI-PDK\Install_Cloned_PDK.ps1"
```

The installer creates a directory junction so KLayout loads the clone directly:

```text
C:\Users\<username>\KLayout\salt\JNU_MWP_PDK
  -> C:\Users\<username>\JNU-MWP-SOI-PDK\salt\JNU_MWP_PDK
```

For an existing clone, only run its installer. Use `-KLayoutHome` or `KLAYOUT_HOME`
for a custom user directory. No separate `tech/` copy is needed. Do not clone the
whole repository under `KLayout/salt/`. Existing PDK folders or legacy loaders are
never overwritten: close KLayout and back them up outside KLayout before retrying.
Preserve private GDS and other PDKs. Keep the clone at its installed location;
moving or deleting it breaks the junction.

Restart KLayout. After successful loading, KLayout should show:

- Technology: `JNU_MWP_PDK`
- Top-level menu: `JNU_MWP_PDK`
- Libraries: `JNULib`, `JNULib_BlackBox`

`JNULib` provides eight editable PCell types. `JNULib_BlackBox` automatically loads 25 bundled fixed blackbox devices without requiring whitebox GDS. Use `Instance → JNULib_BlackBox` to place them. The devices cover 1310/1550 nm grating and edge couplers, MMIs, splitters, polarization beam splitters, a polarization rotator, polarizers, optical switches, and a terminator.

Blackboxes retain only a rectangular footprint, PinRec ports, DevRec bounds, and a name label. They omit internal physical geometry and are layout/connectivity placeholders, not final fabrication geometry.

### Updates and Whitebox GDS

GitHub changes are not applied automatically. On the clone's `main` branch, run:

```powershell
git -C "$env:USERPROFILE\JNU-MWP-SOI-PDK" pull --ff-only origin main
```

Restart KLayout; Python-only changes may also use Reload JNU PDK. The junction
removes the need to copy updated files. Preserve local changes and resolve branch
divergence instead of forcing a reset. Back up important layouts before PCell upgrades.

Whitebox GDS requires separate authorization to `Jerry-behappy/JNU-MWP-SOI-Library`.
Put the authorized extracted GDS files in `<KLayout user home>/jnu_private/JNU_MWP_gds`
and restart/reload. Legacy `pymacros/JNU_MWP_gds` remains supported. Public code
updates do not update private GDS. Never commit whitebox GDS to this repository.

### Notes

This project is based on the original project by Lukas Chrostowski and contributors. The original MIT license and copyright notices have been retained. See `LICENSE.md` in the repository root.

The fixed whitebox GDS directory is intentionally not committed:

```text
salt/JNU_MWP_PDK/pymacros/JNU_MWP_gds/
```

The whitebox directory is excluded by `.gitignore`. Bundled blackbox GDS loads independently, and PCell source code remains included. Maintainers can run `salt/JNU_MWP_PDK/pymacros/JNU_MWP_tools/release/export_blackbox_gds.py --source <local-whitebox-directory> --output <new-blackbox-directory>` to refresh the blackbox data. To distribute blackboxes without PCell source code, use the separate blackbox packaging workflow.

Generated files such as `klayoutrc*`, `__pycache__`, `.pyc`, `.pyo`, and log files are not tracked by version control.
