<p align="right">
  <a href="README.md"><img src="docs/assets/readme/lang-zh-active.svg" alt="简体中文（当前）" height="30"></a>
  <a href="README.en.md"><img src="docs/assets/readme/lang-en.svg" alt="English" height="30"></a>
</p>

<p align="center"><img src="docs/assets/readme/jinan-university-logo.png" alt="暨南大学校徽与校名" width="340"></p>

# JNU-MWP-SOI-PDK

暨南大学光电混合集成实验室的 KLayout 硅光 PDK。安装后可使用 `JNU_MWP_PDK` 技术、`JNULib` 和 `JNULib_BlackBox` 器件库。

## 能做什么

- **参数化器件**：直波导、弯曲、S 弯、Taper、波导长度补偿、微环和螺旋延迟线。支持 Circular、Bezier、Euler 弯曲。
- **波导绘制与连接**：Path ⇄ Waveguide、单宽度／复合宽度波导、参数预设、器件端口自动连接与吸附。
- **版图辅助**：生成 PinRec／DevRec 端口与边界、编号文字阵列、图层筛选和当前 Cell 的 DRC 检查。
- **固定器件**：内置五个可查看结构的公开 EBeam 白盒；黑盒库提供器件占位、端口与名称，便于布局和连线。实验室私有白盒需单独授权。

<a id="克隆仓库安装windows"></a><a id="git-clone-installation-windows"></a>

## 安装（Windows）

首次安装需要 [Git](https://git-scm.com/downloads) 和 KLayout。

1. **[下载安装宏 Install_JNU_PDK.lym](https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK/releases/download/installer-macro/Install_JNU_PDK.lym)**。
2. 将 `.lym` 拖入平时使用的 KLayout，在 **Macro Development** 中选择 **Install JNU PDK**，点击绿色 **Run**，再点击 **安装**。
3. 等待完成并重启 KLayout，选择 `JNU_MWP_PDK` Technology。顶部会出现 `JNU_MWP_PDK` 功能菜单。

安装宏会读取当前 KLayout 的用户目录、克隆仓库并创建目录联接，无需查找程序目录或输入 PowerShell 命令。

<a id="更新与白盒-gds"></a><a id="updates-and-whitebox-gds"></a>

## 更新与白盒

在 `main` 版本上，每次启动 KLayout 会后台检查更新；若版本不同，可在弹窗中点击 **立即更新**。也可使用 **JNU_MWP_PDK → Check for PDK Updates**。开发分支和无法连接 GitHub 时不弹窗。更新完成后重启 KLayout。

获授权的实验室白盒可通过 **JNU_MWP_PDK → Install / Update Whitebox Library** 安装；公开仓库不包含这些私有 GDS。黑盒只有占位形状，不能作为最终流片的器件结构。

## 更多信息

[详细使用说明](docs/USER_GUIDE.md) · [问题反馈](https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK/issues) · [许可证](LICENSE.md)

本项目保留了原项目的 MIT 版权声明。五个公开 EBeam GDS 的来源与许可见 [白盒资源说明](salt/JNU_MWP_PDK/pymacros/JNU_MWP_gds/NOTICE.md)。
