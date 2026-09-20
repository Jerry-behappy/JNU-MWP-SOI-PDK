# 完整实验室 Package 构建 / Laboratory Package Build

## 中文

代码来自 `Jerry-behappy/JNU-MWP-SOI-PDK`；固定 GDS 来自私有仓库
`Jerry-behappy/JNU-MWP-SOI-Library` 的 `JNU_MWP_gds/`。
发布者需要获得私有仓库访问权限，使用已登录的 GitHub CLI 或 Git 获取器件。
不要把令牌写入代码、`grain.xml` 或交付包，也不要把白盒 GDS 上传公开 PDK 仓库。

在本机开发目录或公开仓库根目录执行，输出目录须尚不存在：

```powershell
gh repo clone Jerry-behappy/JNU-MWP-SOI-Library C:\JNU-internal\JNU-MWP-SOI-Library
python salt\JNU_MWP_PDK\pymacros\JNU_MWP_tools\release\package_lab_pdk.py `
  --gds-source C:\JNU-internal\JNU-MWP-SOI-Library\JNU_MWP_gds `
  --output C:\JNU-internal\JNU_MWP_PDK_lab_package_v1.1.2 --zip
```

若已经 clone，先在器件仓库检查未提交修改，再按实验室流程更新。
脚本不修改本机正在使用的 GDS。省略 `--gds-source` 时使用当前 PDK 的本机 GDS。
公开仓库自身不带 GDS，因此从公开源码构建完整包时必须提供该参数。

交付物是完整目录及 ZIP，不是公开 GitHub Release。不要将其加入公开版本控制。
交付包含白盒固定器件、公开 PCell、黑盒库、菜单及 DRC；不含维护 skill、测试、
发布工具、用户配置或 Git 元数据。内部 ZIP 的安装方法见 `README_LAB_INSTALL.md`。
包启动宏显式注册 `.lyt`，不要求另复制 `tech`；原有手动安装应按安装说明先备份。

发布前使用真实 KLayout 检查安装和冷启动：

```powershell
python salt\JNU_MWP_PDK\pymacros\JNU_MWP_tools\tests\verify_lab_package_installation.py `
  --package C:\JNU-internal\JNU_MWP_PDK_lab_package_v1.1.2 `
  --klayout D:\KLayout\klayout_app.exe
```

检查使用临时 `KLAYOUT_HOME`，不会安装到发布者实际用户目录。它会在被检查的交付目录
生成本机索引；发放 ZIP 应由构建脚本先生成，避免把该临时本机索引发出。
后续发布须提高 PDK 根 `grain.xml` 中的版本号。器件库注册名保持 `JNULib` 和
`JNULib_BlackBox`，Technology 保持 `JNU_MWP_PDK`。

还应追加 `--peer-package <已安装的 siepic_tools 目录>` 与
`--peer-package <已安装的 siepic_ebeam_pdk 目录>`，运行 SiEPIC/EBeam 共存检查。
早期启动宏只注册技术和内部接口，公开库保留普通 autorun，不能提前导入 SiEPIC。

## English

The public PDK repository supplies the code. Obtain fixed GDS from the private
`Jerry-behappy/JNU-MWP-SOI-Library/JNU_MWP_gds` repository using an authorized
GitHub account. Never embed access tokens or upload whitebox GDS to the public
PDK repository. Use the commands above with an existing Python installation.

`--gds-source` selects a separate library checkout without modifying the active
development PDK. The output directory and ZIP must not already exist. Omitting
this argument uses the local PDK's GDS; public source checkouts do not contain it.

Distribute the complete ZIP internally, not as a public GitHub Release. Recipients
install with the provided local package-manager launcher and do not need GitHub
credentials. The package registers its Technology through an autorun macro, with
no external `tech` folder. Developer skills, tests and user configuration are excluded.

The verification command installs into an isolated temporary KLayout home and
checks two cold starts and generated PCell GDS. It prepares a machine-local index
in the tested folder, so distribute the clean ZIP generated before verification.
Increase the version in `grain.xml` for subsequent updates while preserving the
stable library and Technology names.
Also run with two `--peer-package` arguments pointing to installed `siepic_tools`
and `siepic_ebeam_pdk` folders to verify menu coexistence. Public libraries load
during normal autorun; early Technology registration must not import SiEPIC.
