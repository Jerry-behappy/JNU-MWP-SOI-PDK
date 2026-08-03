# 硅光版图约定

## 环境与边界

- KLayout 主程序：D:\KLayout\klayout_app.exe。
- PDK、技术文件和版图库路径必须从当前 KLayout 环境中确认，不将本地路径写成跨项目规则。
- 使用库名、cell 名、PCell 参数和端口几何共同确认器件身份；不要依据截图或发行版本名推断。
- 本 skill 只操作版图和任务脚本。普通绘图、修图、实例替换、端口连接和 GDS 验证不应默认修改 PDK 源码。
- 只有用户明确要求修改 PCell 源码、库注册、技术文件或发布包时，才离开版图流程并进入 PDK 开发流程。

## 图层与单位

- 层号必须从当前技术和版图中核对，不根据截图颜色或其他项目的习惯推断。
- marker layer 是临时选择接口，常用 290/0，但任务脚本必须参数化，不把它当成工艺层。
- 所有坐标计算区分数据库单位和微米。先读取 layout.dbu，再做微米与 DBU 转换。

## PCell、固定 cell 与外部库

- 在完整 KLayout 环境中用 cell.is_pcell_variant()、cell.pcell_library() 和 cell.pcell_parameters_by_name() 判断 PCell。
- Basic.Text 是可编辑 PCell。优先修改 text、layer 等参数，不把文字重画成多边形。
- 新建文字优先使用 layout.create_cell("TEXT", "Basic", parameters)，再按生成 cell 的 bbox 对齐。
- 固定库器件通过明确的库名、cell 名和几何/端口验收重新关联；不要只凭相似 bbox 替换。
- 固定 GDS 器件应以当前有效库中的 cell 为目标恢复关联，不恢复或引用来源不明的旧顶层副本。
- 外部库的波导、逆向设计器件和其他内容默认保持不变，除非用户明确纳入目标。

## 绘图 PCell 约定

- Waveguide 与 Path to Waveguide 应创建真正的布局本地 Waveguide PCell variant；原始 Manhattan Path 由 TypeShape path 参数保存，并使用项目定义的属性作恢复后备。
- 新生成的 Waveguide 不向项目定义的原始路径层写入 Path，也不创建未经用户允许的 helper cell。
- Waveguide 的 DevRec 沿同一中心线生成，其净空和层规则必须从当前项目技术文件读取。
- Path to Waveguide 只转换原始 Manhattan Path；若选择集中混入已圆滑 Waveguide、S_Bend 内部 Path 或非 Manhattan Path，应跳过并汇总提示，不让整批转换失败。
- Waveguide、Bend 和 S_Bend 的默认参数由当前 PDK 或用户输入决定，不把某一工艺的数值写成跨项目默认值。
- 所有只读派生参数，如自动采样点数、总长度、差分长度，按 PCell 实际参数读取和验证，不在版图脚本中手动覆盖。

## 端口与实例

- 端口坐标和方向以实例变换后的 PinRec 路径、端口文字及实际 Si 截面共同确认。
- 实例变换必须同时考虑旋转、镜像、缩放、位移、阵列向量和父级变换。
- 共享 cell 的参数修改可能影响多个引用。修改前确认是改变实例的 PCell variant，还是改变共享 cell 几何。
- 删除旧 cell 前确认其引用数为零；不要为了清理名称而删除仍被非目标实例使用的 cell。

## 文件策略

- 默认保留原文件并另存语义清楚的新文件名。
- 用户明确要求原位修改时，仍先写同目录临时文件并重读，最后用原子替换覆盖原路径。
