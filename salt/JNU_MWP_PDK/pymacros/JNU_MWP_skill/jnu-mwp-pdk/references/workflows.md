# JNU_MWP_PDK Workflows

## Tool Code Organization

- `JNU_MWP_tools/` 根目录只保留包入口 `__init__.py`，不得把功能实现重新堆放到根目录。
- 可被 PCell、菜单动作和测试共同复用的纯计算、几何、图层及端口逻辑放入 `core/`；依赖当前 KLayout 视图、选择、弹窗或 Undo transaction 的交互功能放入 `actions/`；黑盒发布与复制检查放入 `release/`；所有 `verify_*.py` 放入 `tests/`。
- 新代码使用完整包路径导入，例如 `JNU_MWP_tools.core.common` 和 `JNU_MWP_tools.actions.path_to_waveguide`。根 `__init__.py` 中的旧模块别名只用于读取已有宏或用户脚本，不得作为新代码的导入方式，也不得为兼容性复制同名根文件。
- 移动工具模块时同步检查 `JNU_MWP_pcells/`、`JNU_MWP_PDK_Menu.lym`、`Keybindings/`、动态导入、回归脚本和发布复制清单；模块中按相对层级推导 `pymacros` 的代码也必须同步调整。
- 发布包只复制 `JNU_MWP_tools/__init__.py`、`core/` 和 `actions/`。`release/` 与 `tests/` 只存在于完整开发包中。
- 目录迁移完成后依次执行：旧扁平导入 `rg` 扫描、全工具与 PCell `py_compile`、新旧导入 smoke test、隐藏 KLayout 菜单加载、相关 GDS 回归；最后清理工具目录下生成的 `__pycache__`。

## Bend and Waveguide

- `corner_points()` 是唯一分发入口；三种点列均保持 `(0,0) -> (R,R)`，量化后首段 `(0,0)->(10,0)`、末段 `(R,R-10)->(R,R)` DBU。
- Euler 几何、路径检查、点数和长度使用 Reff。普通 radius 在 Euler GUI 中隐藏但不删除。
- Path to Waveguide 每个 Qt 信号只连接一个聚合刷新器；提交参数、派生显示、几何和名称使用同一计算结果。
- Path to Waveguide 的页签顺序为 `User-Defined`、`Single-Width Waveguide`、`Composite-Width Waveguide`，主窗口固定从 `1187 × 541 px` 内容区尺寸打开且不保存用户临时缩放。后两页使用 Editable/Calculated 双栏；`Editable Parameters`、`Calculated Parameters`、`Saved Types` 和 `Selected Parameters` 四个分组标题使用16 pt加粗，普通标签、输入框、页签、按钮和 Note 标题保持 KLayout 默认字体。Single 页 Bend Type 是首个可编辑字段，Composite 页 Bend Type 位于 Bend Radius 前。User-Defined 页按所选模式显示全部输入和派生参数，只有 Preset Name 可编辑；名称输入实时更新下拉项，并以500 ms防抖原子保存，名称非空、跨预设唯一且不改变稳定ID。`Save as User-Defined` 立即写入预设但不关闭窗口，成功后区分新建和已存在预设进行提示；主窗口 Cancel 不生成波导，但三个页签的全部有效设置、当前预设和当前页签仍会保存。生成逻辑按页签语义映射，禁止使用随页签顺序变化的硬编码索引。
- 除 Path to Waveguide 主窗口外，JNU 自定义参数窗口通过 `core/gui_state.py` 把每个窗口的实际宽高原子写入用户 `.klayout/jnu_gui_state.json`；OK、Cancel和标题栏关闭均保存，热重载或KLayout重启后恢复。Application配置只作为旧记录回退，不能作为唯一存储。
- 用户预设保存在 `jnu_waveguide_params.json` 的版本化 `user_defined` 结构中，只保存可编辑参数并在使用时重算派生值。稳定 ID 由模式和规范化参数生成；完全相同参数去重，同名不同参数追加 `_2/_3`。每个预设含独立多行 Note，Note不参与ID、名称和几何；使用500 ms单次定时器防抖保存，并在切换预设/页签、Manage、OK、Cancel及窗口关闭前强制原子写入。管理窗口以暂存列表执行多选删除，只有管理窗口 OK 才原子写入，Cancel 放弃删除。
- Waveguide PCell 与 Path to Waveguide 的 Si/DevRec 使用同一平滑中心线，并仅写入扫掠后的 Polygon；DevRec 总宽度等于 `wg_width + 2 µm`，确保 Si 两侧各保留 1 µm 净空。TypeShape `path` 与恢复属性继续保存可逆中心线数据，不作为可见图形输出。
- 公开 `JNULib` PCell 必须具有 `68/0` DevRec。普通器件以实际波导层 bbox 为基础，含外向 PinRec 的边不增加净空，其余边向外扩展 1 µm；bbox 只由器件层计算，不得被 PinRec 或 Text 拉大。当前 Microring、Archimedean Spiral、Paperclip Spiral 和 Composite Paperclip Spiral 共用 `core/devrec.py`，Bend、Taper、S-Bend 及内部两类 Waveguide 保留各自已有的 DevRec 几何。
- `Straight_Waveguide` 是公开水平直波导，默认 W=0.5 µm、L=50 µm；opt1/opt2 朝 180°/0°，左右 DevRec 与端面齐平，上下各扩 1 µm。
- 公开名称仅注册 `S_Bend`。Bezier 的 `B` 是水平归一化坐标：`P1=((1-B)L,0)`、`P2=(BL,H)`；输入值必须原样映射到 `P2.x/L`。独立PCell默认B=0.35；`SBend connect`初始参数固定为Bezier、B=0.3、R=30 µm。Si和DevRec为Polygon，1/99严格为空，只有PinRec保留Path。
- `Bend_90deg`、内部 `Waveguide`、`S_Bend`、两种 Paperclip 的实体波导必须为 Polygon；长 Paperclip 仍在安全直段分块，分块 Polygon 合并检查后不得断接。Composite Paperclip 在生成全部恒宽段、taper与弯曲段后执行小尺度闭合，消除 DBU 舍入缝隙，不得跨越设计 gap。
- `Taper.length` 只定义渐变段；`port1_extension_length`/`port2_extension_length` 默认0 µm并分别在渐变段前后增加 width1/width2 恒宽直段。opt1固定为x=0，opt2位于总长度末端；Si保持单一连续Polygon，DevRec覆盖总长度，PinRec宽度与端部局部宽度一致。
- Path to Waveguide复合模式把弯曲primitive设为bend width；起始端/终端下拉只能选择straight width或bend width。选择bend width时，起始端到第一个弯曲入口或最后一个弯曲出口到终端保持bend width，不再经过straight width；其他bend width到straight width的局部过渡完整放在直段，顺序为bend-width恒宽transition、taper、straight-width恒宽transition，其中transition默认2 µm、taper默认20 µm。opt1/opt2 PinRec分别使用端部实际宽度，Waveguide to Path恢复为straight width。路径容量按弯曲占用、端部taper和直/弯局部过渡共同检查；继续生成时每条Path统一降低到最大可行半径，Euler保持Rmax/Rmin比例。
- Path to Waveguide只转换原始Manhattan Path；选择集中若包含已圆滑Waveguide/S_Bend内部Path或其他非Manhattan Path，跳过并汇总提示，不影响同批有效Path继续转换。
- `Waveguide` 与 `Composite_Waveguide` 不进入公开 `JNULib`；`JNU_MWP_InternalWaveguideRegistry.lym` 以 early autorun 安装注册器，`pymacros/__init__.py` 和菜单 autorun 再作幂等安装。注册器必须覆盖已有视图、CellView 创建和文件打开前的视图同步，在每个用户 layout 中预注册同名本地 PCell 声明，确保用户在 GUI 重启后打开 GDS 时即可恢复 PCell 身份。Path to Waveguide 创建的 variant 直接实例化在原所属 cell 中，不新增中间容器。KLayout 禁止在活动 Undo transaction 中注册本地 PCell，也不允许本地 PCell 首次生产时向受 Undo 管理的只读 shape list 写入图形，因此声明注册和全部 variant 预生成都必须在 `LayoutView.transaction` 开始前完成；transaction 内只插入实例、写入实例恢复属性并删除输入 Path。若预生成或 transaction 失败，清理本轮新增且无父实例引用的 variant。原始 Manhattan Path 由 TypeShape `path` 参数保存；名为 `JNU_MWP_raw_manhattan_path` 的无图形属性提供后备，并以 GDS 数字实例属性镜像跨文件保存。新波导的 `1/99` 必须为空，不得创建 raw helper cell，也不得强制切换当前视图的图层显隐。反向转换依次读取 PCell 参数、恢复属性、旧版 cell 内 `1/99` 和旧版 helper；旧版容器和 helper 读取后删除，但不把 Path 写回 `1/99`。
- Cell 名称包含所有可编辑弯曲参数及 Rmax/Rmin/Reff，排除 Bend Points 和波导层；完全相同的局部路径与参数复用同一 variant，不同路径碰撞同一基础名称时按稳定签名追加 `__002`、`__003`，不得保留 `$N`。

## Interactive DRC

- `DRC → JNU_MWP_DRC` 直接打开 KLayout 原生 `Macro Development` 并定位到 `drc/JNU_MWP_DRC.lydrc`；使用原生保存功能持久化规则。规则文件只保留一个单参数 `report("标题")`，供原生绿色 Run 建立报告上下文；禁止 `source()` 和带报告路径的 `report()`。执行时选择 `DRC → Run JNU_MWP_DRC`，该动作会剥离单参数 report、注入临时输入与报告路径，只针对当前编辑 Cell 运行已保存代码。
- 点击 Run DRC 时，把当前内存 layout 写到临时 GDS，临时 DRC 宏显式调用 `source(path, active_cell)` 与 `report(title, temporary_lyrdb)`；其中 `active_cell` 是当前 GUI 正在编辑的 cell，DRC 只检查该 cell 及其子层级，不得按全局 top cell 扫描其他区域。规则注释、违规 output 描述和其 DSL 数值阈值必须一致。运行结束后将 `.lyrdb` 读入当前 LayoutView 的 Marker Browser，并清理所有临时文件。

## Runtime Reload

- `JNU_MWP_PDK → Reload JNU PDK` 在当前菜单回调退出后异步执行，避免重建菜单时销毁正在触发的 Action。待触发的单次 timer 只能由 `reload_pdk` 模块级引用保存，禁止写入或读取 `MainWindow` 的动态 Python 属性；重复触发必须合并为一次。
- 清除 `JNU_MWP_pcells`、`JNU_MWP_tools` 与 `JNULib` 模块缓存后从磁盘重新导入；同名公开库只保留一个，并调用 `Library.refresh()` 更新全部 client layout。
- 对已打开 layout 中现存的 `Waveguide` / `Composite_Waveguide` 以同名新声明调用 `register_pcell`，保持 PCell ID 不变，再调用 `Layout.refresh()` 重算已有 variant。
- 菜单宏注册必须幂等：删除全部已知 action item、替换主窗口持久 action 列表后再插入。重建前以稳定 action ID 保存当前 `pya.Action.shortcut`；若当前值已为空，则从 `Application.get_config("key-bindings")` 中相同完整菜单路径恢复，且不得改写用户配置。成功只写短暂状态栏消息，失败弹窗且不得删除用户布局对象。

## EBeam Library Visibility in JNU Technology

- EBeam 的标准库由 SiEPIC 加载器绑定到 `EBeam` Technology，因此不能只依赖原库在 `JNU_MWP_PDK` 的 Library 面板中显示。JNU 启动时调用 `core/ebeam_library_bridge.py`，为 JNU 额外注册 EBeam、EBeam_Beta、EBeam-Dream、EBeam-SiN、EBeam-ANT 五个同名 Library；它们读取 EBeam 安装目录中的既有 GDS 与 PCell，原 EBeam Library 保持不变。
- 桥接仅在 EBeam Technology、其安装根目录与 SiEPIC 加载器均存在时生效；缺少任何依赖时返回不可用状态而不影响 JNULib 注册。重复调用必须复用现有 JNU 绑定 Library，禁止重复注册或删除 EBeam 原库。

## Paperclip

- waypoint、inner-length 下限、type3 引出、采样、安全分段、几何、总长度和 delta_L 使用 effective radius。
- Euler 名称与 Text 写 `Reff/Rmax/Rmin`，不写隐藏的普通 `R`。
- `vertical_stretch` 不改变相邻波导 pitch；type3 保持边到边间距等于 gap，opt1 端口中心到第一个 90° Bend 起点固定为 10 nm。
- 分段只能发生在 DBU 舍入后严格水平/垂直且满足安全距离的直段。
- 20 nm PinRec 以 Si 端面为中心，内侧 10 nm 与 Si 重叠、外侧 10 nm 露出；端口主体与内侧 landing 合并，DRC 使用相交检查而不是完整包覆检查。

## Archimedean_Spiral

- 外侧采用固定 pitch 的双臂 Archimedean Spiral，中心 S 连接器独立使用四个 90° Bend 映射；禁止退化为 Paperclip 折线路径。type2 禁止 jog；type3 左臂继续生成 Archimedean 曲线直到竖直切线，再经外侧直段和一个底部公共 Bend 到达 opt2 等高位置。
- 中心 S 四个转角与 type3 底部输出转角都调用当前 PCell `bend_type`。五个转角都通过 `bend_90deg.corner_points()`，统一使用 effective radius；Euler 时为 Reff，普通 `min_radius` 在 GUI 中隐藏。
- `vertical_stretch` 增加中心 S 连接器的上下高度并同步扩大双臂内孔净空，不改变外侧双臂的 `wg_width + gap` pitch。
- type1 为同侧端口；type2 为异侧纵向错位端口；type3 为异侧且 y 坐标严格相同的端口。type3 外侧垂直段与主体边到边距离等于 gap。
- opt1 朝 180°，type1 opt2 朝 180°，type2/type3 opt2 朝 0°；所有端口在实际 Si draw segment 中保留至少 `wg_width` 长的严格水平 landing，并把最外侧 10 nm 保留为独立边。metric 点列从同一绘制几何合并生成，物理 Si 转 Region 后在 landing 内的截面中心不得偏移。
- Archimedean 端点通过解析切线求根与水平/竖直输出轴对齐；完整中心线按 4000 点上限、24 点重叠分块，Si 层 Region 合并后写入。合并后执行 `size(1).size(-1)` 闭合分块 DBU 舍入产生的 ≤1 DBU 缝隙，再插入 cell。
- `length` 是目标下限；自动选择最小完整圈数。`total_length`、`delta_L`、cell 名和 Text 使用 DBU 量化后的同一完整中心线结果。
- `points_per_90`、`turns`、`total_length` 和 `delta_L` 只读；GUI callback 与 coerce 共用 `calculate_spiral_geometry()`。

## Fixed GDS and Naming

### Public Package and Authorized GDS

- 推荐分发方式为公开 `JNU-MWP-SOI-PDK` Package，私有 `JNU-MWP-SOI-Library` 单独授权；不要修改后者的可见性。
- `release/package_lab_pdk.py --public --blackbox-source <已验证黑盒目录> --output <新目录>` 只复制运行时代码、公开 PCell、黑盒 GDS、相对路径技术文件和授权安装器，不携带 skill、测试、构建工具或白盒 GDS。
- 将构建结果同步到 Git 仓库的 `packages/`，`grain.xml` URL 指向 `packages/JNU_MWP_PDK[main]`。更新代码时提高版本号并同步重新生成包及 `packages/repository.xml`，再直接推送 main。
- 用户执行一次 `Enable_JNU_Packages.ps1` 配置包含官方源及既有自定义源的索引；不自动登记官方 Salt.Mine。后续使用 Manage Packages 更新公开代码。
- `Install_Private_GDS.ps1` 支持已授权下载并解压后的 `-Source` 目录，以及当前用户 `gh auth login` 后的私有仓库下载。只把 `.gds` 写入 `<KLayout home>/jnu_private/JNU_MWP_gds`，先验证输入再备份/替换；不将私有数据放回 Salt 管理目录。
- `core/fixed_gds.py` 先使用独立私有目录，缺失时兼容开发目录及完整离线包。公开代码更新/卸载不得删除独立 GDS；撤销远端授权不会删除本地已下载数据。
- 验证 `verify_lab_package_installation.py --public --package <构建结果> --klayout <exe> --private-gds-source <授权GDS>`；发布后加 `--index-url <真实公开索引>` 验证匿名 Salt 下载。还需测试 SiEPIC/EBeam 共存。禁止以本机已登录 GitHub 的克隆成功替代匿名 Package 安装验收。

### Optional Offline Laboratory Package

- 公开代码仓库为 `Jerry-behappy/JNU-MWP-SOI-PDK`，私有固定器件仓库为 `Jerry-behappy/JNU-MWP-SOI-Library`。运行时继续从安装包内 `pymacros/JNU_MWP_gds` 加载；独立器件仓库不直接作为未经认证的公共 Salt 依赖。
- 完整内部交付使用 `release/package_lab_pdk.py --gds-source <checkout/JNU_MWP_gds> --output <新目录> --zip`；源码、私有 GDS checkout、本机正在使用的 PDK 都不因构建而修改。GDS 数量以所选器件版本为准，不硬编码为本机开发目录数量。
- 交付使用 `grain.xml` 和 `JNU_MWP_PDK_Startup.lym`；接收方运行 `Open_Lab_Package_Manager.ps1` 生成本地 Salt 索引，再通过 Manage Packages 安装、更新和卸载。更新提高 grain 版本号，库名和 Technology 名保持稳定。
- 早期启动宏不能导入 `JNULib` 或 SiEPIC；公开库保留 `pymacros/__init__.py` 普通 autorun 入口，主窗口建立后才允许桥接 EBeam。SiEPIC 的 `_globals.Python_Env` 在首次导入时缓存，提前导入会跳过 `setup` 并导致 EBeam 宏菜单挂到错误位置。
- 用 `tests/verify_lab_package_installation.py --package <交付目录> --klayout <exe>` 验证实际 Salt 安装、无外部 tech、两次冷启动、菜单快捷键、全部固定器件和公开 PCell 几何；另传两个 `--peer-package`，分别指向已安装的 `siepic_tools` 和 `siepic_ebeam_pdk`，验证共存时环境为 GUI、EBeam DRC/示例宏位于 SiEPIC 子菜单。探针在事件循环和菜单挂载完成后执行，共存时创建 EBeam Technology 视图。仅有进程退出码不算通过，必须读取 probe 成功报告。测试在临时 KLAYOUT_HOME 中执行，不修改用户正在使用的安装。
- 完整包包含白盒器件和 PCell，仅内部发送；公开 GitHub 只提交代码、模板和说明。禁止交付 Git 元数据、账户凭据、维护 skill、测试工具、klayoutrc 或作者机器的绝对安装路径。

### Runtime Naming

- 固定白盒器件只从 `pymacros/JNU_MWP_gds/` 加载；该目录应包含 23 个 `.gds` 文件。不要创建顶层 `gds/` 镜像目录。
- 移动或清理固定 GDS 后，用 `rg` 检查 loader、打包脚本、README 和辅助脚本，确保不存在指向旧 `gds/` 的路径；同时验证 `JNULib.py` 仍指向 `pymacros/JNU_MWP_gds/`。
- 黑盒生成以 `pymacros/JNU_MWP_gds/` 为白盒输入，但发布包必须排除该目录和 `JNULib.py`。
- 文档可使用 `JNU_MWP_SOI_PDK` 展示名；代码、Technology、Salt、菜单、安装目录、skill 与黑盒包继续使用 `JNU_MWP_PDK`。
- 只有执行黑盒打包流程时，才同步修改 `pymacros/README.md` 和 PDK 使用说明；普通开发、维护和单独文档请求不改写这两类文档。若打包流程确需更新 `pymacros/README.md`，保持完整中文章节在前、完整英文章节在后。

## Numerical Text Array

- 以起始值、结束边界和非零整数步长生成最多 10000 个编号；递增使用正步长，递减使用负步长。
- 每个编号通过 `layout.create_cell("TEXT", "Basic", parameters)` 创建，`text`、`layer` 和 `mag` 直接使用用户参数；容器 Cell 只保存这些 PCell 实例。
- Horizontal 沿 `+X` 排列并对齐 bbox 中心 Y，Vertical 沿 `+Y` 排列并对齐 bbox 中心 X；相邻文字的实际 bbox 中心距等于用户 pitch，DBU 量化误差不超过 1 DBU，竖排文字自身不旋转，最终容器 bbox 左下角为 `(0,0)`。
- 生成后把容器 Cell 配置给 KLayout 原生 Instance 工具，由用户移动鼠标并单击放置；若原生动作不可用，保留 Cell 并提示手动放置。

## Snap Components

- `Snap components` 使用 KLayout transient selection：当前选中的全部对象是移动组，鼠标悬停命中的对象是固定参考。
- 端口从实例内部 `1/10` PinRec Path，或从直接选中的 `1/10` PinRec primitive path 的中心、点序方向和宽度识别；只有方向相差 180° 的光学端口可以匹配。
- 在固定参考与移动组全部可匹配端口中选择中心距离最近的一对，平移移动组全部对象使 moving pin 中心与 fixed pin 中心重合；不得旋转、镜像或修改实例参数。
- 空选择、无 transient selection、数组实例、移动组或参考对象无 PinRec、移动组包含参考对象或无相向端口时必须提示，不移动任何对象；polygon/path/text 等 primitive 混选不因类型本身报错。
- 成功吸附或最近相向端口已经重合时不得弹窗或写状态栏；只保留失败提示和成功移动后的版图刷新。

## Make Pins for Cell

- 选中的 cell instance 执行 `Make Pins for Cell` 后，器件 bbox 必须递归覆盖 Si、JNU SiN、EBeam SiN、Rib 和 M1。L/R/T/B 中被选择的边是光学端口边，DevRec 与该物理边严格对齐；其余边各向外扩 0.5 µm，再从端口边与器件 Region 的交叠段生成有方向 PinRec。
- 没有 DevRec 时插入新矩形；旧版工具留下的单一 Box 且不足本次边界时可替换为新矩形。已有 DevRec 包含 Text、Path、Polygon 或多个形状时视为自定义识别信息，保持不变。

## Verification

- 运行相关 Python 文件的 `py_compile`。
- 运行 `tests/verify_pcell_parameter_order.py`，确保全部注册 PCell 的设置面板先显示可编辑参数、末尾集中显示只读参数。
- 数值检查三种 Bend 的 10 DBU 端段和严格端口方向。
- 用 KLayout `-z -e` 隐藏 GUI 模式运行 `tests/verify_waveguide_devrec_regression.py`，检查公开 JNULib 不含内部 Waveguide PCell、完整 Path to Waveguide 的 transaction 时序，并检查 Circular/Bezier/Euler、0.5/2.0 µm 本地 PCell variant 的 TypeShape 参数、DevRec 双侧净空、新 cell 的空 `1/99`、GDS 属性恢复、旧版格式兼容、helper cell 数量和共享实例清理语义。
- 用 `tests/verify_composite_waveguide_regression.py` 检查复合宽度截面、taper、局部DevRec、半径降级、Euler缩放、端口、空1/99和GDS Path往返。
- 用 `tests/verify_path_to_waveguide_presets.py` 检查 User-Defined 首位、主窗口每次恢复为1187×541且不保存临时缩放、Bend Type 顺序、16 pt分组标题及普通控件默认字体、Preset Name实时重命名与稳定ID、其余参数只读、三个页签设置和当前页签持久化、schema迁移、原子写入、保存提示、Note独立性/防抖/关闭前保存、去重、批量删除，以及从首位 User-Defined 点击OK仍返回所选预设原始模式参数。
- 用 `tests/verify_gui_state_regression.py` 检查每个稳定窗口键的独立尺寸、JSON原子写入、默认尺寸回退以及真实QDialog重开后的宽高恢复。
- 用 `tests/verify_sbend_regression.py` 检查 `B=0.35/0.365` 的控制点直接映射、唯一公开名称 `S_Bend`、SBend connect 默认参数、Si/DevRec Polygon、空1/99、水平PinRec和GDS重读。
- 用 `tests/verify_taper_regression.py` 检查零延伸兼容、两端非零直段、连续Polygon、DevRec总长度、端口位置/宽度/方向、负长度规整和GDS重读。
- 用 `tests/verify_bend_regression.py` 检查三种 Bend 下的 Bend/Waveguide/Paperclip/Composite Paperclip 实体层无Path、PinRec仍为Path、长Paperclip安全分块连通及GDS重读。
- 用 `D:\KLayout\klayout_app.exe` 生成并重读 Bend、Waveguide、Archimedean_Spiral 和两种 Paperclip 的 GDS。
- 用 `tests/verify_spiral_regression.py` 覆盖三种 Bend × 三种端口及 7195.766 µm 长样例，并逐角检查中心四个转角和 type3 底部输出转角跟随设置，同时检查 type2 无 jog、type3 竖直切线/底部 Bend/y 对齐、宽度级水平 landing、最外侧 10 nm 边、2 µm 宽波导 GDS 截面 0°、分块重叠、Region 连通性、最小圈数和 GDS 重读。
- 用 `tests/verify_numerical_text_array_regression.py` 检查递增/递减/单值序列、数量上限、`Basic.TEXT` PCell 身份、Magnification、目标层、横纵中心距、原点归一化、唯一命名和 GDS 重读。
- 用 `tests/verify_snap_components_regression.py` 检查单实例、多实例移动组、primitive 混选、PinRec primitive、最近相向端口、同向端口拒绝、移动组包含参考对象拒绝和整体平移保持相对位置。
- 用 KLayout 批处理运行 `tests/verify_make_pins_for_cell_regression.py`，检查 L/R 与 T 端口的 0.5 µm 非端口净空、M1 纳入器件 bbox、PinRec 数量和旧版单一小 DevRec 的升级。
- 用 KLayout `-z -e` 运行 `tests/verify_drc_dialog_regression.py`，检查唯一 Technology DRC 文件、规则持久化、当前 Cell source 注入、临时宏 XML，以及原生编辑器的 current/active macro 同步与调试模式关闭。再运行 `tests/verify_drc_execution_regression.py`，用确定违规版图确认原生规则连续执行两次都能新增非空 Marker Database，并确认当前 Cell 菜单入口也能载入报告。
- 用 `tests/verify_public_pcell_devrec_regression.py` 审计全部公开 PCell 的 `68/0`，覆盖微环两种 drop 总线及三类 Spiral 的 type1/type2/type3，检查单一矩形边界、端口边/非端口边净空、Si 包含关系和 GDS 重读。
- 用 `tests/verify_straight_waveguide_regression.py` 检查默认 W/L、Si 尺寸、两个水平端口、PinRec 宽度、上下 1 µm DevRec、Text 和 GDS 重读。
- 用 `tests/verify_reload_pdk_regression.py` 连续重载三次，确认公开库不重复、Straight_Waveguide 保留、内部两类 Waveguide PCell ID 不变且已有 variant 完成重算。
- 用 KLayout `-z -e` 运行 `tests/verify_reload_pdk_gui_regression.py`，确认菜单宏和完整重载各重复三次后仍只有 9 个唯一 Action、单一 `JNULib`，并覆盖旧菜单首次升级、当前 Action 快捷键复制及已丢失快捷键从配置恢复。
- 用 KLayout 批处理运行 `tests/verify_ebeam_library_bridge_regression.py`，确认五个 EBeam Library 都已绑定到 `JNU_MWP_PDK`、包含 EBeam 器件数据、重复桥接不会创建重复库，并且无需改动原 EBeam Technology。
- 验收 GUI 实时派生值、三种命名及 `__002/__003` 冲突后缀；GDS 重读后名称和本地 PCell 身份必须保持。
- 生成黑盒包并检查禁止项；对 canonical skill 运行 UTF-8 `quick_validate.py`，再运行联接脚本 `check`。
- 检查固定 GDS 规范目录存在且包含 23 个文件，并确认顶层旧 `gds/` 目录不存在。
