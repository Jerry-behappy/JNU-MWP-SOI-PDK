# JNU-MWP-SOI-PDK

## 中文说明

`JNU-MWP-SOI-PDK` 是暨南大学光电混合集成实验室使用的 KLayout 光子 PDK 工程。公开 Package 包含 `JNU_MWP_PDK` technology、KLayout 菜单、DRC、PCell、固定黑盒器件和图层配置；白盒 GDS 保持私有并单独授权安装。

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

### 公开 Package 与私有 GDS

推荐通过 `Tools > Manage Packages` 安装和更新，不需要额外复制 `tech/`。

1. 下载本仓库 ZIP 并解压，右键运行 [packages/Enable_JNU_Packages.ps1](packages/Enable_JNU_Packages.ps1)，一次性添加 JNU 索引。
2. 完全关闭 KLayout，从 Windows 开始菜单重新打开，在 `Install New Packages` 中安装 `JNU_MWP_PDK`，然后重启。
3. 以后通过 `Update Packages` 更新。公开包无需 GitHub 登录，包含 8 类 PCell 和 25 个黑盒器件。

白盒 GDS 位于私有仓库 `Jerry-behappy/JNU-MWP-SOI-Library`。获授权的同事接受邀请后下载其 ZIP，解压并运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\KLayout\salt\JNU_MWP_PDK\Install_Private_GDS.ps1" -Source "D:\下载\JNU-MWP-SOI-Library-main\JNU_MWP_gds"
```

白盒数据安装到 `KLayout/jnu_private/JNU_MWP_gds`，不被公开 Package 更新或卸载覆盖。
重启或 `Reload JNU PDK` 后，固定白盒器件出现在 `JNULib`。
支持 GitHub CLI 授权下载/更新；详见 [安装说明](packages/README_INSTALL.md)。
不要共享 token，也不要把白盒 GDS 放入本公开仓库。
当前使用自定义索引，包含官方包源，但尚未登记官方 Salt.Mine 默认列表。
从手动安装版迁移前，按安装说明备份旧包/技术副本并迁出私有 GDS，避免重复加载或更新丢失。

### 可选：离线实验室完整包

实验室完整包支持 `Tools > Manage Packages` 安装，不需要额外复制 `tech/`。
固定白盒 GDS 来自私有仓库 `Jerry-behappy/JNU-MWP-SOI-Library`，不上传本公开仓库。
发布者使用已授权账户取得 GDS 后生成内部 ZIP；同事解压后运行包内
`Open_Lab_Package_Manager.ps1`，在 `Install New Packages` 中安装 `JNU_MWP_PDK`，然后重启。
此入口生成本地安装索引，不向公共 Salt.Mine 发布，也不需要接收者提供 GitHub 凭据。
完整包包含固定器件、8 类公开 PCell、黑盒库、菜单和 DRC。

参阅 [实验室包构建说明](salt/JNU_MWP_PDK/pymacros/JNU_MWP_tools/release/lab_package/README_BUILD.md)
和 [安装、更新与卸载](salt/JNU_MWP_PDK/pymacros/JNU_MWP_tools/release/lab_package/README_LAB_INSTALL.md)。
公开源码下载不包含白盒 GDS，不等同于实验室完整 ZIP。

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

`JNU-MWP-SOI-PDK` is a KLayout photonic PDK for the Optoelectronic Hybrid Integration Laboratory at Jinan University. The public package contains the technology, menus, DRC, PCells, fixed blackbox devices and layer configuration. Whitebox GDS remains private and is installed separately with authorization.

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

### Public Package and Private GDS

Download and extract this repository, then run
[packages/Enable_JNU_Packages.ps1](packages/Enable_JNU_Packages.ps1) once.
Close KLayout and reopen it from the Windows Start menu. Use Tools > Manage
Packages > Install New Packages to install `JNU_MWP_PDK`, then restart.
Use Update Packages for future releases. No separate `tech/` folder or GitHub
login is required for the public package, which includes eight PCells and 25 blackboxes.

Authorized colleagues download the private `Jerry-behappy/JNU-MWP-SOI-Library`
ZIP and run `Install_Private_GDS.ps1 -Source <extracted-JNU_MWP_gds-folder>`.
Whitebox data lives in `KLayout/jnu_private/JNU_MWP_gds`, outside the package's
update/uninstall directory. Restart or use Reload JNU PDK to see it in `JNULib`.
Authenticated GitHub CLI updates are also supported; see the
[installation guide](packages/README_INSTALL.md). Never share tokens or commit
whitebox GDS to this public repository. The custom index includes the official
package source but is not registered in the default Salt.Mine listing.
Before migrating a manual installation, follow the backup and private-data
migration steps in the guide to avoid duplicate loaders or losing private GDS.

### Optional: Offline Complete Laboratory Package

The complete laboratory ZIP supports `Tools > Manage Packages` installation
without an extra `tech/` folder. Fixed whitebox GDS comes from the private
`Jerry-behappy/JNU-MWP-SOI-Library` repository and is never committed here.
An authorized publisher builds the internal ZIP. Recipients extract it, run
`Open_Lab_Package_Manager.ps1`, install `JNU_MWP_PDK` from `Install New Packages`,
and restart KLayout. The launcher creates a local package index; it does not
publish to the public Salt.Mine and recipients do not need GitHub credentials.
The full package includes fixed devices, eight public PCells, the blackbox library,
menus and DRC. Downloading this public source repository alone does not supply GDS.

See the [build guide](salt/JNU_MWP_PDK/pymacros/JNU_MWP_tools/release/lab_package/README_BUILD.md)
and [installation guide](salt/JNU_MWP_PDK/pymacros/JNU_MWP_tools/release/lab_package/README_LAB_INSTALL.md).

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
