# Compatibility and limits

[Back to the catalog](../README.md#skill-catalog)

## What is supported

| Area | Current scope |
| --- | --- |
| Input | Complete Orca/Bambu-family 3MF project with `Metadata/model_settings.config` and `Metadata/project_settings.config` |
| Geometry | Millimetres, configured multipart roots, supported package-local mesh references |
| Builds | Rigid, upright and on the bed; unsupported rotations/scales must be adapted explicitly |
| Output | New temporary 3MF with native support modifiers; the source is preserved |
| Slicer | Native engine supplied by the user; reference workflow tested with Snapmaker Orca |
| Materials | Existing physical slots; no bundled printer/material calibration |
| Installation | Generic skill can stand alone; octopus specialization needs its sibling generic skill |
| Python | Python 3.12 is the tested runtime; install the declared geometry dependencies |

STL, OBJ and mesh-only 3MF are not direct inputs to these project editors. Import them into a compatible slicer, assign the printer/materials, orient the model and save a complete project first.

Orca/Bambu metadata compatibility is not a promise that every fork or version will produce the same support. Slice with the actual target engine.

## The octopus adapter

`prender-polvo-3d` recognizes one articulated geometry family: a fixed central body with eight regularly spaced radial chains and a compatible four/five-ring segment pattern. It is a pattern detector, not a universal toy or joint classifier.

Its reference profile uses support in Z=0..3 mm on the common fixed base. The upper blocker covers the measured fixed body in Z=3..6 mm. The eight moving-arm keepouts remain separate. Neither dimension describes half the entire themed head.

The detector reports a mismatch instead of treating any object named “octopus” as a match. Current name-based Skull/Skeleton exclusions are an extra conservative routing rule, not geometric proof. Inspect any requested exception.

The specialization's imports require `prender-3d` alongside `prender-polvo-3d`. Install both skills and keep their names. Renaming or installing only the specialization breaks that relationship.

## What geometry analysis means here

The agent inspects measurements, identifies useful fixed contacts and plans the constraints. Scripts parse positive geometry, describe masks and preserve project structure. A conservative convex mask may cover empty concavities; tighter geometry and keepouts remain necessary where those spaces matter.

The helpers do not solve printer dynamics, identify every functional joint automatically, or calibrate a universally correct support gap.

## API boundaries

Use `apply_retention.py` as the guarded entry point. It accepts only native retention fields and refuses machine, material, temperature, quality, G-code and raft overrides.

`apply_regions` is a low-level in-memory project writer. Its caller must validate the supplied native settings; it does not enforce the CLI allowlist. The grid adapter also accepts a broader explicitly reviewed object process. Do not bypass the CLI and assume that calibration preservation is enforced by the core.

## Validation boundary

Synthetic automated tests exercise parsing, mask geometry, ownership, idempotent updates, rejected operations and template detection. They do not run a slicer or a printer.

The public package does not ship the private project-specific wrappers used during development. In particular, it does not ship a broad G-code/temperature/spiral-travel validator. Native support contact, collision and machine checks must be performed for each output.

The helpers neither start prints nor change a live printer's speed, temperature or fans. A physical print is required to verify adhesion, movement and removability.

## Dependency licenses

NumPy, lxml, trimesh, Shapely and the declared mesh-analysis dependencies are installed separately under their own licenses. The MIT license in this repository covers the original skill instructions, helpers, illustrations and documentation. Models and printer software retain their existing licenses.
