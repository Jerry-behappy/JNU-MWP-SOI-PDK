# Bundled SiEPIC EBeam layout cells

The following five unchanged GDS files are sourced from the SiEPIC EBeam PDK,
installed locally as EBeam version 0.4.53:

- `ebeam_crossing4.gds`
- `ebeam_terminator_te1310.gds`
- `ebeam_terminator_te1550.gds`
- `ebeam_y_1310.gds`
- `ebeam_y_1550.gds`

Upstream project: <https://github.com/SiEPIC/SiEPIC_EBeam_PDK>.
Original path: `EBeam/gds/EBeam/`.
License: MIT, <https://github.com/SiEPIC/SiEPIC_EBeam_PDK/blob/master/LICENSE.md>.
Copyright (c) 2016-2020, Lukas Chrostowski and contributors.
The required permission and warranty notice is included beside these GDS files
in [`LICENSE.md`](LICENSE.md). The repository root also retains this copyright.

The original GDS Text is retained in the JNU whitebox cells. In particular,
EBeam component and Lumerical INTERCONNECT annotations describe the upstream
model; bundling these layouts does not add a JNU simulation model.
