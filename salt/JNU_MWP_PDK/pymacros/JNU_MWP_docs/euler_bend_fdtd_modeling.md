# JNU_MWP_PDK 欧拉弯曲 FDTD 建模资料

生成日期：2026-07-15  
适用对象：`Bend_90deg`、`Waveguide` 中的 90° Manhattan 圆角、使用公共 `corner_points()` 的 Spiral/Paperclip 局部 90° 弯曲。  
主要源码依据：

- `C:\Users\zjy\KLayout\salt\JNU_MWP_PDK\pymacros\JNU_MWP_pcells\bend_90deg.py`
- `C:\Users\zjy\KLayout\salt\JNU_MWP_PDK\pymacros\JNU_MWP_tools\core\bend_curvature.py`
- `C:\Users\zjy\KLayout\salt\JNU_MWP_PDK\pymacros\JNU_MWP_tools\core\bend_sampling.py`
- `C:\Users\zjy\KLayout\salt\JNU_MWP_PDK\d25\d25.lyd25`

## 1. 结论先行

JNU_MWP_PDK 的 Euler 90° 弯曲不是用 PCell 面板中的普通 `radius` 生成。选择 `bend_type = Euler` 时：

1. 用户输入 `Euler_Rmax` 和 `Euler_Rmin`。
2. PDK 数值积分得到 `Euler_Reff`。
3. 90° 弯曲局部中心线被放入 `(0, 0) -> (Euler_Reff, Euler_Reff)` 的弯曲盒。
4. 起点强制保留 10 nm 水平直段，终点强制保留 10 nm 垂直直段。
5. FDTD 最稳妥的几何来源是从 KLayout 导出的 Si 层 GDS/OASIS；如果要脚本重建，则应按本资料的中心线公式和宽度外扩生成波导实体。

默认 Euler 参数为：

| 参数 | 默认值 | 单位 | 说明 |
|---|---:|---|---|
| `Euler_Rmax` | 30.0 | µm | 弯曲端点最大曲率半径，曲率最小 |
| `Euler_Rmin` | 10.0 | µm | 弯曲中点最小曲率半径，曲率最大 |
| `Euler_Reff` | 约 14.555 | µm | 由数值积分得到的有效弯曲盒半径 |
| `PORT_STRAIGHT_UM` | 0.010 | µm | 端口强制直段长度，即 10 nm |
| `dbu` | 0.001 | µm | KLayout 数据库单位，1 nm |

## 2. 局部坐标和端口方向

标准 `Bend_90deg` 的局部中心线定义为：

- 起点：`(0, 0)`。
- 终点：`(Reff, Reff)`。
- 输入切线：沿 `+x`。
- 输出切线：沿 `+y`。
- PCell 端口语义：`opt1` 方向为 180°，`opt2` 方向为 90°。

如果在 FDTD 中只仿真一个独立 90° Euler bend，可以直接使用这个局部坐标。若嵌入实际电路，应优先从 GDS 导入最终 Si 多边形，因为 Waveguide、Paperclip、Archimedean_Spiral 会把局部 90° bend 旋转/镜像到全局路径中。

## 3. Euler 曲线数学模型

JNU_MWP_PDK 使用“两段 45° 对称拼接”的改进 Euler 曲线。第一段曲率沿弧长线性变化：

```text
kappa(s) = 1 / Rmax + s / A^2,  0 <= s <= L0
A^2 = L0 / (1 / Rmin - 1 / Rmax)
```

其中：

- `Rmax`：端点最大曲率半径。
- `Rmin`：中点最小曲率半径。
- `L0`：第一段 45° 曲线弧长。
- 第二段由第一段关于中点对称生成，使整体转角为 90°。

PDK 先估算总弧长，再迭代修正，使两段曲线总转角满足：

```text
integral(kappa ds) = pi / 2
```

第一段数值积分得到中点坐标 `(x_mid, y_mid)`，完整 90° Euler bend 的有效弯曲盒半径为：

```text
Euler_Reff = x_mid + y_mid
```

完整中心线终点为 `(Euler_Reff, Euler_Reff)`。

## 4. PDK 端口直段处理

`bend_90deg.py` 在生成 Circular/Bezier/Euler 点列后都会调用 `_with_port_straights()`，强制加入端口直段：

```text
起始直段: (0, 0) -> (0.010, 0)
末端直段: (Reff, Reff - 0.010) -> (Reff, Reff)
```

这两个 10 nm 直段的目的不是让 FDTD 有足够长的端口模式传播距离，而是保证 KLayout 中 PinRec/端口方向严格。FDTD 中仍建议在 bend 前后额外添加直波导引入段，例如 1-3 µm，便于端口模式展开和反射监测。

## 5. 几何层和工艺栈

版图几何层：

| 图层 | 含义 | FDTD 用途 |
|---|---|---|
| `1/0` | Si 波导实体 | 导入或重建为硅芯层 |
| `1/10` | PinRec | 只用于端口标记，不作为光学材料 |
| `68/0` | DevRec | 器件识别边界，不作为光学材料 |
| `1/99` | 输入/旧版中心线 Path | 只作恢复/调试，不作为最终光学几何 |

PDK 的 `d25/d25.lyd25` 给出了 2.5D 可视化栈，适合作为 FDTD 初始建模参考，但文件注释明确说明它主要用于可视化检查，不代表真实工艺形貌。若后续有 foundry 截面文件，应以工艺文件为准。

当前 2.5D 可视化栈：

| 区域 | z 范围 | 说明 |
|---|---:|---|
| BOX | -3 µm 到 0 | BOX 3 µm |
| 完整 Si | 0 到 220 nm | `LayerSi = 1/0` |
| rib/slab Si | 0 到 150 nm | `LayerSi_rib = 2/0`，浅刻蚀后剩余 150 nm |
| Si substrate | -13 µm 到 -3 µm | 衬底显示区域 |

FDTD 里常用的最小材料设置：

- Si core：使用仿真工具内置 crystalline Si 或工艺拟合色散模型。
- BOX / lower cladding：SiO2。
- upper cladding：若版图工艺为裸片可用 air；若有包层需改为 SiO2 或对应介质。
- 如果只仿真 `Bend_90deg` / 普通 strip waveguide，通常只需要 `1/0` 的 220 nm 全刻蚀硅层。

## 6. 从 PDK 参数到 FDTD 几何的推荐流程

### 流程 A：GDS 导入，推荐

1. 在 KLayout 中放置目标 PCell，例如 `Bend_90deg` 或含 Euler bend 的 Waveguide/Spiral。
2. 设置：
   - `bend_type = Euler`
   - `Euler_Rmax`
   - `Euler_Rmin`
   - `width`
3. 导出 GDS/OASIS。
4. 在 FDTD 中导入 GDS：
   - 只映射 `1/0` 为 Si 几何。
   - 不导入 `1/10`、`68/0`、`10/0` 作为材料。
   - 设定 z span：220 nm，z min = 0，z max = 220 nm。
5. 在输入/输出端外接直波导段和 mode port。

优点：完全保留 PDK 的 DBU 量化、Path 多边形化和实例变换。  
风险最低，适合最终提交仿真。

### 流程 B：中心线重建

如果 FDTD 环境更适合脚本生成，可以使用本目录附带脚本导出中心线：

```powershell
python C:\Users\zjy\KLayout\salt\JNU_MWP_PDK\pymacros\JNU_MWP_docs\export_euler_bend_points.py `
  --rmax 30 `
  --rmin 10 `
  --width 0.5 `
  --output C:\Users\zjy\Desktop\jnu_euler_bend_Rmax30_Rmin10.csv
```

CSV 中的 `x_um, y_um` 是中心线坐标。FDTD 中需要以 `width` 对中心线做等距外扩，或者按中心线采样点生成多段圆滑波导。若 FDTD 工具支持直接导入路径并指定宽度，建议保持单位为 µm。

## 7. FDTD 区域建议

以默认 `Rmax=30 µm, Rmin=10 µm, width=0.5 µm` 为例：

- Euler_Reff ≈ 14.555 µm。
- bend 盒尺寸约 `14.555 µm × 14.555 µm`。
- 建议在输入端 `-x` 方向、输出端 `+y` 方向各加 1-3 µm 直波导。
- FDTD x/y 边界到 Si 几何边缘建议留至少 1-2 µm 空隙；若 bend 损耗很低、泄漏场延伸较远，可增大到 3 µm。
- z 方向建议覆盖：上包层至少 1 µm，下方 BOX 至少 1-2 µm；若要看衬底泄漏，则包含完整 BOX 到衬底。
- 边界使用 PML。
- 端口使用 eigenmode / mode source，输入端选 TE0；输出端用 mode expansion monitor 统计 TE0 透射和高阶模式串扰。
- 网格：Si 边界附近使用 mesh override。220 nm SOI strip 波导常见横向/纵向网格在 10-20 nm 量级；若对 bend loss 的 0.01 dB 级差异敏感，需要收敛扫描。

## 8. 推荐输出指标

FDTD/EME 仿真建议至少输出：

| 指标 | 定义 |
|---|---|
| `S21_TE0` | 输入 TE0 到输出 TE0 的复振幅透射 |
| insertion loss | `-10 log10(|S21_TE0|^2)` |
| reflection | `10 log10(|S11_TE0|^2)` 或线性反射功率 |
| higher-order crosstalk | 输出端 TE1/TE2 等模式功率 |
| radiation loss | 输入功率 - 输出所有导模功率 - 反射导模功率 |
| phase | `arg(S21_TE0)`，用于后续紧凑模型 |

如果目标是电路级模型，应导出频率/波长扫宽内的 S 参数，例如 1500-1600 nm 或你项目指定 C-band 范围。

## 9. 与公开资料的对齐

JNU 的 Euler bend 设计思想与公开硅光/氮化硅文献中的“adiabatic bend / Euler bend 抑制模式相互作用”一致。可作为引用或仿真方法参考的公开资料：

- Jiang X., Wu H., Dai D., “Low-loss and low-crosstalk multimode waveguide bend on silicon,” Optics Express, 2018. PDK 源码在 `bend_curvature.py` 中把这篇作为 Euler 参考文献。
- Ansys Innovation Courses: [Bend Waveguide Analysis using Mode, FDTD, EME, and FEEM](https://innovationspace.ansys.com/product/bend-waveguide-analysis-using-mode-fdtd-eme-and-feem/)，用于弯曲波导仿真流程参考。
- Ansys Optics: [Bent Waveguide (FEEM)](https://optics.ansys.com/hc/en-us/articles/4409707153811-Bent-Waveguide-FEEM)，可参考弯曲模式、有效折射率和半径扫描思路。
- Ansys Optics: [Curved waveguide taper (varFDTD and FDTD)](https://optics.ansys.com/hc/en-us/articles/360042799713-Curved-waveguide-taper-varFDTD-and-FDTD)，可参考曲线器件中 mode expansion monitor 和 2.5D/3D 对比的组织方式。

## 10. 建模检查清单

提交 FDTD 前建议逐项检查：

1. `bend_type` 是否为 `Euler`。
2. `Euler_Rmax > Euler_Rmin > 0`。
3. 记录 `Euler_Reff`，不要把 GUI 中隐藏的普通 `radius` 当作 Euler bend 的真实盒半径。
4. GDS 导入时只把 `1/0` 映射为 Si。
5. 端口前后有足够直波导，不只依赖 PDK 的 10 nm 端口直段。
6. 输入/输出 port 截面远离 bend 曲率变化区。
7. 网格收敛至少做一次粗/细对比。
8. 同时保存几何参数、材料模型、网格、边界、端口模式编号和波长范围。
9. 如果结果要做紧凑模型，导出复数 S 参数而不仅是透射功率。

## 11. 当前源码注意事项

本资料按当前工作区源码生成。当前 `Archimedean_spiral.py` 中：

- `_CENTER_PCELL_BEND_CORNER_INDICES = frozenset((1, 2, 4, 5))`
- `_TYPE3_PCELL_BEND_CORNER_INDICES = frozenset((1,))`

也就是说，当前源码视角下，Archimedean_Spiral 的中心连接器四个 90° 转角和 type3 底部输出转角都会调用 PCell 的 `bend_type`。如果你的版图分支已经采用“只有指定蓝框转角跟随 PCell，其余固定 Circular”的规则，请以该分支的源码/GDS 导出结果为准，并相应更新本节。

