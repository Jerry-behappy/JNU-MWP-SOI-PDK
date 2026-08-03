---
name: klayout-sip-skill
description: Design, inspect, edit, repair, annotate, route, analyze, and verify silicon-photonic layouts in KLayout, including GDS/OASIS hierarchy, PCell and fixed-library instances, waveguides, spirals, ports, grating couplers, Basic.Text labels, marker-layer selections, geometry extraction, and safe in-place or copy-on-write GDS modification. Use for silicon-photonic layout drawing and post-processing tasks without modifying the underlying PDK source, library registration, technology files, packaging, or implementation.
---

# KLayout SiP Skill

处理 KLayout 硅光版图的设计、修改、修复、分析和验收。版图任务默认不修改 PDK 源码；只有用户明确要求修改 PCell 实现、库注册、技术文件或发布包时，才进入 PDK 开发流程。

## 职责边界

- 将 GDS/OASIS、版图层级、器件实例、端口、波导和标注视为操作对象。
- 对版图绘制和修改，使用本 skill 的通用版图约定；不要将普通版图任务扩展为 PDK 开发。
- 不因版图中出现失效实例就修改 PDK 源码；先尝试恢复库关联或替换实例。
- PDK 源码、库注册、技术文件和发布包不属于本 skill 的默认修改范围，除非用户明确点名。
- 不把具体项目文件名、截图颜色、临时坐标或某次实例数量写成通用规则。

## 强制工作流

1. 明确输入文件、输出策略、目标对象和必须保持不变的内容。默认另存；只有用户明确要求时才原位覆盖。
2. 使用安装完整库环境的 D:\KLayout\klayout_app.exe -b -r 读取版图。独立 Python pya 只能辅助检查，不能单独证明 PCell 或 library 关联有效。
3. 检查 dbu、顶层、层列表、cell 层级、PCell/library 状态、实例变换、端口和圈选标记。可先运行 scripts/inspect_layout.py。
4. 构造显式目标集合，并在写入前验证数量、名称、参数或几何特征。目标不明确时停止，不做范围外猜测。
5. 记录不变量：非目标实例多重集合、关键层几何、父级关系、阵列参数、顶层 bbox、端口和原文件哈希。
6. 用任务脚本实施修改。新增 Python 文件运行 py_compile。
7. 先写同目录临时 GDS，再用 KLayout 重新读取并验证；通过后才另存或用 os.replace 原位替换。失败时删除临时文件并保留原文件。
8. 报告目标数量、实际映射、输出路径、保留项和重读结果，不把非致命 GDS 警告冒充成功验证。

## 按需读取

- 处理库、层、PCell、端口、工作目录和版图使用约定时，读取 [references/layout-conventions.md](references/layout-conventions.md)。
- 执行实例替换、波导绘制、spiral 绘制、文字编辑、器件放置、端口连接、标注排序或曲率分析时，读取 [references/editing-workflows.md](references/editing-workflows.md)。
- 使用 marker layer、递归层级、阵列、重复实例或几何模式识别目标时，读取 [references/selection-and-hierarchy.md](references/selection-and-hierarchy.md)。
- 设计验证、哈希、不变量和原位覆盖流程时，读取 [references/verification.md](references/verification.md)。

## 工具入口

通用检查命令：

~~~powershell
& 'D:\KLayout\klayout_app.exe' -b -r '<skill>\scripts\inspect_layout.py' -rd input_file='<layout.gds>' -rd marker_layer='290/0'
~~~

修改本 skill 后运行：

~~~powershell
python scripts/sync_skill_links.py sync
python scripts/sync_skill_links.py check
~~~
