---
name: jnu-mwp-pdk
description: Use when developing, verifying, or packaging the JNU_MWP_PDK KLayout photonic PDK.
---

# JNU_MWP_PDK Skill

本目录是 Codex 与 Claude 共用的唯一规范源。用户目录中的 `jnu-mwp-pdk` 必须是指向本目录的 Windows 目录联接，不维护独立副本。

## Project Roots

- Workspace: `C:\Users\zjy\KLayout`
- PDK: `C:\Users\zjy\KLayout\salt\JNU_MWP_PDK`
- Canonical skill: `C:\Users\zjy\KLayout\salt\JNU_MWP_PDK\pymacros\JNU_MWP_skill\jnu-mwp-pdk`
- Fixed GDS source: `C:\Users\zjy\KLayout\salt\JNU_MWP_PDK\pymacros\JNU_MWP_gds`
- Blackbox output: `C:\Users\zjy\Desktop\JNU_MWP_PDK_blackbox_v1.1`

## Core Rules

- 新增或修改的代码注释使用中文，并保留现有 UTF-8 文件头。文件抬头的 `# 时间: YYYY-MM` 必须更新为修改时的年月份（例：`# 时间: 2026-07`），不允许沿用旧的创建月份。
- 代码注释描述几何、数据流和识别规则，不使用用户截图中的颜色/框选标记，也不以“参考某项目”代替实现原理；仅在说明真实兼容接口时保留外部工具名称。
- `bend_90deg.py` 是 Circular、Bezier、Euler 90° 弯曲点列的唯一规范源；其他模块只调用其公共 API。
- 公共 Bend 保持 `(0,0) -> (R,R)`，首末分别包含严格 10 nm 水平、垂直直段；`dbu=0.001 um` 时必须是 10 DBU。
- Euler 的实际几何半径统一取 `euler_Reff(Rmax,Rmin)`；隐藏的普通 radius 仅用于旧布局兼容。
- 所有 `points_per_90` / `npoints` 只读并自动计算；全部 PCell 必须先声明所有可编辑参数，再声明全部只读参数，确保设置面板的只读区位于最下方；只读参数名称以 ` [uneditable]` 结尾，浮点派生值显示三位小数。
- GUI callback 与 coerce/OK 校验必须共用纯计算 helper；编辑中的无效输入清空派生字段，仅提交时提示错误。
- `pymacros/JNU_MWP_tools` 按职责分为 `core/`（公共计算与端口）、`actions/`（菜单功能）、`release/`（发布工具）和 `tests/`（回归脚本）；根目录只保留包入口。PCell 文件确保 `pymacros` 位于 `sys.path`，并通过 `from JNU_MWP_tools.core.make_pin import make_pin` 导入端口生成函数。旧版 `JNU_MWP_tools.<module>` 导入仅由根 `__init__.py` 的运行时别名兼容，不恢复根目录重复文件。
- Layout 菜单的 `Numerical text array` 生成普通容器 Cell；每个编号必须保持为 `Basic.TEXT` PCell 实例，字号字段直接映射 `Basic.Text.mag`，不得转换为普通 `pya.Text` 或多边形；排列距离定义为相邻文字实际 bbox 的中心距，DBU 量化误差不超过 1 DBU。
- Layout 菜单的 `Snap components` 采用 transient selection 流程：当前选中的全部对象为移动组，鼠标悬停命中的对象为固定参考；不限制选中对象类型，只要选中集合和参考对象中能识别到 PinRec 光学端口即可，在双方全部端口中选择距离最近且方向相差 180° 的端口对，对移动组全部对象执行整体平移，不旋转、不镜像、不修改 PCell 参数。成功或端口已经重合时完全静默，仅失败时弹窗提示。
- `DRC → JNU_MWP_DRC` 必须先打开一次性按层设置窗口：左栏 `Layer Definitions` 固定显示九个中文层名，并在每行右侧提供可编辑 `Source Specification`；右栏先显示可编辑全局 DRC 参数，再以“`Rules to Check` 勾选框 + 不可编辑层名 + 可编辑完整 DRC DSL 参数”显示同样九层。Si、PinRec、M1、M2、DeepTrench 默认勾选，其他层默认规则为空且不勾选；勾选但规则为空必须拒绝执行。规则、图层和勾选状态每次打开均从源码默认值重置，禁止持久化；对话框尺寸仍按 `core/gui_state.py` 的通用规则保存。点击 `OK` 时把当前内存版图写入临时 GDS，以当前表单内容生成临时 `.lydrc` 并显式执行 source/report，再把临时 `.lyrdb` 载入当前 Marker Browser；临时 GDS、宏和报告随后删除，默认 `JNU_MWP_DRC.lydrc` 不得被改写。点击 `Cancel` 不执行 DRC。
- `pymacros/JNU_MWP_gds` 是 23 个固定白盒 GDS 的唯一规范目录；`JNULib.py` 只从该目录注册稳定白盒库 `JNULib`。库注册名属于 PCell 身份，白盒与黑盒必须分别固定为 `JNULib` 和 `JNULib_BlackBox`，不得将发行版本号写入库名或新生成器件的库身份；发行版本应写入 `Library.description`，使 Library 面板显示为“稳定库名 — vX.Y, 组件说明”，与 EBeam 的显示语义一致。旧的 `*_v1.x` 名称只用于载入时清理兼容。已删除的顶层 `gds` 目录是旧副本，不得重新创建或引用。
- EBeam PDK 已安装且已加载时，`JNULib` 启动阶段调用 `core/ebeam_library_bridge.py`，把 EBeam、EBeam_Beta、EBeam-Dream、EBeam-SiN、EBeam-ANT 以同名 Library 注册到 `JNU_MWP_PDK` Technology，使当前技术选择为 JNU 时 Library 面板仍可显示 EBeam 器件库。桥接必须复用已安装 EBeam 的 GDS、PCell 源码和版本说明；不得修改、删除或将原 `EBeam` Technology 的 Library 改绑为 JNU。EBeam 未安装或未加载时静默跳过，JNU PDK 仍应独立工作。
- Waveguide PCell 与 Path to Waveguide 共用 `draw_waveguide_geometry()`；Si 与 DevRec 都把中心线扫掠结果规范化为 Polygon，DevRec 总宽度为 `wg_width + 2 µm`，即 Si 两侧各保留 1 µm 器件识别净空。PCell TypeShape `path` 和恢复属性继续保存可编辑 Manhattan 中心线，但不得在物理层或 `1/99` 生成恢复 Path。
- Path to Waveguide 生成的 `Waveguide` / `Composite_Waveguide` 必须作为真实本地 PCell 直接实例化在原所属 cell 中，禁止新增 `__JNU_P2W_*` 中间容器。cell 名使用完整参数化显示名称；局部 Manhattan 路径与全部实际生效参数相同的波导复用同一 variant，不同路径产生同一基础名称时按稳定签名分配 `__002`、`__003` 后缀，禁止把 KLayout 自动生成的 `$N` 作为最终名称。输入路径以首点局部化并通过实例平移恢复原坐标。启动、创建 LayoutView/CellView 及热重载时必须预注册两个内部 PCell 声明，使 GDS 在解析前即可恢复真实 PCell 身份；二者仍不得进入公开 `JNULib` 器件列表。Waveguide to Path 继续兼容旧 `__JNU_P2W_*`、`JNU_WG_*`、`Waveguide$N` 与 `Composite_Waveguide$N`，但新生成数据不得写出这些结构或名称。
- `JNULib` 注册的每个公开 PCell 都必须生成 `68/0` DevRec。普通器件使用单一矩形识别边界：先取实际波导层 bbox，具有外向 PinRec 端口的边保持器件原边界，其他边在 Si 外增加 1 µm 净空；不得让 Text 或 PinRec 自身扩大器件 bbox。内部 `Waveguide` / `Composite_Waveguide` 继续按各自中心线和局部宽度规则生成 DevRec。
- `Make Pins for Cell` 对无 DevRec 的普通 cell 使用与 SiEPIC Component 转换一致的规则：由 Si、JNU SiN、EBeam SiN、Rib 与 M1 的递归器件 bbox 生成单一 `68/0` Box；选中的 L/R/T/B 端口边与物理器件边严格对齐，所有未选端口边外扩 0.5 µm。旧版工具写入的单一小 DevRec Box 在下一次执行时可安全升级；包含文字或其他形状的自定义 DevRec 不得覆盖。PinRec 始终在与选中端口对应的物理器件边生成。
- 公开 `Straight_Waveguide` 默认宽度 0.5 µm、长度 50 µm；沿 +X 生成单一 Si 矩形，opt1/opt2 分别朝 180°/0°，PinRec 宽度等于波导宽度。DevRec 左右端面与 Si 端面齐平，上下各扩展 1 µm，并固定写入 68/0。
- 公开 PCell 名称仅为 `S_Bend`，不得继续注册 `S_Bend_Waveguide` 别名。其 Bezier 参数 `B` 直接定义第二控制点的归一化水平坐标，必须满足 `P2.x=B*L`、`P1.x=(1-B)*L`，不得使用 `1-B` 作为界面实际值，也不得按端点欧氏距离再次缩放；独立PCell默认 `B=0.35`。`SBend connect` 固定以 Bezier、`B=0.3`、`R=30 µm` 创建初始PCell参数。S_Bend 的 Si 和 DevRec 只写 Polygon，`1/99` 保持为空，PinRec 保留有方向短 Path。
- 波导实体层统一使用 Polygon：`Bend_90deg`、内部 `Waveguide`、`S_Bend`、`Paperclip_Spiral` 与 `Paperclip_Spiral_with_Composite_Waveguide` 不得在 Si 或路径式 DevRec 图层写入 Path；PinRec 是方向识别载体，必须继续使用短 Path。Paperclip 长中心线仍只在安全直段分块，各块转换为 Polygon；Composite Paperclip 合并直段、taper 和弯曲 Polygon，并闭合 DBU 舍入产生的微小拼接缝。
- `Taper` 的 `length` 仅表示线性渐变段长度；`port1_extension_length` 和 `port2_extension_length` 默认为 0 µm且不得为负。opt1 固定在 x=0，几何依次为 width1 直段、渐变段、width2 直段，opt2 位于三段总长度末端；Si 是单一连续 Polygon，DevRec 覆盖完整长度，PinRec 随端部延伸移动。
- Path to Waveguide 支持单宽度与复合宽度两类生成模式。复合模式创建 `Composite_Waveguide`，默认直宽2 µm、起始端/终端下拉均选择直宽、弯宽0.5 µm、taper 20 µm、直/弯 transition 2 µm、Bezier B=0.3、R=30 µm；端部下拉只允许选择当前直宽或弯宽。端部PinRec分别使用起始端/终端实际宽度，Waveguide to Path恢复为直宽Path。选择弯宽的起始端到第一个弯曲入口、选择弯宽的最后一个弯曲出口到终端都保持弯宽；其余弯宽到直宽的局部过渡完全位于相邻直段，顺序为弯宽直段 transition → taper → 直宽直段 transition，保证taper两端曲率为0。DevRec按局部宽度两侧各扩1 µm。半径或直段长度不足时先列出问题线段并Yes/Cancel确认，继续后每条Path采用统一最大可行半径；固定 taper/transition 仍无法容纳的Path不得转换。
- Path to Waveguide GUI 的页签顺序为 `User-Defined`、`Single-Width Waveguide`、`Composite-Width Waveguide`。主窗口每次以 `1187 × 541 px` 内容区尺寸打开，用户临时缩放不得持久化。后两页左栏集中可编辑参数、右栏集中只读派生参数；`Editable Parameters`、`Calculated Parameters`、`Saved Types` 与 `Selected Parameters` 四个分组标题使用16 pt加粗，普通标签、输入框、页签、按钮和 `Note` 标题必须保持 KLayout 默认字体。Single 页 Bend Type 排在全部可编辑参数首位，Composite 页 Bend Type 排在 Bend Radius 前。`Save as User-Defined` 仅在原子写入成功后弹窗提示，新建与已存在预设使用不同说明。用户页通过下拉框选择预设，并显示与对应基础页一致的全部输入和派生数值；其中只有 Preset Name 可编辑，输入时下拉项必须实时同步，500 ms防抖原子保存，名称不能为空或与其他预设重复，重命名不得改变预设ID、参数、Note或几何。每个预设另有独立 Note，500 ms防抖自动保存并在切换、管理、OK、Cancel和关闭前强制写入，Note不参与ID、命名或几何。管理窗口只支持多选删除；重命名通过 Preset Name 完成。三个页签的全部有效设置、当前预设和当前页签都必须持久化，User-Defined 位于首位后生成分支必须按页签语义而非固定数字索引判断，避免误用 Single 页参数。预设 JSON 采用原子替换，旧版配置必须自动迁移。
- 除 Path to Waveguide 主窗口外，由 JNU 功能菜单创建且允许调整大小的参数对话框通过 `core/gui_state.py` 按稳定窗口键保存独立尺寸；尺寸原子写入用户 `.klayout/jnu_gui_state.json`，KLayout 配置项仅作兼容回退，并在 OK、Cancel 或标题栏关闭后保存，使热重载和重启后均能恢复。
- Path to Waveguide 只转换原始 Manhattan Path；若选择集中混入已圆滑 Waveguide/S_Bend 内部 Path 或其他非 Manhattan Path，必须跳过这些对象并汇总提示，不能让整批转换直接失败。
- `Waveguide` 与 `Composite_Waveguide` 是 Path to Waveguide 的工具内部 PCell，不得注册到公开 `JNULib`，避免出现在 KLayout `Instance → JNULib` 器件列表。Path to Waveguide 必须在当前用户版图中按需注册本地声明并创建真正的 PCell variant；本地声明注册和 variant 首次几何生产都必须在 `LayoutView.transaction` 开始前完成，transaction 内只插入实例、写入实例恢复属性并删除输入 Path。预生成失败时清理本轮新增且无父实例引用的 variant。TypeShape `path` 参数保存原始 Manhattan Path；同时保留名为 `JNU_MWP_raw_manhattan_path` 的无图形恢复属性，并以GDS数字实例属性镜像解决PCell展开写出时的属性丢失。新波导不得向 `1/99` 写入Path，也不得创建 `__JNU_RAW_PATH` helper cell；`1/99` 仅用于输入引导和旧版读取且在技术层属性中默认隐藏，转换动作不得改写用户当前视图的显隐状态。Waveguide to Path按PCell参数、恢复属性、旧版`1/99`、旧版helper的顺序读取，复合波导恢复Path宽度取直宽。
- 根菜单 `Reload JNU PDK` 通过清除 JNU Python 模块缓存、重新导入 `JNULib.py` 与 `JNULib_BlackBox.py` 并同名注册稳定库 `JNULib`、`JNULib_BlackBox` 实现无重启更新。两个公开库均调用 `Library.refresh()`；每个已打开 layout 中已注册的内部 `Waveguide` / `Composite_Waveguide` 必须以同名新声明替换后调用 `Layout.refresh()`。菜单宏重跑前先按稳定 action ID 保存当前快捷键，当前值为空时从 `Application.get_config("key-bindings")` 的稳定菜单路径恢复，再移除并重建 action item；重复重载不得产生重复菜单、失效回调或丢失用户快捷键。
- `Archimedean_Spiral` 是独立的双臂 Archimedean 螺旋，不得用 `Paperclip_Spiral` 代替；中心 S 连接器的四个转角都映射 `bend_90deg.corner_points()`，并全部跟随 PCell `bend_type`，统一使用当前 effective radius。
- `Archimedean_Spiral.vertical_stretch` 拉伸中心 S 连接器并同步扩大内孔净空，外侧双臂 pitch 保持不变；type1/type2/type3 分别为同侧、异侧错位、异侧等高端口。
- `Archimedean_Spiral.total_length` 和 `delta_L` 使用 DBU 量化后的完整中心线计算，`delta_L = total_length - abs(opt2.x-opt1.x)`。
- `Archimedean_Spiral` 的端口语义以 `Paperclip_Spiral` 为准：type2 保留天然错位且禁止 jog；type3 左臂继续生成 Archimedean 曲线直到切线严格竖直，随后走外侧直段，底部输出区域仅映射一个跟随 PCell `bend_type` 的公共 90° Bend，使两端口等高。
- `Archimedean_Spiral` 的 opt1 朝 180°，type1 opt2 朝 180°，type2/type3 opt2 朝 0°；所有端口必须在实际 Si `draw_segments` 中包含至少一个 `wg_width` 长的严格水平 landing，最外侧独立边保持 10 nm，确保宽波导转为 Polygon/Region 后端口物理角度仍为 0°，禁止只修改 metric 点列。
- `Archimedean_Spiral` 完整中心线按最多 4000 点、24 点重叠分块；物理 Si 层必须把分块 Path 转成 Region 后合并，合并后执行 `size(1).size(-1)` 闭合分块 DBU 舍入产生的 ≤1 DBU 缝隙，再插入 cell；raw path 层保留重叠 Path。
- Paperclip 仅在 DBU 坐标严格水平或垂直的安全直段分段，禁止在弯曲段分段。
- Paperclip `ports_type=type3` 的 opt1 端口中心到第一个 90° Bend 起点固定为 10 nm。
- Paperclip（含 Composite）Si 层在端口外侧增加 10 nm 延伸，确保 20 nm 长 PinRec 路径完全被 Si 覆盖，避免 DRC `PinRec.not_inside(LayerSi)` 误报。
- 修改 Bend 后必须回归 Waveguide、Path to Waveguide、Archimedean_Spiral、Paperclip 和 Composite Paperclip。
- 黑盒包不得包含 `JNU_MWP_skill`、`JNU_MWP_pcells`、`JNU_MWP_gds`、`JNULib.py`、`JNU_MWP_tools/release`、`JNU_MWP_tools/tests` 或 `klayoutrc*`；只携带工具包入口及 `core/actions` 运行时代码。
- `JNU_MWP_SOI_PDK` 当前仅作为产品文档展示名；Technology、Salt、菜单、安装目录、canonical skill 和黑盒发布包继续使用工程名 `JNU_MWP_PDK`，除非用户明确启动整体迁移。
- `pymacros/README.md` 先完整写完中文，再完整写英文；不要交错排列双语段落。
- 只有执行 `package_blackbox_pdk.py` 打包黑盒器件库时，才同步修改 `pymacros/README.md` 和 PDK 使用说明文档；普通代码开发、PCell/菜单/图层修改、规则更新、维护性脚本和单独文档请求都不得改写这两类文档。
- 涉及较为重要的 PDK 开发规则的更新或增加，才修改本 skill 的 `SKILL.md` 与 `references/`；个别 PCell 参数微调、单次回归脚本、一次性维护工具或与 PDK 主线无关的临时修缮，不进入 skill，避免噪声污染共享规范源。

## Workflow

1. 修改前阅读 `references/project-map.md` 和 `references/workflows.md`；不自动读取项目根 `JNU_PDK_CONTEXT_BACKUP.md`。
2. 用 `rg` / `Get-Content` 检查现状，用 `apply_patch` 做聚焦修改。
3. 对所有改动的 Python 文件运行 `py_compile`，再运行 KLayout 批处理和 GDS 重读验证。
4. 修改本 skill 后运行 `python scripts/sync_skill_links.py sync` 与 `check`。
5. `JNU_PDK_CONTEXT_BACKUP.md` 仅保留为历史记录，除非用户明确要求，否则不读取、不写入。
