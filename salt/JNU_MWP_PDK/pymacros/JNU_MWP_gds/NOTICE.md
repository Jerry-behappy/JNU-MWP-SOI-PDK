# SiEPIC EBeam layout cells in the independent Library

The following five GDS files are distributed in this independent
Library repository and are not included in the public JNU MWP PDK repository.
They are sourced from the SiEPIC EBeam PDK, installed locally as EBeam version
0.4.53:

- `1550_crossing4.gds` (upstream `ebeam_crossing4.gds`)
- `1310_500nm_TE_terminator.gds` (upstream `ebeam_terminator_te1310.gds`)
- `1550_500nm_TE_terminator.gds` (upstream `ebeam_terminator_te1550.gds`)
- `1310_Ybranch.gds` (upstream `ebeam_y_1310.gds`)
- `1550_Ybranch.gds` (upstream `ebeam_y_1550.gds`)

JNU library names, in the same order: `1550_crossing4`,
`1310_500nm_TE_terminator`, `1550_500nm_TE_terminator`, `1310_Ybranch`, and `1550_Ybranch`.
Each distributed filename and top-cell name matches its JNU library name.
Only structure-name records are renamed; geometry, ports and all original
GDS Text remain unchanged. The names above record the upstream provenance.

Upstream project: <https://github.com/SiEPIC/SiEPIC_EBeam_PDK>.
Original path: `EBeam/gds/EBeam/`.
License: MIT, <https://github.com/SiEPIC/SiEPIC_EBeam_PDK/blob/master/LICENSE.md>.
Copyright (c) 2016-2020, Lukas Chrostowski and contributors.
The required permission and warranty notice is included beside these GDS files
in [`LICENSE.md`](LICENSE.md). The repository root also retains this copyright.

The original GDS Text is retained in the JNU whitebox cells. In particular,
EBeam component and Lumerical INTERCONNECT annotations describe the upstream
model; bundling these layouts does not add a JNU simulation model.
