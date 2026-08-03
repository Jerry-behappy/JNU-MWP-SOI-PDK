# 版图设计与修改工作流

## 库实例恢复与替换

1. 分别统计失效 cell、有效 PCell、固定库 cell、引用数量和父级。
2. 建立显式映射：旧目标 → 库、PCell/cell 名、参数。参数不确定时从端口、文字、bbox 和相邻连接反推，并把推断写入验证条件。
3. 创建或取得新库 cell，保留原实例的父级、位移、旋转、镜像、缩放和阵列参数。
4. 核对替换前后端口、bbox 和连接关系；只删除已无引用的旧 cell。
5. 对未纳入目标的 Waveguide、spiral、inverse-design 和固定器件做不变量检查。

## Basic.Text 编辑与标注

- 修改已有文字时调用实例的 `change_pcell_parameter`，只改变用户指定参数。
- 换层时保持 `text`、`mag`、字体、间距、bias、实例变换和位置不变。
- “逆时针旋转一次”通常解释为实例角度 `+90°`；保持实例原点、缩放和镜像不变，并在报告中写明角度变化。
- 新建文字时先生成 PCell variant，再根据文字 bbox 中心与目标锚点计算实例位移。双位数和单数字符宽度不同，不使用固定左下角偏移代替居中。
- 同一数字可能出现多次，也可能有完全重叠实例。用实例多重集合验收，不用以数字或坐标为唯一键的字典吞掉重复项。
- `Numerical text array` 应生成普通容器 Cell，内部每个编号保持为 `Basic.TEXT` PCell 实例；字号直接映射 `Basic.Text.mag`，不得转成普通 `pya.Text` 或多边形。
- 编号阵列的 pitch 定义为相邻文字实际 bbox 中心距，横排对齐 bbox 中心 Y，竖排对齐 bbox 中心 X；DBU 量化误差不超过 1 DBU。

## 光栅与器件编号

1. 优先通过有效 cell 实例识别器件；若版图已扁平化，再使用重复几何、端口或局部 bbox 模式识别。
2. 把排序规则写成坐标规则，例如“X 递增，同 X 下 Y 递增”，不要仅写“按图片顺序”。
3. 若存在少量示范标签，把它们当作锚点验证排序和文字偏移；不把截图像素直接当作版图坐标。
4. 新增标签后验证器件数量、编号全集、每个标签的目标锚点、文字层和 PCell 参数。

## 波导绘制与转换

1. Path to Waveguide 只处理原始 Manhattan Path。遇到已圆滑的 `Waveguide`、`Waveguide_SBend`、S Bend 内部 Path 或非 Manhattan Path 时跳过，并在结果中列出跳过数量和原因。
2. 单宽波导创建布局本地 `Waveguide` PCell；复合宽度波导创建布局本地 `Composite_Waveguide` PCell。不要为“看起来像波导”的多边形伪造公开库身份。
3. 保留原始 Manhattan Path 的 PCell path 参数和恢复属性；新波导不向项目定义的原始路径层写入 Path，不创建未经用户允许的 helper cell，也不强行改变用户当前图层显隐。
4. 复合波导按直段容量放置 taper。若半径或直段不足，先列出问题线段；继续生成时每条 Path 使用统一最大可行半径，固定 taper 仍无法容纳的 Path 不转换。
5. 用户要求保留既有波导时，不重建任何 `Waveguide*` cell；只修改用户允许的器件、文字、连接器或实例变换。

## Bend、S Bend 与自动连接

- 90° Bend 的三种形状都应保持端口 `(0,0) -> (R,R)` 的语义；验证时关注端口位置、方向和 10 nm 端部 landing，而不是只看 bbox。
- S Bend Bezier 参数 `B` 直接表示 `P2.x/L`。不要把界面值替换成 `1-B`，也不要按端点欧氏距离二次缩放。
- `SBend connect` 用于两实例光口自动连接时，初始参数采用 Bezier、`B=0.3`、`R=30 µm`；连接后验证 PinRec 中心重合、方向相反和 Si 连续。

## 端口对齐与波导连接

1. 在全局坐标中求两个端口中心、方向和波导宽度。
2. 先选择允许移动的实例，再计算旋转/镜像和位移；不移动用户要求固定的器件。
3. 对齐后验证端口中心重合、方向相反、Si 截面连续且没有短缺或额外重叠。
4. 用户要求保留既有 Waveguide 时，不重建现有 Waveguide；只移动/旋转目标实例或添加明确允许的过渡段。
5. spiral、adapter 或蓝框器件连接后，同时检查 opt1/opt2、层级、PCell 参数和周围净空。

## Spiral 绘制与放置

- `Archimedean_Spiral` 是独立双臂 Archimedean 螺旋，不用 `Paperclip_Spiral` 代替；type1 为同侧端口，type2 为异侧错位端口，type3 为异侧等高端口。
- `Archimedean_Spiral.vertical_stretch` 拉伸中心 S 连接器并扩大内孔净空，外侧双臂 pitch 保持不变。type2 保留天然错位且不加 jog；type3 通过外侧引出和底部 Bend 实现等高。
- `Archimedean_Spiral` 的 opt1 朝 180°；type1 的 opt2 朝 180°，type2/type3 的 opt2 朝 0°。放置或连接时以 PinRec 和实际 Si landing 双重确认方向。
- `total_length` 和 `delta_L` 读取 PCell 根据 DBU 量化中心线计算的只读值；`delta_L = total_length - abs(opt2.x-opt1.x)`。
- Paperclip 或 Composite Paperclip 只能在严格水平/垂直且安全的直段分段；不要在弯曲段切分或用修改 metric 点列代替实际 Si 端口 landing。
- 宽波导 spiral 的端口处应保留至少 `wg_width` 长的严格水平 landing，并在端口外侧保留 10 nm 延伸，避免 PinRec 未被 Si 覆盖的假 DRC 问题。

## 曲率与弯曲半径分析

1. 从波导边界提取中心线；若已有原始 Path 或 PCell 路径，优先使用它而不是重新骨架化。
2. 按弧长重采样中心线，避免原始点密度影响数值导数。
3. 由一阶、二阶导数计算带符号曲率：`κ=(x'y''-y'x'')/(x'^2+y'^2)^(3/2)`。
4. 半径取 `R=1/|κ|`；近零曲率显示为无穷大或缺失值，不截成虚假的有限半径。
5. 只对采样噪声做有说明的平滑，并同时输出中心线、曲率-弧长和半径-弧长图。

## 失败处理

- 目标数量、编号全集、库关联或锚点验证不符合预期时立即停止写入。
- 将检查结果报告给用户；不要为了让脚本继续而放宽条件到可能修改非目标对象。
