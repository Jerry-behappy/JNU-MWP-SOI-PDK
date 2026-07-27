# JNU-MWP-SOI-PDK

## 中文说明

`JNU-MWP-SOI-PDK` 是暨南大学微波光子方向使用的 KLayout 光子 PDK 工程。当前仓库以开发源码形式发布，包含 `JNU_MWP_PDK` technology、KLayout 菜单、DRC、PCell、工具脚本和图层配置。

### 仓库内容

- `salt/JNU_MWP_PDK/`：KLayout salt 包主体，包含菜单、PCell、工具、DRC 和图层配置。
- `tech/JNU_MWP_PDK/`：KLayout technology 注册目录，用于让 KLayout 识别 `JNU_MWP_PDK` 技术。
- `salt/JNU_MWP_PDK/JNU_MWP_PDK.lyt`：salt 包内的 technology 配置。
- `tech/JNU_MWP_PDK/JNU_MWP_PDK.lyt`：用户 technology 目录中的 technology 配置。
- `salt/JNU_MWP_PDK/layers.lyp`：JNU PDK 图层显示配置。
- `salt/JNU_MWP_PDK/drc/JNU_MWP_DRC.lydrc`：JNU DRC 规则入口。
- `salt/JNU_MWP_PDK/pymacros/JNU_MWP_pcells/`：JNU PCell 源码。
- `salt/JNU_MWP_PDK/pymacros/JNU_MWP_tools/`：JNU 菜单功能和公共工具源码。
- `salt/JNU_MWP_PDK/pymacros/JNU_MWP_skill/`：项目内部维护用 skill，不用于黑盒发布包。

### 手动安装方式

将当前仓库内容复制到：

```text
C:\Users\<用户名>\KLayout
```

复制完成后，应满足以下目录结构：

```text
C:\Users\<用户名>\KLayout\salt\JNU_MWP_PDK
C:\Users\<用户名>\KLayout\tech\JNU_MWP_PDK
```

然后重启 KLayout，或在 Macro Development 中重新加载宏。正常加载后，KLayout 中应能看到：

- Technology：`JNU_MWP_PDK`
- 顶部功能菜单：`JNU_MWP_PDK`
- 器件库：`JNULib`、`JNULib_BlackBox`

### 重要说明

本仓库没有上传固定白盒器件 GDS 目录：

```text
salt/JNU_MWP_PDK/pymacros/JNU_MWP_gds/
```

该目录已在 `.gitignore` 中排除。因此，本仓库适合作为 PDK 源码、工具、PCell、菜单和 DRC 的开发发布目录。若需要向他人分发不包含白盒 GDS 的可安装黑盒 PDK，请使用项目中的黑盒打包流程生成独立发布包。

运行过程中生成的 `klayoutrc*`、`__pycache__`、`.pyc`、`.pyo`、日志文件等不会纳入版本控制。

---

## English Description

`JNU-MWP-SOI-PDK` is a KLayout photonic PDK project for Jinan University microwave photonics work. This repository is published as a source/development package and contains the `JNU_MWP_PDK` technology, KLayout menu integration, DRC, PCells, utility scripts, and layer configuration.

### Repository Contents

- `salt/JNU_MWP_PDK/`: main KLayout salt package, including menus, PCells, tools, DRC, and layer configuration.
- `tech/JNU_MWP_PDK/`: KLayout technology registration directory for the `JNU_MWP_PDK` technology.
- `salt/JNU_MWP_PDK/JNU_MWP_PDK.lyt`: technology configuration inside the salt package.
- `tech/JNU_MWP_PDK/JNU_MWP_PDK.lyt`: technology configuration under the user technology directory.
- `salt/JNU_MWP_PDK/layers.lyp`: JNU PDK layer display configuration.
- `salt/JNU_MWP_PDK/drc/JNU_MWP_DRC.lydrc`: JNU DRC entry script.
- `salt/JNU_MWP_PDK/pymacros/JNU_MWP_pcells/`: JNU PCell source code.
- `salt/JNU_MWP_PDK/pymacros/JNU_MWP_tools/`: JNU menu actions and shared utility code.
- `salt/JNU_MWP_PDK/pymacros/JNU_MWP_skill/`: internal project skill used for maintenance, not included in blackbox release packages.

### Manual Installation

Copy the contents of this repository to:

```text
C:\Users\<username>\KLayout
```

After copying, the directory structure should include:

```text
C:\Users\<username>\KLayout\salt\JNU_MWP_PDK
C:\Users\<username>\KLayout\tech\JNU_MWP_PDK
```

Then restart KLayout, or reload macros from Macro Development. After successful loading, KLayout should show:

- Technology: `JNU_MWP_PDK`
- Top-level menu: `JNU_MWP_PDK`
- Libraries: `JNULib`, `JNULib_BlackBox`

### Notes

The fixed whitebox GDS directory is intentionally not committed:

```text
salt/JNU_MWP_PDK/pymacros/JNU_MWP_gds/
```

This directory is excluded by `.gitignore`. Therefore, this repository is intended for PDK source code, tools, PCells, menus, and DRC development. To distribute an installable blackbox PDK without whitebox GDS files, use the project blackbox packaging workflow to generate a separate release package.

Generated files such as `klayoutrc*`, `__pycache__`, `.pyc`, `.pyo`, and log files are not tracked by version control.