# Origin of five bundled EBeam blackboxes

`ebeam_crossing4.gds`, `ebeam_terminator_te1310.gds`,
`ebeam_terminator_te1550.gds`, `ebeam_y_1310.gds`, and `ebeam_y_1550.gds`
are fixed rectangular blackboxes derived from the corresponding original
SiEPIC EBeam PDK GDS cells (local release 0.4.53). Original waveguide geometry
and model annotations are omitted; optical port locations and names are kept.

Upstream: <https://github.com/SiEPIC/SiEPIC_EBeam_PDK>.
License: MIT, <https://github.com/SiEPIC/SiEPIC_EBeam_PDK/blob/master/LICENSE.md>.
Copyright (c) 2016-2020, Lukas Chrostowski and contributors.
The full permission and warranty notice is in the PDK's `LICENSE.md`.

`Pcell_Waveguide_Bump.gds` is a fixed blackbox generated from the JNU-native
`Pcell_Waveguide_Bump` default variant, not EBeam PCell source code.
