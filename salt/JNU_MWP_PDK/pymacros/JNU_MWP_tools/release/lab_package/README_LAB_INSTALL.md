# JNU MWP PDK 实验室完整 Package

## 中文说明

本交付包包含白盒固定 GDS、8 类公开 PCell、波导工具、菜单和 DRC。
含器件设计细节，仅通过实验室内部渠道发送；不要上传公开 GitHub。
公开仓库用于维护代码和打包工具，不是本完整包的更新源。
固定器件来源为私有仓库 `Jerry-behappy/JNU-MWP-SOI-Library/JNU_MWP_gds`。
发布者通过已授权账户取得器件后打包；接收本完整 ZIP 的同事不需要 GitHub 凭据。
不要把访问令牌写入 `grain.xml`、安装脚本或索引。

### 安装

1. 安装 KLayout 0.30 或更新版本，将整个 ZIP 解压到可写的固定目录。
2. 关闭正在使用的 KLayout，避免同时安装、更新同一个包。
3. 在解压目录打开 PowerShell，运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Open_Lab_Package_Manager.ps1
```

若找不到 KLayout，追加 `-KLayoutExe "实际安装目录\klayout_app.exe"`。
脚本根据解压位置生成 `repository.local.xml`，只为此次 KLayout 设置实验室索引。
4. 在打开的 KLayout 中选择 `Tools > Manage Packages > Install New Packages`。
   找到 `JNU_MWP_PDK`，勾选安装并点击 `Apply`。
5. 关闭并重新打开 KLayout。Technology 中应显示 `JNU_MWP_PDK`，
   顶部出现同名菜单，Library 中出现 `JNULib` 和 `JNULib_BlackBox`。

整个 Package 安装在 KLayout 用户目录的 `salt/JNU_MWP_PDK`。
无需复制 `tech/JNU_MWP_PDK`，无需更改 `.lyt` 路径，也不需要 Python。
首次安装前若已手动安装过 JNU PDK，请先把原有的 JNU Salt 目录、JNU Technology
目录和旧 JNU 根目录 loader 备份到 KLayout 搜索路径之外，然后再安装。
不要删除自己另外保存的器件 GDS 或版图。

### 更新与卸载

收到实验室更新 ZIP 后解压，并运行新版的同一入口脚本。
在 `Update Packages` 选择 JNU 包进行更新，然后重启 KLayout。
发布者必须提高 `grain.xml` 的版本号，才能在列表中识别新版本。
请把个人修改的 DRC 或额外器件另行备份，Package 更新会替换已安装包内容。
在 `Current Packages` 选择 JNU 包并执行 `Remove Package` 可卸载，然后重启。
直接启动 KLayout 可以正常使用已安装 PDK；管理实验室更新时使用本入口。
此索引仅列出 JNU；安装或更新 SiEPIC 时使用正常启动的 KLayout 默认索引。

### 快捷键

`9` Path to Waveguide；`8` Waveguide to Path；
`6` Cell Connect by Waveguide；`7` Snap components。

## English Instructions

This internal delivery includes fixed whitebox GDS, eight public PCells, waveguide
tools, menus and DRC. Share it only within the laboratory. Do not upload it to the
public GitHub repository, which hosts the source and build tools only.
Fixed GDS originates from the private `Jerry-behappy/JNU-MWP-SOI-Library`
repository. The publisher retrieves it with an authorized account; recipients
of the complete internal ZIP do not need GitHub credentials. Never put access
tokens in package metadata, launchers or indexes.

Install KLayout 0.30 or newer. Extract the entire ZIP to a writable directory,
close KLayout, and run `Open_Lab_Package_Manager.ps1` using the PowerShell command
above. Supply `-KLayoutExe` if automatic executable discovery fails.

In the launched KLayout, open `Tools > Manage Packages > Install New Packages`,
select `JNU_MWP_PDK`, and click `Apply`. Restart KLayout after installation.
The package lives entirely under `salt/JNU_MWP_PDK`; no external `tech` directory,
machine-specific paths, or separate Python installation are needed.

Before migrating an existing manual installation, back up its JNU package,
Technology folder and legacy JNU root loader outside KLayout's search paths.
Preserve personal layouts and device files.

For updates, extract a newer laboratory delivery and use its launcher, then open
`Update Packages`. The publisher must increment the package version. Back up any
local rule or device edits before updating. Uninstall using `Current Packages >
Remove Package`, then restart KLayout.

The launcher scopes the laboratory index to its child process, without changing
system environment variables. This index lists JNU only. Launch KLayout normally
to manage SiEPIC packages using the default index.
