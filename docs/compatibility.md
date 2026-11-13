# Compatibility and limits

[Back to the catalog](../README.md#skill-catalog)

## Retention editors: what is supported

| Area | Current scope |
| --- | --- |
| Input | Complete Orca/Bambu-family 3MF project with `Metadata/model_settings.config` and `Metadata/project_settings.config` |
| Geometry | Millimetres, configured multipart roots, supported package-local mesh references |
| Builds | Rigid, upright and on the bed; unsupported rotations/scales must be adapted explicitly |
| Output | Read-only JSON reports/plans, or new temporary 3MF from the explicitly selected editor; source preserved |
| Slicer | Native engine supplied by the user; reference workflow tested with Snapmaker Orca |
| Materials | Existing physical slots; no bundled printer/material calibration |
| Installation | Generic skill can stand alone; analysis, footprint, octopus and Burj skills reuse its project helpers |
| Python | Python 3.12 is the tested runtime; install the declared geometry dependencies |

STL, OBJ and mesh-only 3MF are not direct inputs to these project editors. Import them into a compatible slicer, assign the printer/materials, orient the model and save a complete project first.

Orca/Bambu metadata compatibility is not a promise that every fork or version will produce the same support. Slice with the actual target engine.

## The octopus adapter

`prender-polvo-3d` recognizes one articulated geometry family: a fixed central body with eight regularly spaced radial chains and a compatible four/five-ring segment pattern. It is a pattern detector, not a universal toy or joint classifier.

Its reference profile uses support in Z=0..3 mm on the common fixed base. The upper blocker covers the measured fixed body in Z=3..6 mm. The eight moving-arm keepouts remain separate. Neither dimension describes half the entire themed head.

The detector reports a mismatch instead of treating any object named “octopus” as a match. Current name-based Skull/Skeleton exclusions are an extra conservative routing rule, not geometric proof. Inspect any requested exception.

The specialization's imports require `prender-3d` alongside `prender-polvo-3d`. Install both skills and keep their names. Renaming or installing only the specialization breaks that relationship.

## What geometry analysis means here

`analyze-3d-geometry` reports actual planar mesh sections at its declared first-layer plane. Resolved negative sections are subtracted in 2D where supported. This is not a full slicer Boolean or proof of the physical first-layer toolpath. The report records unresolved features instead of automatically classifying every joint.

`custom-footprint` plans native mask descriptors using explicit fixed-part selection, height, contour and keepouts. It writes JSON only. The guarded retention CLI applies reviewed regions and settings in a separate step. A successful plan does not prove that the slicer generated useful support contact.

The agent inspects measurements, identifies useful fixed contacts and plans the constraints. Scripts parse positive geometry, describe masks and preserve project structure. A conservative convex mask may cover empty concavities; tighter geometry and keepouts remain necessary where those spaces matter.

The helpers do not solve printer dynamics, identify every functional joint automatically, or calibrate a universally correct support gap.

## API boundaries

Use `apply_retention.py` as the guarded entry point. It accepts only native retention fields and refuses machine, material, temperature, quality, G-code and raft overrides.

`apply_regions` is a low-level in-memory project writer. Its caller must validate the supplied native settings; it does not enforce the CLI allowlist. The grid adapter also accepts a broader explicitly reviewed object process. Do not bypass the CLI and assume that calibration preservation is enforced by the core.

## Validation boundary

Synthetic automated tests exercise parsing, mask geometry, ownership, idempotent updates, rejected operations and template detection. They do not run a slicer or a printer.

The Burj export additionally has a synthetic pilot sliced by native Snapmaker Orca build `9bf2f18`: one custom tower, 72 real changes, identical executable commands with object-flush flags off/on, and the tower ending at the last change at 16 mm. Those explicit-command checks passed. Native U1 G-code also calls firmware macros whose bodies are not available to this parser: the strict overall audit remains incomplete (`passed=false`, exit 2), with command-level success reported separately. It does not certify motion or extrusion hidden inside those macros. The native prime-tower path creates another tower; it is not the supported single-Burj mode. See the [Burj skill](../skills/printing/torre-burj/SKILL.md) for the contract and limits. No physical cleaning or adhesion test was performed for this export.

The public package does not ship private project-specific wrappers or a universal G-code/spiral-travel validator. The included Burj audit is specialized to its own plan. Native support contact, collision and machine checks must be performed for each output.

The helpers neither start prints nor change a live printer's speed, temperature or fans. A physical print is required to verify adhesion, movement and removability.

## Dependency licenses

NumPy, lxml, trimesh, Shapely and the declared mesh-analysis dependencies are installed separately under their own licenses. The MIT license in this repository covers the original skill instructions, helpers, illustrations and documentation. Models and printer software retain their existing licenses.

## Image-based relief

[Destacar relevo 3D](../skills/printing/destacar-relevo-3d/SKILL.md) adds a separate workflow for image registration, contrasting outlines and raised emblems. Its helper accepts a reviewed planar XY polygon with holes and produces a closed STL in a temporary directory. Install its own requirements.txt. It does not reuse the retention writers and does not promise automatic 3MF integration or curved projection.

Synthetic tests cover planar topology, holes, requested dimensions, invalid inputs and mesh export/reload. Native slicing, color priority, registration, preserved functional voids and physical adhesion must be checked for each real project.
