<p align="right">
  <a href="README.md"><img src="docs/assets/readme/lang-zh.svg" alt="简体中文" height="30"></a>
  <a href="README.en.md"><img src="docs/assets/readme/lang-en-active.svg" alt="English (current)" height="30"></a>
</p>

<p align="center"><img src="docs/assets/readme/jinan-university-logo.png" alt="Jinan University logo" width="340"></p>

# JNU-MWP-SOI-PDK

A KLayout silicon photonics PDK from Jinan University's Optoelectronic Hybrid Integration Laboratory. It provides the `JNU_MWP_PDK` technology and the `JNULib` and `JNULib_BlackBox` libraries.

## What it does

- **Parametric devices:** straight waveguides, bends, S-bends, tapers, waveguide length compensation, microrings, and spiral delay lines, with Circular, Bezier, and Euler bends.
- **Waveguide design:** Path ⇄ Waveguide conversion, single-width and composite-width guides, saved parameter presets, automatic device connections, and port snapping.
- **Layout tools:** PinRec/DevRec generation, numbered text arrays, layer filtering, and DRC for the active cell.
- **Fixed devices:** the blackbox library provides footprints, ports, and names for 30 devices. All fixed whitebox GDS files are installed from the separately authorized device library.

## Installation (Windows)

Install [Git](https://git-scm.com/downloads) and KLayout first.

1. **[Download Install_JNU_PDK.lym](https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK/releases/download/installer-macro/Install_JNU_PDK.lym)**.
2. Drop the `.lym` file into your usual KLayout window. In **Macro Development**, select **Install JNU PDK**, click the green **Run** button, then **安装 (Install)**.
3. When installation finishes, restart KLayout and choose the `JNU_MWP_PDK` technology. The `JNU_MWP_PDK` menu will appear.

The macro finds the active KLayout user directory, clones the repository, and creates a directory junction. No executable-path lookup or PowerShell command is needed.

## Updates and whiteboxes

On `main`, KLayout checks for updates in the background at startup. If the installed revision differs, click **Update now** in the prompt. You can also use **JNU_MWP_PDK → Check for PDK Updates**. Development branches and GitHub connection failures are skipped silently. Restart KLayout after an update.

Use **JNU_MWP_PDK → Install / Update Whitebox Library** to install authorized whiteboxes from the separate [JNU-MWP-SOI-Library](https://github.com/Jerry-behappy/JNU-MWP-SOI-Library). This public PDK repository contains no whitebox GDS files. Blackboxes are placement and connectivity placeholders, not final fabrication geometry.

## More

[Detailed user guide](docs/USER_GUIDE.md#english-user-guide) · [Report an issue](https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK/issues) · [License](LICENSE.md)

See the [resource notice](salt/JNU_MWP_PDK/pymacros/JNU_MWP_blackbox_gds/NOTICE.md) for the provenance and MIT license of five EBeam-derived blackboxes.
