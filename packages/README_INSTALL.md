# JNU PDK Package

## 中文

### 安装公开 PDK

公开包包含 Technology、8 类公开 PCell、菜单、DRC 和固定黑盒器件，不包含白盒 GDS。
只需 KLayout 0.30 或更新版本，无需另行复制 `tech/`。不需要 GitHub 登录。

1. 下载本仓库 ZIP 并解压，在 `packages` 目录右键 `Enable_JNU_Packages.ps1`，选择“使用 PowerShell 运行”。只需配置一次。
2. 完全关闭 KLayout，从 Windows 开始菜单重新打开。
3. `Tools > Manage Packages > Install New Packages` 中选择 `JNU_MWP_PDK`，点击 Apply，然后重启。
4. 以后通过 `Update Packages` 更新公开代码；无需重新下载 ZIP。

索引来自本 GitHub 仓库，并包含官方 Salt.Mine，因此仍可安装 SiEPIC 等包。
没有登记官方 Salt.Mine，未配置本索引的电脑不会自动看到 JNU 包。
脚本保留已有自定义索引，将用户级 `KLAYOUT_SALT_MINE` 指向 `KLayout/jnu-package-sources.xml`。
从旧终端或旧 VSCode 启动 KLayout 可能仍继承旧环境变量，需要重新打开终端/VSCode。

若使用过手动安装版，请先关闭 KLayout，把旧 `salt/JNU_MWP_PDK`、旧 `tech/JNU_MWP_PDK` 及独立 JNU loader 移到 KLayout 目录以外备份，再安装 Package，避免重复加载。不要移动其他 PDK。
旧版本位于 `pymacros/JNU_MWP_gds` 的本机白盒 GDS 必须先按下面方法安装到独立目录，不能依赖 Package 更新保留这些文件。

### 安装授权白盒 GDS

仓库所有者只向需要完整器件的实验室成员授权 `Jerry-behappy/JNU-MWP-SOI-Library`。
每位接收者使用自己的 GitHub 账号，不共享 token，也不把凭据放入索引或 PDK。

最简单的方式：接受邀请后，在私有仓库选择 Code > Download ZIP，解压。
运行以下命令，将路径替换为解压出的 `JNU_MWP_gds` 目录：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\KLayout\salt\JNU_MWP_PDK\Install_Private_GDS.ps1" -Source "D:\下载\JNU-MWP-SOI-Library-main\JNU_MWP_gds"
```

需要直接下载/更新时，安装 Git 和 GitHub CLI，执行一次 `gh auth login`。
之后运行相同脚本但省略 `-Source`，脚本会使用当前授权账号下载私有仓库：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\KLayout\salt\JNU_MWP_PDK\Install_Private_GDS.ps1"
```

GDS 安装到 `%USERPROFILE%\KLayout\jnu_private\JNU_MWP_gds`；如配置了 `KLAYOUT_HOME`，使用该目录。
也可通过 `-KLayoutHome` 显式指定用户目录。现有数据替换前保留带日期的备份。
安装完成后重启，或执行 `Reload JNU PDK`，固定白盒器件显示在 `JNULib` 中。
公开 Package 的更新/卸载不删除这个独立目录。白盒 GDS 更新仍需单独运行安装脚本。
撤销 GitHub 授权只能阻止后续下载，不能远程收回已下载的 GDS。

## English

### Public Package

The public package contains the technology, eight public PCells, menus, DRC and
fixed blackbox devices. It does not contain whitebox GDS. KLayout 0.30+ is required;
no extra `tech/` directory or GitHub login is needed.

Download and extract the repository ZIP, then run `packages/Enable_JNU_Packages.ps1`
once. Close KLayout and reopen it from the Windows Start menu. Install
`JNU_MWP_PDK` through Tools > Manage Packages > Install New Packages and restart.
Use Update Packages for subsequent code updates.

The custom GitHub index includes the official Salt.Mine and preserves existing
custom sources. It is not registered in the default public Salt.Mine listing.
The setup script sets the user-level `KLAYOUT_SALT_MINE` to
`KLayout/jnu-package-sources.xml`. Restart terminals/VSCode before launching KLayout
from them. Back up an old manual installation outside KLayout before migration;
do not keep duplicate technology files or loaders. Migrate old bundled private
GDS with the separate installer before updating the package.

### Authorized Whitebox GDS

Accept your invitation to `Jerry-behappy/JNU-MWP-SOI-Library`, download and extract
its ZIP, then run `Install_Private_GDS.ps1 -Source <extracted-JNU_MWP_gds-folder>`.
Alternatively, install Git and GitHub CLI, run `gh auth login` with your own
authorized account, and run the installer without `-Source` to download/update.
Never share tokens or embed credentials in the package or index.

The destination is `<KLayout user home>/jnu_private/JNU_MWP_gds`, outside Salt's
update/uninstall directory. `KLAYOUT_HOME` and `-KLayoutHome` are supported.
Existing data is backed up before replacement. Restart KLayout or use Reload JNU
PDK to load fixed devices into `JNULib`. Update private GDS separately by rerunning
the installer. Revoking repository access does not remove previously downloaded files.
