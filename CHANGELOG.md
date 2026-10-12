<p align="right">
  <a href="CHANGELOG.md"><img src="docs/assets/readme/lang-zh-active.svg" alt="简体中文（当前）" height="30"></a>
  <a href="CHANGELOG.en.md"><img src="docs/assets/readme/lang-en.svg" alt="English" height="30"></a>
</p>

# 更新说明

[返回 README](README.md) · [完整提交记录](https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK/commits/JNU_MWP_PDK_V1.4/)

按更新日期倒序排列。历史日期采用 Git 提交日期（北京时间，UTC+8），同一天的相关改动合并说明；完整提交记录可查看每一次提交的内容与时间。

## 2026-10-12 · V1.4 开发分支

- V1.3 同步最新 `main`，包含双波段 TE 端面耦合器黑盒的居中修正；开发分支更名为 `JNU_MWP_PDK_V1.4`。
- 中文、英文 README 新增更新说明入口；新增中英文更新历史页面，可切换语言并查看更新日期。
- README 与器件库功能框中的固定器件数量同步为 31 个。

## 2026-10-10 · v1.3 器件库与波导修复

- 修复 `Pcell_Waveguide_Bump` 两端短直段被简化的问题：直接生成圆弧内外边界，两端保留 20 nm 恒宽直段，端面与 PinRec 中心对齐，直弯相切。
- 限制 bump 最大角度为 149°，避免圆弧折回端口；超过可实现的增量长度时，由只读参数显示实际值。
- 固定黑盒同步至 31 个：新增 `1310_4×4_MMI`、`1550_3.2um-MFD_TE_edge_coupler`，双波段端面耦合器更新为 `1550_1310_3.2um-MFD_TE_edge_coupler`。
- 白盒与黑盒库的显示版本更新为 v1.3，稳定注册名继续使用 `JNULib` 和 `JNULib_BlackBox`。
- 修正双波段 TE 端面耦合器黑盒的居中位置。

## 2026-10-08 · 快捷键回调与旧版版图迁移

- 修复安装路径含单引号时菜单 Python 回调的语法错误，使菜单操作与快捷键可正常触发。
- 新增旧版 `JNULib` PCell 引用迁移工具，用于修复旧名称导致的 `<defunct>`；迁移保留备份。

## 2026-10-01 · 器件、波导恢复与安装维护

- 修复复制 Waveguide PCell 后保存重开时变成裸名 `Waveguide` 的问题，完善 GUI 打开版图时的 PCell 恢复。
- 放大 Path to Waveguide 参数界面字体，并接入简体中文界面翻译。
- 加入 `Crossing4`、`1310_TE_Terminator`、`1550_TE_Terminator`、`1310_Ybranch`、`1550_Ybranch`，以及可编辑的 `Pcell_Waveguide_Bump`。
- 固定白盒统一放入 `pymacros/JNU_MWP_gds`，规范源迁至独立授权器件库；公开 PDK 不携带固定白盒 GDS。
- 所有 PCell 从固定黑盒库中移除，黑盒库只提供固定器件占位与端口。
- `main` 安装版在 KLayout 启动时检查更新，可点击更新提示完成更新；开发分支不提示，网络不可用时跳过。
- README 加入校徽、语言切换与功能框图；详细功能说明迁至独立使用说明页面，安装教程与 AI 提示词集中展示。

## 2026-09-30 · PCell 命名与界面语言

- 公开 `JNULib` 参数化器件统一增加 `Pcell_` 名称前缀。
- 新增 English / 简体中文选择，默认 English；菜单与 PCell 参数标签随语言切换，重启后生效。
- 白盒、黑盒库显示版本更新为 v1.2，库注册名保持稳定。
- 开始修复复制 Waveguide PCell 后参数化名称丢失的问题。

## 2026-09-29 · 默认快捷键

- 安装时自动绑定并保存 JNU 功能默认快捷键。
- 对旧版空白快捷键配置进行一次性迁移。

## 2026-09-28 · 波导转换与直接下载

- Path to Waveguide 支持任意图层上的 Manhattan Path；Waveguide to Path 统一恢复为 Si `1/0` 图层 Path。
- 根据独立器件库更新同步固定黑盒。
- README 安装宏链接改为直接下载 `.lym` 文件。

## 2026-09-24 · 端口与安装器

- PinRec 短路径统一为实际 20 nm，正确处理旋转实例的全局端口方向。
- 新增可拖入 KLayout 的安装宏，以及安装、检查更新和白盒库更新菜单。

## 2026-09-21 · 安装路径与端口边界

- 移除重复 Technology 目录，统一通过包内技术配置安装。
- 完善跨盘安装与安装目标预览。
- Make Pins for Cell 从器件物理边界生成端口，避免使用 DevRec 边界造成端口偏移。
- 加入可点击的中英文功能框图与对应使用说明链接。

## 2026-09-20 · 公开安装与固定黑盒

- 使 PDK 安装路径可搬运，采用 Git 克隆与目录联接安装。
- 随公开仓库提供固定黑盒；固定白盒通过独立授权安装。
- 加入 AI 安装与更新提示词、功能概览、中英文使用说明及问题反馈入口。
- 说明本机白盒目录与公开仓库的分发边界。

## 2026-09-03 · 器件连接与维护

- 更新菜单、DRC 与热重载流程，加入 Cell Connect by Waveguide 连接功能。
- 增加项目 MIT 许可说明。

## 2026-08-03 · 波导、螺旋与 DRC

- 改进波导恢复、螺旋端口几何、DRC 原生编辑与执行、热重载流程。
- 完善公共弯曲几何及相关回归检查。

## 2026-07-27 · 初始公开版本

- 导入 JNU MWP SOI PDK 源码与技术配置。
- 加入中文、英文 README。
