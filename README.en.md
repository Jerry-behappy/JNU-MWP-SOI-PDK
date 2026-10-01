<p align="right">
  <a href="README.md"><img src="docs/assets/readme/lang-zh.svg" alt="简体中文" height="30"></a>
  <a href="README.en.md"><img src="docs/assets/readme/lang-en-active.svg" alt="English (current)" height="30"></a>
</p>

<p align="center"><img src="docs/assets/readme/jinan-university-logo.png" alt="Jinan University logo" width="340"></p>

# JNU-MWP-SOI-PDK

A KLayout silicon photonics PDK from Jinan University's Optoelectronic Hybrid Integration Laboratory. It provides the `JNU_MWP_PDK` technology, parametric `JNULib`, fixed-device `JNULib_BlackBox`, waveguide tools, and DRC. The public repository works independently with nine PCell types and 30 fixed blackboxes; 29 fixed whitebox GDS files are available through a separately authorized library.

## Feature map

**Click a card to jump to its instructions on this page.**

<table>
  <tr><th colspan="2">JNU-MWP-SOI-PDK · Feature Map</th></tr>
  <tr>
    <td width="50%"><a href="#devices"><img src="docs/assets/features/devices-en.svg" width="520" alt="Libraries and PCells"></a></td>
    <td width="50%"><a href="#waveguides"><img src="docs/assets/features/waveguides-en.svg" width="520" alt="Waveguide design"></a></td>
  </tr>
  <tr>
    <td width="50%"><a href="#connections"><img src="docs/assets/features/connections-en.svg" width="520" alt="Connecting and aligning devices"></a></td>
    <td width="50%"><a href="#layout-tools"><img src="docs/assets/features/layout-en.svg" width="520" alt="Layout utilities"></a></td>
  </tr>
  <tr>
    <td width="50%"><a href="#drc"><img src="docs/assets/features/drc-en.svg" width="520" alt="Design rule checking"></a></td>
    <td width="50%"><a href="#installation"><img src="docs/assets/features/setup-en.svg" width="520" alt="Installation and maintenance"></a></td>
  </tr>
</table>

<a id="devices"></a>
## 01 · Libraries and parametric design

1. Select the `JNU_MWP_PDK` technology in KLayout. Open `JNULib` with the **Instance** tool, choose a PCell, and set its parameters. Placed instances remain editable through their properties.
2. The nine PCell types cover straight guides, 90° bends, S-bends, tapers, double-bus microrings, Archimedean spirals, standard and composite-width Paperclip spirals, and a four-arc waveguide bump. `Pcell_Waveguide_Bump` lets you edit extra length, width, effective radius, and maximum angle.
3. `JNULib_BlackBox` supplies footprints and PinRec ports for 30 fixed devices. Installing the separately authorized library adds their whitebox geometry to `JNULib`. A blackbox footprint is unsuitable as final fabrication geometry.

<a id="waveguides"></a>
## 02 · Waveguide design

1. Draw a Manhattan Path with horizontal and vertical segments on any layer. Select it and press **`9`**, or choose **JNU_MWP_PDK → Waveguides → Path to Waveguide**.
2. Choose single-width, composite-width, or a saved User-Defined preset. Set Circular, Bezier, or Euler bends, radius, and widths. Review the calculated values and click **OK**. A successful conversion replaces the input Path with an editable waveguide PCell.
3. To change the route, select the waveguide and press **`8`** (**Waveguide to Path**). This restores a Path on Si `1/0`; edit it and press `9` again. **Save as User-Defined** stores settings and Notes. Non-Manhattan paths are skipped, and insufficient bend space is reported.

<a id="connections"></a>
## 03 · Connection and alignment

- **Cell Connect by Waveguide (`6`):** select exactly two device instances with facing PinRec ports. The tool chooses the nearest eligible pair and creates a waveguide for collinear ports or an editable S-bend for lateral offset. Check spacing and bend clearance afterward.
- **Snap components (`7`):** select the objects to move, hover over an unselected reference device, then press `7`. The selected group translates to align facing ports without rotation, mirroring, or an added waveguide.

<a id="layout-tools"></a>
## 04 · Layout utilities

- **Layout → Make Pins for Cell:** enter the target cell and choose its left, right, top, or bottom port sides. The tool adds PinRec and creates DevRec when missing. Inspect pin positions and directions.
- **Layout → Numerical text array:** set the number range, step, orientation, layer, spacing, and text size, then place the result with the mouse. Labels remain editable `Basic.TEXT` instances.
- **Layout → Layer Exclude:** save a layout copy first. Check the layers to **keep**; optionally flatten, merge shapes, or remove other cells. The operation does not save GDS automatically, so inspect and save a separate result.

<a id="drc"></a>
## 05 · Design rule checking

1. Enter the cell to check. Open **JNU_MWP_PDK → DRC → JNU_MWP_DRC**, then edit and **save** the rules in KLayout's Macro Development editor.
2. Return to the layout and choose **DRC → Run JNU_MWP_DRC**. The run covers the active cell and its descendants.
3. Locate violations in **Marker Browser**, fix them, and rerun. The run menu does not use unsaved rule edits.

<a id="installation"></a>
<a id="git-clone-installation-windows"></a>
## 06 · Installation and maintenance

### Windows: install from KLayout

Install KLayout and [Git](https://git-scm.com/downloads) first.

1. **[Download Install_JNU_PDK.lym](https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK/releases/download/installer-macro/Install_JNU_PDK.lym)**.
2. Drop the `.lym` file into the KLayout you normally use. In **Macro Development**, select **Install JNU PDK**, click the green **Run** button, then **安装 (Install)**.
3. Restart KLayout, select the `JNU_MWP_PDK` technology, and confirm the top-level menu and both libraries appear.

The macro reads KLayout's actual user directory, clones `main`, and creates a directory junction; KLayout and the source clone may reside on different drives. **This download installs `main`. Use the AI prompt below to test the `JNU_MWP_PDK_V1.2` development branch shown on this page.**

### Install or update the development branch with an AI agent

Copy these prompts into an AI agent **that can access local files and run commands**. It should inspect the current installation and preserve other PDKs, private GDS, and local changes.

**Installation prompt**

> Install the `JNU_MWP_PDK_V1.2` branch of https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK in the KLayout I normally use. First determine KLayout's actual user directory and inspect any existing `salt/JNU_MWP_PDK` installation or Git clone. Preserve other PDKs, private whitebox GDS, and local changes. Install through a Git clone and directory junction, then restart and verify the `JNU_MWP_PDK` technology, `JNULib`, `JNULib_BlackBox`, and function menu.

**Update prompt**

> Update the JNU-MWP-SOI-PDK installed in my current KLayout. First locate the Git clone targeted by `salt/JNU_MWP_PDK` and identify its current branch. If it is `JNU_MWP_PDK_V1.2`, fast-forward only that branch. Do not force-reset, overwrite local changes, or delete private whitebox GDS. Verify the libraries and menu after updating, and tell me whether a restart is required.

<a id="updates-and-whitebox-gds"></a>
### Updates, language, and whiteboxes

- A `main` installation checks GitHub for updates at startup. Click **Update now** in the prompt or use **JNU_MWP_PDK → Check for PDK Updates**. Development branches do not show automatic update prompts. Restart KLayout after updating.
- Choose **JNU_MWP_PDK → Language → English / 简体中文** to change menu and PCell parameter labels; the change takes effect **after a restart**. **Reload JNU PDK** can reload Python tools, but changes to startup macros, technology, or installation paths still require a restart.
- Authorized users can choose **JNU_MWP_PDK → Install / Update Whitebox Library** to install 29 fixed whiteboxes from the separate [JNU-MWP-SOI-Library](https://github.com/Jerry-behappy/JNU-MWP-SOI-Library). This public PDK repository contains no whitebox GDS.

[Detailed user guide](docs/USER_GUIDE.md#english-user-guide) · [Report an issue](https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK/issues) · [License](LICENSE.md)
