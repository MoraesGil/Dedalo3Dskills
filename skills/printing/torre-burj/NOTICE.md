# Code provenance

Copyright (c) 2026 MoraesGil. Published under this repository's MIT license by the author, including commercial use.

The original author-owned deterministic `custom_tower/gcode.py` and `custom_tower/geometry.py` were developed by Gilberto Moraes in the separate Snapmaker slicer integration project. This public port adapts only those author-owned modules:

- Initial custom tower implementation: commit `7f351d870f90aa7b0873fe4fdebfe3734413667f`.
- Commanded occupancy/foundation-brim revision: commit `0b5df2d50482ee7edc5cc2921dbfe6f784e624c4`.

Changes in this port include instance-aware heterogeneous section measurement, optional interface material, bounded taper power, strict standard-library inputs, and a new standalone 3MF adapter, CLI and audit wiring.

The new adapter does not include the other project's `Project`, preset normalization, schema extraction, guard, service, server or editor implementation. This notice does not relicense that separate AGPL project or third-party work. Snapmaker Orca remains a separate external program with its own license. No slicer binary, vendor preset payload or client model is distributed here.

The geometric inspiration is the Burj Khalifa's three-lobed form. No affiliation with the building, its architects or owners is claimed.
