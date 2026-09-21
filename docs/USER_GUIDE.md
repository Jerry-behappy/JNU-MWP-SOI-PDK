# JNU-MWP-SOI-PDK 使用说明 / User Guide

[返回项目 README](../README.md) | [English User Guide](#english-user-guide)

## 中文使用说明

本说明对应当前源码中的 `JNULib`、`JNULib_BlackBox` 与 `JNU_MWP_PDK` 菜单。安装和更新采用 Git 克隆方式，具体命令见 [README 安装说明](../README.md#克隆仓库安装windows)。长度、半径、宽度和间距参数未特别注明时均以 µm 为单位。

### 1. 开始使用

1. 完成克隆与安装，重启 KLayout，并使用可编辑模式打开或新建版图。
2. 将版图技术选择为 `JNU_MWP_PDK`，确认图层列表和顶部同名菜单已加载。
3. 使用 KLayout 的 Instance 工具，在 Library 中选择 `JNULib` 放置参数化器件，或选择 `JNULib_BlackBox` 放置固定黑盒器件。
4. 修改 PCell 的可编辑参数，查看底部带 `[uneditable]` 标记的派生结果，再确认放置。修改已放置器件时，打开该实例的 PCell 参数属性。
5. 按下文绘制波导或连接器件，检查端口位置，再对当前 Cell 执行 DRC。
6. 保存 GDS。重要设计在升级 PDK 或做展平、删层操作前应另存备份。

普通 PCell 的新实例使用内置默认值，不把上次实例的参数作为新建默认值。`Path to Waveguide` 的窗口设置与自定义预设则会保存，二者是不同的使用行为。

### 2. 器件与参数

`JNULib` 中可直接放置的 8 类 PCell：

| PCell | 主要用途与参数 |
|---|---|
| `Straight_Waveguide` | 恒定宽度直波导，设置长度与宽度。 |
| `Bend_90deg` | 90° 弯曲，选择 Circular、Bezier 或 Euler，并设置对应半径或曲率参数。 |
| `S_Bend` | S 形连接，设置水平长度、纵向偏移、宽度与弯曲类型。 |
| `Taper` | 两种宽度间的线性渐变；可设置渐变长度和两端恒宽延伸段。 |
| `Microring_DoubleBus` | 双总线微环，设置环与总线的尺寸、耦合间距等参数。 |
| `Paperclip_Spiral` | 回形针螺旋延迟线，设置宽度、间距、圈数、内侧长度、端口类型及弯曲参数。 |
| `Paperclip_Spiral_with_Composite_Waveguide` | 复合宽度回形针螺旋；横向直波导使用 straight width，纵向直波导及弯曲使用 bend width，并通过直段中的 taper 过渡。 |
| `Archimedean_Spiral` | 双臂阿基米德螺旋，以目标长度为下限确定圈数，并显示实际长度与外径等结果。 |

`Waveguide` 和 `Composite_Waveguide` 是波导转换工具创建的内部 PCell，不在 `JNULib` 的公开器件列表中直接选择。

**弯曲参数**：Circular 使用圆弧半径；Bezier 使用半径和 `B`，界面显示计算出的 `Rmax/Rmin`；Euler 使用 `Rmax/Rmin`，界面显示有效半径 `Reff`。相关界面中的弯曲采样点数自动计算并只读；修改输入后，适用的只读派生字段实时刷新。

**螺旋端口**：`type1` 为同侧端口，`type2` 为异侧错位端口，`type3` 为异侧等高端口。单宽度螺旋中 `gap` 表示相邻波导的边到边间距，中心线间距为 `pitch = width + gap`。使用复合宽度时还应检查不同截面和 taper 区域的实际间距。

**长度读数**：螺旋中的 `L` 为几何中心线总长度；`delta_L = L - abs(opt2.x - opt1.x)`，用于比较额外绕行长度，不是直接以时间为单位的延时。换算传播延时还需要群折射率及工作波长等信息。

### 3. 固定器件与黑盒

`JNULib_BlackBox` 随仓库提供 25 个固定黑盒 GDS，覆盖 1310/1550 nm 光栅耦合器、端面耦合器、MMI、分光器、偏振器件、光开关和终端器件。黑盒保留器件占位、端口、识别边界与名称，可用于规划布局及连接，但不包含可直接流片的内部结构。

固定白盒 GDS 来自另行授权的私有器件库。按 [README 中的白盒说明](../README.md#更新与白盒-gds) 放置到 KLayout 用户目录的 `jnu_private/JNU_MWP_gds` 后，重启或执行 `Reload JNU PDK`，即可在 `JNULib` 使用；已有源码目录中的 `pymacros/JNU_MWP_gds` 也兼容。取得白盒文件不会自动把已放置的黑盒替换为真实结构，交付前必须检查实际引用的器件。

### 4. 菜单与快捷键

以下路径均从顶部 `JNU_MWP_PDK` 菜单进入。快捷键为首次安装的默认值，用户在 KLayout 中的自定义设置优先。

| 菜单路径 | 默认快捷键 | 功能 |
|---|---|---|
| `Waveguides → Path to Waveguide` | `9` | 将选中的 Manhattan Path 转为单宽度或复合宽度波导。 |
| `Waveguides → Waveguide to Path` | `8` | 将支持恢复的波导实例还原为原始 Path。 |
| `Waveguides → Cell Connect by Waveguide` | `6` | 连接两个选中实例的最近可用相向端口。 |
| `Layout → Snap components` | `7` | 将选中对象整体平移到鼠标悬停参考对象的相向端口。 |
| `Layout → Make Pins for Cell` | 未预设 | 给当前 Cell 的指定边界生成端口与必要的 DevRec。 |
| `Layout → Numerical text array` | 未预设 | 生成横向或纵向的编号文字阵列。 |
| `Layout → Layer Exclude` | 未预设 | 展平目标 Cell，保留选定图层，并可选合并图形或删除其他 Cell。 |
| `DRC → JNU_MWP_DRC` | 未预设 | 打开原生 Macro Development 中的规则文件。 |
| `DRC → Run JNU_MWP_DRC` | 未预设 | 对当前编辑 Cell 及其子层级运行已保存的规则。 |
| `Reload JNU PDK` | 未预设 | 重载 JNU Python 模块、器件库和菜单。 |

### 5. 绘制与修改波导

#### Path to Waveguide

1. 在 `Si (1/0)` 或 `Waveguide (1/99)` 层绘制仅含水平、垂直线段的 Manhattan Path，并选中一个或多个 Path。`1/99` 默认隐藏，使用前可在图层面板中显示。
2. 按 `9`，选择 `Single-Width Waveguide`、`Composite-Width Waveguide`，或已保存的 `User-Defined` 预设。
3. 单宽度模式设置波导宽度和弯曲参数；复合模式还需设置直宽、弯宽、两端宽度、taper 长度与 transition 长度。端部宽度可选择当前直宽或弯宽。
4. 检查只读采样点数和曲率结果，点击 OK。成功转换的输入 Path 会被对应波导实例替换。
5. 若提示某些路径空间不足，检查问题线段。允许降低半径会改变实际弯曲参数，应重新核对；固定 taper/transition 仍放不下的路径不会转换。非 Manhattan Path 会被跳过。

用 `Save as User-Defined` 保存常用设置；在 `User-Defined` 页选择、重命名预设或填写 Note，管理窗口支持删除预设。窗口有效设置、当前页签与预设会保存。

#### Waveguide to Path

选中待修改的波导实例，按 `8` 恢复 Si 层的原始 Manhattan Path，修改路径后再按 `9` 转换。复合波导恢复的 Path 宽度使用直宽。此功能不是把任意 Polygon 或任意 PCell 自动反推为中心线。

未选中可识别的波导时，工具会询问是否转换当前 Cell 中的波导；取消即不执行批量转换。普通展平或外部软件处理可能丢失恢复数据，需保留可编辑设计源文件。

### 6. 连接与吸附器件

**Cell Connect by Waveguide**：恰好选中两个 Cell Instance，按 `6`。工具识别 PinRec 并选择距离最近的可用相向端口，支持水平 `0°/180°` 或垂直 `90°/270°` 配对。端口严格共线时创建与 Path to Waveguide 一致的内部 `Waveguide`；存在侧向偏移时创建可编辑 `S_Bend`。不支持阵列实例直接展开，也不是任意角度或自动避障布线工具。生成后应检查宽度、弯曲空间和与其他结构的间距。

**Snap components**：选中要移动的对象，把鼠标停在未选中的参考对象上，再按 `7`。两侧需有可识别的相向 PinRec；工具整体平移选中组，不旋转、不镜像，也不生成连接波导。吸附成功时静默完成。参考对象依赖 KLayout 的 transient selection，鼠标悬停未命中对象时会提示失败。

### 7. 端口、文字与图层处理

**Make Pins for Cell**：进入需要加工的 Cell，选择左、右、上、下哪些边生成端口。工具依据边界上的物理图形生成 PinRec；没有 DevRec 时按器件边界补建。操作后检查端口位置、宽度和方向，避免对错误的 Cell 执行。

**Numerical text array**：设置起始编号、结束编号、步长、横向或纵向、目标层、间距和字号，确认后进入鼠标跟随放置。文字保持为 `Basic.TEXT` 实例，间距按相邻文字 bbox 的中心距定义。

**Layer Exclude**：建议只对设计副本使用。当前 layout 存在名为 `TOP` 的 Cell 时优先以它为展平目标，否则使用当前 Cell；弹窗会显示目标名称。勾选表示“保留”图层，不是“删除”图层。未勾选的层会从整个当前 layout 删除，还可选择删除目标以外的 Cell、合并选定层图形或将 Si Path 转为 Polygon。工具不自动保存 GDS，完成后检查并另存输出。

### 8. DRC 检查

1. 进入要检查的 Cell。检查范围是该 Cell 及其子层级，不是屏幕缩放框或可见区域。
2. 通过 `DRC → JNU_MWP_DRC` 打开原生 Macro Development，查看或修改规则，并保存文件；未保存的编辑不会被下一步菜单执行采用。
3. 回到版图，执行 `DRC → Run JNU_MWP_DRC`。
4. 在 Marker Browser 中查看违规类别与位置，修复后再运行。

规则可持久化编辑，但从 Git 更新前应保留自己的规则修改。检查结果受启用规则、图层映射和检查 Cell 影响；无报错不等于满足所有工艺要求，也不代表黑盒已经具备真实器件结构。

### 9. 图层与常见问题

| 图层 | 用途 |
|---|---|
| `Si (1/0)` | 硅波导实体。 |
| `PinRec (1/10)` | 带方向的端口短 Path 与名称。 |
| `DevRec (68/0)` | 器件识别区域。 |
| `Text (10/0)` | 参数与器件标注。 |
| `Waveguide (1/99)` | 输入引导与旧版恢复兼容，默认隐藏。 |

- **找不到菜单或库**：检查克隆目录联接是否有效、安装文件是否完整，避免旧 `tech` 副本或 loader 重复加载；重新启动并查看 Macro Development 的加载错误。
- **没有固定白盒器件**：公开仓库不含私有 GDS，需另行授权安装；黑盒和公开 PCell 可独立使用。
- **参数不能编辑**：`[uneditable]` 是派生结果，应修改关联输入；弯曲采样点数由程序自动计算。
- **两器件无法连接**：确认恰好选中两个非阵列实例、PinRec 存在、端口相向且留有足够空间。
- **保存重开后无法还原波导路径**：先确认 JNU PDK 已正常加载，再检查是否展平或经其他软件移除了 PCell/恢复属性；保留原始可编辑文件。
- **更新后界面未变化**：执行 `Reload JNU PDK` 可更新 Python 功能；涉及启动宏、技术或安装路径时请完全重启。升级前备份重要版图。

### 10. 安装与维护

首次安装请按 [README 克隆安装说明](../README.md#克隆仓库安装windows)，先查询 KLayout 实际用户配置目录，再运行安装脚本。程序、用户目录和源码可以在不同盘符，不要将 PDK 安装目标误设为程序目录。

更新时按 [README 更新说明](../README.md#更新与白盒-gds)，在已安装克隆的 `main` 分支执行 `git pull --ff-only origin main`，保留本地修改和私有 GDS。纯 Python 功能更新后可执行 `Reload JNU PDK`；涉及启动宏、Technology 或安装路径时应完全重启。选择 `JNU_MWP_PDK` Technology 后检查菜单、器件库和图层是否正常。

---

## English User Guide

[Back to README](../README.md)

This guide describes the current `JNULib`, `JNULib_BlackBox`, and `JNU_MWP_PDK` menus. Follow the [Git clone installation instructions](../README.md#git-clone-installation-windows). Geometry parameters use micrometers unless stated otherwise.

### Getting Started

1. Install the clone, restart KLayout, and open or create an editable layout using the `JNU_MWP_PDK` technology.
2. Use Instance with `JNULib` for PCells or `JNULib_BlackBox` for fixed blackboxes.
3. Edit the input parameters and inspect the derived fields marked `[uneditable]` before placing a device.
4. Draw or connect waveguides, check their ports, then run DRC on the intended cell.
5. Save GDS and keep a separate backup before PDK upgrades, flattening, or layer deletion.

New ordinary PCell instances use built-in defaults. Path to Waveguide settings and user-defined presets are saved separately.

### Device Libraries

| Public PCell | Purpose |
|---|---|
| `Straight_Waveguide` | Constant-width straight waveguide. |
| `Bend_90deg` | Circular, Bezier, or Euler 90-degree bend. |
| `S_Bend` | S-shaped connection with configurable length, offset, and width. |
| `Taper` | Linear width transition with optional constant-width end extensions. |
| `Microring_DoubleBus` | Double-bus microring resonator. |
| `Paperclip_Spiral` | Paperclip delay line with configurable turns, spacing, and ports. |
| `Paperclip_Spiral_with_Composite_Waveguide` | Paperclip with straight width on horizontal straights, bend width on vertical straights and bends, and tapers on straight sections. |
| `Archimedean_Spiral` | Dual-arm Archimedean spiral sized to meet a target-length lower bound. |

The internal `Waveguide` and `Composite_Waveguide` PCells are created by the routing tools, not selected from the public library list. Circular uses a radius; Bezier adds `B` and displays derived `Rmax/Rmin`; Euler uses `Rmax/Rmin` and displays `Reff`. Bend sampling is automatic and read-only, with applicable derived fields refreshed as inputs change.

Spiral ports use `type1` for same-side, `type2` for opposite-side offset, and `type3` for opposite-side equal-height ports. For a single-width spiral, `gap` is edge-to-edge spacing and `pitch = width + gap`. Check local spacing separately for composite widths and taper regions. Spiral `L` is centerline length and `delta_L = L - abs(opt2.x - opt1.x)` is extra geometric length, not a propagation time.

The repository includes 25 fixed blackboxes with footprints and ports but no internal fabrication geometry. Authorized whitebox GDS is installed separately as described in the [README](../README.md#updates-and-whitebox-gds). Installing whitebox files does not automatically replace already placed blackbox instances.

### Menus and Shortcuts

All paths below start at `JNU_MWP_PDK`. User-configured shortcuts take priority over these defaults.

| Menu path | Default key | Action |
|---|---|---|
| `Waveguides → Path to Waveguide` | `9` | Convert selected Manhattan Paths to waveguides. |
| `Waveguides → Waveguide to Path` | `8` | Recover supported waveguide instances as original Paths. |
| `Waveguides → Cell Connect by Waveguide` | `6` | Connect the nearest eligible facing pins of two instances. |
| `Layout → Snap components` | `7` | Translate selected objects to facing pins on the hovered reference. |
| `Layout → Make Pins for Cell` | None | Create pins on specified sides of the current cell. |
| `Layout → Numerical text array` | None | Place a horizontal or vertical numbered text array. |
| `Layout → Layer Exclude` | None | Flatten, retain selected layers, and optionally merge shapes or remove other cells. |
| `DRC → JNU_MWP_DRC` | None | Open rules in native Macro Development. |
| `DRC → Run JNU_MWP_DRC` | None | Run saved rules on the active cell and its descendants. |
| `Reload JNU PDK` | None | Reload JNU Python code, libraries, and menus. |

### Waveguide Workflow

1. Draw horizontal/vertical Manhattan Paths on `Si (1/0)` or `Waveguide (1/99)` and select them. Enable the normally hidden `1/99` layer when needed.
2. Press `9` and choose `Single-Width Waveguide`, `Composite-Width Waveguide`, or a saved `User-Defined` preset.
3. Set width and bend parameters. Composite mode also sets straight/bend widths, start/end width choices, taper length, and transition length.
4. Check the calculated fields and confirm. Successful conversions replace their input Paths. Non-Manhattan paths are skipped; insufficient bend space may prompt for a reduced radius. Paths that cannot fit fixed transitions are left unchanged.
5. Use `Save as User-Defined` for reusable settings. Presets can be selected, renamed, annotated with a Note, or deleted through the management window.

To revise a route, select its waveguide instance and press `8`, edit the recovered Si Path, then press `9` again. Composite recovery uses the straight width. With no recognized waveguide selected, a confirmation is required before converting the current cell's waveguides. This is not a general polygon-to-centerline tool; flattening or external processing can remove recovery data.

### Connecting and Arranging Devices

For **Cell Connect by Waveguide**, select exactly two non-array cell instances and press `6`. Both need PinRec ports. The tool supports horizontal or vertical facing pairs: collinear pins create an internal `Waveguide`, while lateral offset creates an editable `S_Bend`. It is not an arbitrary-angle or obstacle-avoiding router; inspect widths and clearances after generation.

For **Snap components**, select the moving objects, hover over an unselected reference object, and press `7`. Facing PinRec ports determine the translation. The whole selected group moves without rotation or mirroring, and no connecting waveguide is added. Successful snapping is silent and requires a valid transient selection under the cursor.

### Layout Utilities

For **Make Pins for Cell**, enter the target cell and choose its port sides. Inspect the generated pin positions, widths, directions, and DevRec. For **Numerical text array**, set numbering, direction, layer, spacing, and magnification, then place the array. Labels remain `Basic.TEXT` instances; spacing is between their bounding-box centers.

Use **Layer Exclude** on a copy. It prefers a cell named `TOP` when present, otherwise the active cell. Checked layers are retained; unchecked layers are deleted from the entire current layout. Optional operations remove other cells, merge shapes, or convert Si Paths to polygons. The tool does not save GDS automatically: inspect and save a separate output.

### DRC and Troubleshooting

Enter the cell to check, open `DRC → JNU_MWP_DRC`, edit and save rules in Macro Development, then return to the layout and choose `DRC → Run JNU_MWP_DRC`. Results appear in Marker Browser. The scope is the active cell and its descendants, not the visible viewport. Unsaved rule edits are not used by the run menu. Preserve customized rules before pulling updates.

`Si (1/0)` contains physical waveguide shapes, `PinRec (1/10)` stores directional ports, `DevRec (68/0)` identifies device regions, and `Text (10/0)` contains annotations. `Waveguide (1/99)` is normally hidden and serves input guides and legacy recovery.

- Missing menus or libraries: check the installation junction, duplicate old loaders or technology copies, and Macro Development errors, then restart.
- Missing fixed whitebox devices: obtain authorized GDS separately; PCells and bundled blackboxes remain available without it.
- Read-only parameters: edit their source inputs; automatic bend sampling is not a manual field.
- Failed connections: check instance selection, facing PinRec directions, and available routing space.
- Lost recovery after reopening GDS: confirm the PDK loaded and that PCell/recovery data was not removed by flattening or another tool.
- Stale code after updates: use Reload for Python changes and restart for startup macros, technology, or path changes.

A clean DRC report is not a fabrication guarantee. Verify the intended process, enabled rules, layer mapping, device geometry, and optical design requirements before delivery.

### Installation and Maintenance

Follow the [README installation instructions](../README.md#git-clone-installation-windows). Query KLayout's actual user directory before running the installer. The executable, user directory, and source clone may be on different drives; the executable directory is not the PDK installation target.

For updates, follow [Updates and Whitebox GDS](../README.md#updates-and-whitebox-gds). Run `git pull --ff-only origin main` on the installed clone's `main` branch, preserving local changes and private GDS. Use `Reload JNU PDK` for Python-only changes; restart KLayout for startup macros, technology, or installation-path changes. Select the `JNU_MWP_PDK` technology and check the menus, libraries, and layers.
