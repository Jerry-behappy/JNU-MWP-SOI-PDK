<p align="right">
  <a href="README.md"><img src="docs/assets/readme/lang-zh-active.svg" alt="简体中文（当前）" height="30"></a>
  <a href="README.en.md"><img src="docs/assets/readme/lang-en.svg" alt="English" height="30"></a>
</p>

<p align="center"><img src="docs/assets/readme/jinan-university-logo.png" alt="暨南大学校徽与校名" width="340"></p>

# JNU-MWP-SOI-PDK

暨南大学光电混合集成实验室的 KLayout 硅光 PDK，提供 `JNU_MWP_PDK` Technology、参数化 `JNULib`、固定器件 `JNULib_BlackBox`、波导工具和 DRC。公开仓库可独立使用 9 类 PCell 与 30 个固定黑盒；29 份固定白盒 GDS 由独立器件库授权安装。

以下菜单路径以默认 English 界面为例；切换为简体中文后，菜单名称会随之翻译。

## 功能导航

**点击下方任意功能框，跳转到本页对应的使用说明。**

<table>
  <tr><th colspan="2">JNU-MWP-SOI-PDK · 功能框图</th></tr>
  <tr>
    <td width="50%"><a href="#devices"><img src="docs/assets/features/devices-zh.svg" width="520" alt="器件库与参数化设计"></a></td>
    <td width="50%"><a href="#waveguides"><img src="docs/assets/features/waveguides-zh.svg" width="520" alt="波导设计"></a></td>
  </tr>
  <tr>
    <td width="50%"><a href="#connections"><img src="docs/assets/features/connections-zh.svg" width="520" alt="器件连接与对齐"></a></td>
    <td width="50%"><a href="#layout-tools"><img src="docs/assets/features/layout-zh.svg" width="520" alt="版图辅助"></a></td>
  </tr>
  <tr>
    <td width="50%"><a href="#drc"><img src="docs/assets/features/drc-zh.svg" width="520" alt="设计规则检查"></a></td>
    <td width="50%"><a href="#installation"><img src="docs/assets/features/setup-zh.svg" width="520" alt="安装与维护"></a></td>
  </tr>
</table>

<a id="devices"></a>
## 01 · 器件库与参数化设计

1. 在 KLayout 选择 `JNU_MWP_PDK` Technology，使用 **Instance** 工具打开 `JNULib`；选择 PCell 并设置参数，放置后仍可在实例属性中编辑。
2. 九类 PCell 涵盖直波导、90° 弯曲、S 弯、Taper、双总线微环、阿基米德螺旋、普通与复合宽度 Paperclip 螺旋，以及四圆弧长度补偿波导。`Pcell_Waveguide_Bump` 可编辑增量长度、宽度、有效半径和最大角度。
3. `JNULib_BlackBox` 提供 30 个固定器件的占位和 PinRec 端口，适合排版与连线。授权安装独立白盒库后，`JNULib` 才会显示对应的固定白盒结构。黑盒占位不能作为最终流片结构。

<a id="waveguides"></a>
## 02 · 波导设计

1. 在任意图层绘制仅含水平、垂直线段的 Manhattan Path，选中后按 **`9`**，或选择 **JNU_MWP_PDK → Waveguides → Path to Waveguide**。
2. 选择单宽度、复合宽度或已保存的 User-Defined 预设；设置 Circular／Bezier／Euler 弯曲、半径和宽度，确认计算结果后点击 **OK**。成功转换的 Path 会被可编辑波导 PCell 替换。
3. 需要修改走线时，选中波导按 **`8`**（**Waveguide to Path**），恢复为 Si `1/0` 层 Path；修改后再按 `9`。可用 **Save as User-Defined** 保存常用参数和 Note。非 Manhattan Path 会被跳过；弯曲空间不足时先检查提示。

<a id="connections"></a>
## 03 · 器件连接与对齐

- **Cell Connect by Waveguide（`6`）**：恰好选中两个有相向 PinRec 的器件实例，工具选择最近的可用端口；共线时生成波导，存在侧向偏移时生成可编辑 S 弯。生成后检查间距和弯曲空间。
- **Snap components（`7`）**：选中要移动的实例或对象，把鼠标停在未选中的参考器件上，再按 `7`。工具按相向端口整体平移选中组，不旋转、不镜像，也不额外生成波导。

<a id="layout-tools"></a>
## 04 · 版图辅助

- **Layout → Make Pins for Cell**：进入目标 Cell，选择需要端口的左／右／上／下边，生成 PinRec，并在缺少 DevRec 时补建边界；完成后检查端口方向与位置。
- **Layout → Numerical text array**：填写起止编号、步长、横向／纵向、目标层、间距与字号，确认后用鼠标放置；编号保持为可编辑的 `Basic.TEXT` 实例。
- **Layout → Layer Exclude**：建议先另存版图副本。勾选要**保留**的图层，按需展平、合并或删除其他 Cell；操作不会自动保存 GDS，完成后检查并另存。

<a id="drc"></a>
## 05 · 设计规则检查

1. 进入要检查的 Cell，打开 **JNU_MWP_PDK → DRC → JNU_MWP_DRC**，在 KLayout 原生 Macro Development 中编辑并**保存**规则。
2. 回到版图选择 **DRC → Run JNU_MWP_DRC**，检查范围为当前编辑 Cell 及其子层级。
3. 在 **Marker Browser** 中定位违规，修复后重新运行；未保存的规则修改不会被运行菜单采用。

<a id="installation"></a>
<a id="克隆仓库安装windows"></a><a id="git-clone-installation-windows"></a>
## 06 · 安装与维护

### Windows：拖入 KLayout 安装

首次安装需要 KLayout 和 [Git](https://git-scm.com/downloads)。

1. **[下载安装宏 Install_JNU_PDK.lym](https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK/releases/download/installer-macro/Install_JNU_PDK.lym)**。
2. 将 `.lym` 拖入平时使用的 KLayout，在 **Macro Development** 中选择 **Install JNU PDK**，点击绿色 **Run**，再点击“安装”。
3. 完成后重启 KLayout，选择 `JNU_MWP_PDK` Technology，并确认顶部菜单及两个器件库已出现。

安装宏从正在运行的 KLayout 读取用户配置目录，克隆 `main` 并建立目录联接，不要求 KLayout 与源码在同一盘。**该下载入口安装 `main`；测试本页所在的 `JNU_MWP_PDK_V1.2` 开发分支，请使用下方 AI 提示词。**

### 用 AI 代理安装或更新开发分支

把下面的文字复制给**能够访问本机文件并执行命令**的 AI 代理。让它先检查现有安装，保留其他 PDK、私有 GDS 和本地改动。

**安装提示词**

> 请在我平时使用的 KLayout 中安装 https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK 的 `JNU_MWP_PDK_V1.2` 分支。先确认该 KLayout 实际使用的用户配置目录，检查是否已有 `salt/JNU_MWP_PDK` 安装或 Git 克隆；保留已有 PDK、私有白盒 GDS 和本地修改。通过 Git 克隆与目录联接安装，完成后重启验证 `JNU_MWP_PDK` Technology、`JNULib`、`JNULib_BlackBox` 和功能菜单。

**更新提示词**

> 请更新我当前 KLayout 安装的 JNU-MWP-SOI-PDK。先确定 `salt/JNU_MWP_PDK` 联接指向哪个 Git 克隆以及当前分支；如果是 `JNU_MWP_PDK_V1.2`，仅对该分支做安全的快进更新。不要强制重置、覆盖本地修改或删除私有白盒 GDS。更新后检查器件库与菜单，并说明是否需要重启。

<a id="更新与白盒-gds"></a><a id="updates-and-whitebox-gds"></a>
### 更新、语言与白盒

- `main` 安装版每次启动会后台检查 GitHub 更新；发现新版可点击弹窗中的“立即更新”，也可使用 **JNU_MWP_PDK → Check for PDK Updates**。开发分支不自动提示更新；完成更新后重启 KLayout。
- 选择 **JNU_MWP_PDK → Language → English / 简体中文** 切换菜单和 PCell 参数标签，**重启后生效**。仅修改 Python 功能时可用 **Reload JNU PDK** 热重载；启动宏、Technology 或安装路径变动后仍应重启。
- 获授权后使用 **JNU_MWP_PDK → Install / Update Whitebox Library**，从独立 [JNU-MWP-SOI-Library](https://github.com/Jerry-behappy/JNU-MWP-SOI-Library) 安装 29 份固定白盒；公开 PDK 仓库不包含白盒 GDS。

[详细使用说明](docs/USER_GUIDE.md) · [问题反馈](https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK/issues) · [许可证](LICENSE.md)
