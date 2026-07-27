# GDS 修改验证

## 验证阶段

1. **读取前**：记录输入绝对路径、大小、SHA-256 和修改时间。
2. **规划后**：验证目标数量、参数全集、父级和允许变化的字段。
3. **内存修改后**：立即检查每个目标的新状态及不变量。
4. **临时写出后**：用新的 `pya.Layout()` 在完整 KLayout 环境中重读临时 GDS。
5. **提交前**：确认输入哈希未被外部程序改变。
6. **提交后**：确认最终路径存在、哈希匹配临时成品且无遗留临时 GDS。

## 必查项目

- 顶层 cell、顶层实例数量和整体 bbox。
- 目标实例数量、PCell/library 身份、参数、端口、变换、阵列和父级。
- 非目标实例多重集合。
- 用户点名保护的 Waveguide、spiral、固定器件及其引用数量。
- marker layer 和其他保护层的几何。
- 输出能被 KLayout 成功重读；不能只依赖 `layout.write()` 无异常。

## 绘图专项验收

- Waveguide：确认是真正的布局本地 `Waveguide` 或 `Composite_Waveguide` PCell，`path` 参数可恢复原始 Manhattan Path，新生成 cell 的 `1/99` 为空，DevRec 相对 Si 中心线两侧各保留 `1 µm` 净空。
- Composite_Waveguide：检查起始端/终端实际宽度、弯曲宽度、taper 完整位于直段、局部 DevRec、半径降级和 GDS Path 往返。
- Bend/S Bend：检查端口坐标、方向、PinRec、Bezier `B` 的控制点语义和 GDS 重读；Euler 检查 Reff 相关参数而不是隐藏兼容 radius。
- Spiral：检查端口方向、端口处水平 landing、type2 无 jog、type3 等高、`vertical_stretch` 不改变外侧 pitch、`total_length`/`delta_L` 与重读后的只读值一致。
- Basic.Text/Numerical text array：确认每个编号仍是 `Basic.TEXT` PCell，`text`、`layer`、`mag`、bbox 中心距和容器层级符合预期。
- Snap/端口连接：确认只移动允许移动的一组实例，组内相对位置不变，目标端口中心重合且方向相差 180°。

## 实例签名

实例签名至少包含：

- PCell：library 名、声明/variant 参数。
- 静态 cell：cell 名或稳定几何哈希。
- `cplx_trans`、`na`、`nb`、`a`、`b`。
- 需要跨父级核对时加入父 cell 和实例路径。

对签名使用 `Counter`，保留重复实例语义。

## 几何哈希

- 对用户要求完全不变的 cell，按 layer/datatype、shape 类型和规范化几何计算哈希。
- 在同一 `dbu` 下比较整数坐标；不要先转浮点微米再比较。
- GDS 记录顺序可能变化，哈希前先排序规范化记录。
- 对超大 Polygon 的 record-length 警告可视为非致命，但必须确认输出重读成功且几何/实例验收通过。

## 原位覆盖

原位修改只允许以下顺序：

1. 在目标目录创建临时 GDS。
2. 写出并关闭。
3. 重新读取临时 GDS并完成全部验证。
4. 再次核对原文件 SHA-256。
5. 使用 `os.replace(temp_path, input_file)` 原子替换。
6. 在 `finally` 中删除失败留下的临时文件。

不要先覆盖原文件再验证，也不要在验证失败后把临时文件冒充结果交付。

## 交付报告

报告实际修改数量、映射/参数、输出路径、保护项、KLayout 重读结果和必要警告。若检测到重复实例、额外目标或用户并发保存，应明确说明并停止，不静默选择其中一部分。
