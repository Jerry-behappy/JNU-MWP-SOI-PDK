# JNU_MWP_PDK Project Map

## Canonical Sources

- `pymacros/JNU_MWP_pcells/bend_90deg.py`: 90° Circular/Bezier/Euler 公共点列与 Bend PCell。
- `pymacros/JNU_MWP_pcells/waveguide.py`: Waveguide PCell、共享绘制函数、PCell path/无图形属性恢复数据和两侧各 1 µm 的 DevRec 净空规则；新几何不写入 1/99。
- `pymacros/JNU_MWP_pcells/composite_waveguide.py`: Composite_Waveguide PCell、起始端/直段/终端/弯曲宽度primitive、端部taper、直/弯transition和局部DevRec规则。
- `pymacros/JNU_MWP_pcells/Archimedean_spiral.py`: 双臂 Spiral、中心四个可配置 Bend、type3 外侧 Archimedean 引出 + 底部可配置输出 Bend、轴向切线求解、重叠分块/Region 合并、宽度级 0° 端口 landing、最外侧 10 nm 端段与长度派生 helper。
- `pymacros/JNU_MWP_pcells/paperclip_spiral.py`: 普通 Paperclip、effective-radius 与共享派生 helper。
- `pymacros/JNU_MWP_pcells/paperclip_spiral_composite.py`: Composite Paperclip。
- `pymacros/JNU_MWP_gds/`: 23 个固定白盒 GDS 的唯一规范目录；顶层旧 `gds/` 目录已删除，不得恢复或引用。
- `pymacros/JNULib.py`: 从 `pymacros/JNU_MWP_gds/` 注册稳定白盒库 `JNULib` 的固定器件与可直接放置 PCell；不公开注册工具内部 `Waveguide` / `Composite_Waveguide`。EBeam PDK 已加载时同时调用跨技术 Library 桥接，使 JNU 技术下可显示 EBeam 器件库。
- `pymacros/JNU_MWP_tools/core/`: 公共基础模块；`bend_sampling.py` 管理自适应采样，`bend_curvature.py` 管理 Bezier/Euler 曲率，`path_geometry.py` 把中心线扫掠结果规范化为 Polygon，`common.py` 管理图层/选择/上下文共享逻辑，`make_pin.py` 生成 SiEPIC 兼容端口，`devrec.py` 按端口边和非端口边净空规则生成公开 PCell 的矩形 DevRec，`gui_state.py` 按稳定窗口键原子保存并恢复自定义对话框尺寸，`ebeam_library_bridge.py` 为 JNU Technology 注册已安装 EBeam PDK 的同名 Library 视图。
- `pymacros/JNU_MWP_tools/actions/`: KLayout 菜单动作；包含 Path↔Waveguide、SBend connect、Make Pins、Layer Exclude、Numerical text array、Snap components 与交互式 DRC。`path_to_waveguide.py` 负责当前用户版图中的内部 Waveguide PCell 按需注册与 variant 创建；`make_pins_for_cell.py` 以端口边对齐、非端口边 0.5 µm 净空规则生成或升级普通 cell 的 DevRec 与 PinRec；`drc.py` 将九层 Source Specification、全局参数和按层勾选的 DSL 规则封装为临时 DRC 宏，并把报告载入当前视图。
- `pymacros/JNU_MWP_tools/release/package_blackbox_pdk.py`: 黑盒发布入口；发布包只复制工具包入口及 `core/actions`。
- `pymacros/JNU_MWP_tools/tests/`: 全部 `verify_*.py` 回归脚本，覆盖 Bend、Waveguide、Composite Waveguide、S-Bend、Spiral、Numerical text array、Snap components 和 PCell 参数顺序。
- `pymacros/JNU_MWP_pcells/s_bend_waveguide.py`: 公开 `S_Bend` PCell；Bezier B 直接映射为 `P2.x/L`，默认 B=0.35；Si/DevRec 为 Polygon 且不写入 1/99。
- `pymacros/JNU_MWP_pcells/taper.py`: 公开 Taper PCell；支持 Port 1/Port 2 恒宽直段延伸，中间渐变长度由 `length` 独立控制。
- `pymacros/JNU_MWP_pcells/straight_waveguide.py`: 公开 Straight_Waveguide PCell；生成水平直波导、两端 PinRec、Text 及固定 68/0 DevRec。
- `pymacros/JNU_MWP_tools/actions/sbend_connect.py`: 两实例端口自动连接；初始参数为Bezier、B=0.3、R=30 µm。
- `pymacros/JNU_MWP_tools/actions/reload_pdk.py`: 运行时重载入口；重建公开 JNULib、替换已打开 layout 的内部波导声明并刷新菜单。
- `pymacros/JNU_MWP_skill/jnu-mwp-pdk/`: Codex/Claude 共用的 canonical skill；上级 `JNU_MWP_skill` 整体不得进入黑盒包。

## Current Names and Layers

- Product/manual display name: `JNU_MWP_SOI_PDK`。
- Technology: `JNU_MWP_PDK`
- Salt/package/install directory/menu/skill engineering name: `JNU_MWP_PDK`
- White library: `JNULib`
- Blackbox library: `JNULib_BlackBox`
- Blackbox output directory: `JNU_MWP_PDK_blackbox_v1.1`
- Si `1/0`; PinRec `1/10`; input/legacy waveguide path `1/99`（默认隐藏）; DevRec `68/0`; Text `10/0`。

在用户明确启动整体迁移前，不要把工程内部名称改成 `JNU_MWP_SOI_PDK`。

## Documentation State

- `pymacros/README.md` 使用“完整中文在前、完整英文在后”的双语结构。
- 当前图文使用说明位于本地项目文档目录；文档展示名不改变工程内部标识。

## Blackbox Release

发布包只包含固定黑盒 GDS、黑盒 loader、菜单和运行所需工具。禁止包含白盒 GDS、PCell 源码、canonical skill 及 `klayoutrc*`。
