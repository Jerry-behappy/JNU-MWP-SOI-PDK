<p align="right">
  <a href="CHANGELOG.md"><img src="docs/assets/readme/lang-zh.svg" alt="简体中文" height="30"></a>
  <a href="CHANGELOG.en.md"><img src="docs/assets/readme/lang-en-active.svg" alt="English (current)" height="30"></a>
</p>

# Changelog

[Back to README](README.en.md) · [Full commit history](https://github.com/Jerry-behappy/JNU-MWP-SOI-PDK/commits/JNU_MWP_PDK_V1.4/)

Updates are listed newest first. Historical dates follow Git commit dates in Beijing time (UTC+8). Related changes on the same day are grouped; the full commit history shows the content and timestamp of every commit.

## 2026-10-19 · Blackbox optical port straights

- Display BlackBox (998/0) with orange diagonal hatching so device labels remain visible. Migrate old solid or outline styles at startup, in new views and on reload, including views using EBeam technology.
- Fix the runtime library loader rebuilding new blackboxes as solid Si blocks. Load the generated GDS layers and hierarchy directly, and verify registered and placed cells against the on-disk geometry.
- All 31 fixed blackboxes now retain a 0.2 µm constant-width Si straight at each optical port. PinRec stays at the outer end with its original position, direction, width and name. The rectangular body uses the existing BlackBox (998/0) layer and ends at the inner end of the straights. DevRec and device-name labels are retained.
- Full blackbox synchronization after whitebox updates uses the same generation rules. Blackboxes exclude internal device geometry and public PCells.

## 2026-10-16 · Consistent fixed-device names

- Rename `Crossing4` to `1550_crossing4`. Align filenames and top-cell names of all five EBeam-derived whiteboxes with their library names, preserving geometry, ports and all text, and synchronize the corresponding blackboxes.
- Keep loader compatibility with legacy EBeam whitebox filenames. Cells already placed in existing layouts are not rewritten automatically.

## 2026-10-15 · Bilingual menus and Spiral lengths

- Calculate Waveguide Length Difference also supports ordinary `Paperclip_Spiral` and `Archimedean_Spiral` instances. Select exactly two supported instances, including mixed selections with Waveguides, to compare actual total lengths and view width and bend parameters. Selecting a composite-width Spiral shows an error and cancels the entire calculation.
- Calculate Waveguide Length now includes ordinary `Paperclip_Spiral` and `Archimedean_Spiral` instances alongside Waveguides, reporting actual centerline lengths, widths and bend parameters. Inner straight lengths and target lengths are not treated as totals. If the selection contains a composite-width Spiral, show an error and cancel the entire calculation without reporting a partial total.
- Match the TFLN PDK menu style by showing Chinese / English together on each line for Waveguides, Layout, DRC and maintenance actions. Remove the Language switch and clean up its old entries during reload while preserving shortcuts.

## 2026-10-14 · PinRec in Layer Exclude

- Add a PinRec (1/10) keep option to Layer Exclude, checked by default on first use and after upgrading. Subsequent uses remember the selection. Keeping the layer preserves port Paths and port-name Text; unchecking it removes the layer.

## 2026-10-13 · Waveguide lengths and parameter details

- Rename the top-level menu to `JNU_MWP_SOI_PDK V1.4` and the technology to `JNU_MWP_SOI_PDK`. Update startup loading, library technology associations and release tools; migrate the previous technology selection and recent-file associations while retaining shortcuts.
- Add Waveguides → Calculate Waveguide Length Difference. Select exactly two Waveguide instances to show their lengths, absolute difference and parameters. Composite comparisons exclude tapers and report constant-width sections separately by physical width. Support bilingual results, reopened GDS and a separate persisted window size.
- Support composite Waveguides by totaling constant-width sections separately for each physical width. Exclude taper sections, include constant-width transitions, and explain the exclusion in the results with the omitted length. Single-width and composite Waveguides can be selected together.
- Show each Waveguide's width, bend type and relevant parameters: Circular radius; Bezier radius, B and maximum/minimum curvature radii; Euler maximum/minimum curvature radii and effective radius.
- Retain the total and individual lengths for multiple selections, with copy counts and subtotals for arrays. Results support scrolling, copying, English and Simplified Chinese.
- Recover historical parameters from cell names and Text after reopening GDS. Missing parameters are shown as “Not stored” rather than replaced by current defaults.

## 2026-10-12 · V1.4 development branch

- Bring V1.3 up to date with `main`, including the centered dual-band TE edge-coupler blackbox, and rename the development branch to `JNU_MWP_PDK_V1.4`.
- Add changelog links to both READMEs and dated Chinese and English update pages with language switching.
- Update the fixed-device counts in the READMEs and library feature cards to 31.
- Rename the Simplified Chinese Snap components menu label from “对齐器件” to “吸附器件”.
- Add Waveguides → Calculate Waveguide Length to total the smoothed centerline lengths of selected single-width Waveguide instances, with instance count and totals in µm/mm. Reject the entire selection if it includes composite-width waveguides or other objects. Both menu and results support English and Simplified Chinese.

## 2026-10-10 · v1.3 libraries and waveguide fixes

- Fix short port straights being simplified in `Pcell_Waveguide_Bump`. Generate the inner and outer arc boundaries directly, retain 20 nm constant-width straights at both ports, align the port faces with PinRec centers, and keep tangent joins.
- Cap the bump angle at 149° to prevent arcs folding past the ports. Readonly parameters report the actual extra length when the requested length exceeds this limit.
- Synchronize 31 fixed blackboxes: add `1310_4×4_MMI` and `1550_3.2um-MFD_TE_edge_coupler`, and replace the dual-band edge coupler with `1550_1310_3.2um-MFD_TE_edge_coupler`.
- Update both library display versions to v1.3 while retaining the stable names `JNULib` and `JNULib_BlackBox`.
- Correct the centered position of the dual-band TE edge-coupler blackbox.

## 2026-10-08 · Menu callbacks and legacy layout migration

- Fix Python callback syntax errors when the installation path contains an apostrophe, restoring menu actions and keyboard shortcuts.
- Add a migration tool for legacy `JNULib` PCell references that appear as `<defunct>` because of old names, retaining a backup during migration.

## 2026-10-01 · Devices, waveguide recovery, and installation

- Fix copied Waveguide PCells reverting to a bare `Waveguide` name after saving and reopening, and improve PCell recovery when opening layouts in the GUI.
- Increase the Path to Waveguide dialog font size and add Simplified Chinese translations.
- Add `Crossing4`, `1310_TE_Terminator`, `1550_TE_Terminator`, `1310_Ybranch`, `1550_Ybranch`, and the editable `Pcell_Waveguide_Bump`.
- Consolidate fixed whiteboxes in `pymacros/JNU_MWP_gds` and move their canonical sources to the separate authorized library. The public PDK contains no fixed whitebox GDS.
- Remove all PCells from the fixed blackbox library, leaving fixed-device footprints and ports.
- Check for updates at KLayout startup on `main` installations, with an update button. Development branches skip prompts, and unavailable networks are ignored.
- Add the university logo, language buttons, and feature map to the READMEs. Move detailed instructions to a separate user guide and group installation steps with AI prompts.

## 2026-09-30 · PCell names and interface language

- Prefix public `JNULib` parametric device names with `Pcell_`.
- Add English and Simplified Chinese options, defaulting to English. Menu and PCell parameter translations take effect after restarting.
- Update whitebox and blackbox library display versions to v1.2 while keeping their registration names stable.
- Begin fixing lost parameterized names in copied Waveguide PCells.

## 2026-09-29 · Default shortcuts

- Bind and persist default JNU shortcuts during installation.
- Migrate legacy blank shortcut settings once.

## 2026-09-28 · Waveguide conversion and direct download

- Allow Path to Waveguide to accept Manhattan Paths on any layer; Waveguide to Path always returns a Path on Si `1/0`.
- Synchronize fixed blackboxes with updates from the separate device library.
- Make the README installer link download the `.lym` file directly.

## 2026-09-24 · Ports and installer

- Standardize PinRec paths to a physical 20 nm length and handle global port directions on rotated instances correctly.
- Add the installer macro that can be dropped into KLayout, plus installation, update-check, and whitebox-update menus.

## 2026-09-21 · Installation paths and port boundaries

- Remove the duplicate technology directory and use the package's technology configuration.
- Improve installation across drives and preview the installation target.
- Generate Make Pins for Cell ports from physical device boundaries to avoid offsets caused by using DevRec boundaries.
- Add clickable Chinese and English feature maps linked to their instructions.

## 2026-09-20 · Public installation and fixed blackboxes

- Make installation paths portable and use Git clones with directory junctions.
- Include fixed blackboxes in the public repository and install fixed whiteboxes through separate authorization.
- Add AI installation and update prompts, a feature overview, bilingual instructions, and issue-reporting links.
- Document the local whitebox directory and its distribution boundary.

## 2026-09-03 · Device connection and maintenance

- Update menus, DRC, and reload behavior, and add Cell Connect by Waveguide.
- Add the project's MIT license notice.

## 2026-08-03 · Waveguides, spirals, and DRC

- Improve waveguide recovery, spiral port geometry, native DRC editing and execution, and reload behavior.
- Refine shared bend geometry and related regression checks.

## 2026-07-27 · Initial public version

- Import the JNU MWP SOI PDK source and technology configuration.
- Add Chinese and English READMEs.
