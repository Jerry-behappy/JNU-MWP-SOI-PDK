# SiEPIC EBeam whitebox source location

The following five unchanged GDS files are stored in the separately authorized
`Jerry-behappy/JNU-MWP-SOI-Library/JNU_MWP_gds` repository, not in this public
PDK repository. They originate from the SiEPIC EBeam PDK, installed locally as
EBeam version 0.4.53:

- `ebeam_crossing4.gds`
- `ebeam_terminator_te1310.gds`
- `ebeam_terminator_te1550.gds`
- `ebeam_y_1310.gds`
- `ebeam_y_1550.gds`

JNU library display names, in the same order: `Crossing4`,
`1310_TE_Terminator`, `1550_TE_Terminator`, `1310_Ybranch`, and `1550_Ybranch`.
The source GDS filenames and their internal upstream cell names remain unchanged.

Upstream project: <https://github.com/SiEPIC/SiEPIC_EBeam_PDK>.
Original path: `EBeam/gds/EBeam/`.
License: MIT, <https://github.com/SiEPIC/SiEPIC_EBeam_PDK/blob/master/LICENSE.md>.
Copyright (c) 2016-2020, Lukas Chrostowski and contributors.
The required permission and warranty notice accompanies the source files in
the separate Library repository. This public repository distributes only
derived fixed blackboxes for these devices.

The original GDS Text is retained in the JNU whitebox cells. In particular,
EBeam component and Lumerical INTERCONNECT annotations describe the upstream
model; bundling these layouts does not add a JNU simulation model.
