# Origin of five bundled EBeam blackboxes

`Crossing4.gds`, `1310_TE_Terminator.gds`, `1550_TE_Terminator.gds`,
`1310_Ybranch.gds`, and `1550_Ybranch.gds` are fixed rectangular blackboxes
derived from upstream `ebeam_crossing4`, `ebeam_terminator_te1310`,
`ebeam_terminator_te1550`, `ebeam_y_1310`, and `ebeam_y_1550` in the
SiEPIC EBeam PDK (local release 0.4.53). Original waveguide geometry
and model annotations are omitted; optical port locations and names are kept.

Upstream: <https://github.com/SiEPIC/SiEPIC_EBeam_PDK>.
License: MIT, <https://github.com/SiEPIC/SiEPIC_EBeam_PDK/blob/master/LICENSE.md>.
Copyright (c) 2016-2020, Lukas Chrostowski and contributors.
The full permission and warranty notice is in the PDK's `LICENSE.md`.

Parametric JNU PCells, including `Pcell_Waveguide_Bump`, are not included in
this fixed blackbox directory.
