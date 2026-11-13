---
name: analyze-3d-geometry
description: Inspect complete Orca or Bambu-family 3MF assemblies before retention or layout changes. Measure real first-layer sections, resolve nested component transforms, and inventory functional negatives and native modifiers without editing the source.
license: MIT
---

# Analyze 3D Geometry

Use a read-only geometric baseline before choosing support contacts, a retention footprint, or a new arrangement. Distinguish the product's bounding dimensions from its actual contact with the plate. This tool measures geometry; it does not decide which components can move.

## Inputs and dependencies

Install this skill together with `prender-3d`, and install the Python packages in that skill's `requirements.txt`. The scripts resolve either sibling installed skill directories or the categorized Dedalo3Dskills checkout. No slicer, online service, or printer connection is required.

The input must be a complete Orca/Bambu-family 3MF containing both `Metadata/model_settings.config` and `Metadata/project_settings.config`. A bare mesh 3MF or STL needs a separate adapter. Keep the project intact rather than importing meshes into an empty project to bypass missing metadata.

## Measure

Run [scripts/preflight.py](scripts/preflight.py) on the saved source. The default examines all build roots. Select a root only when the requested task has that scope.

~~~sh
python scripts/preflight.py source.3mf   --first-layer-height-mm 0.2 --output /tmp/preflight-report.json
~~~

Set the actual first-layer height from the project's reviewed process. The section plane is halfway through that first layer above `--bed-z-mm` (default zero). It is anchored to the plate, not to the bottom of a floating part. `--root-id ROOT_ID` limits the report. `--include-section-geometry` adds XY GeoJSON for a local preview. Output paths must be new files inside a system temporary directory; the source is never written. Use a private temporary directory when reports contain proprietary geometry.

Read the following fields before planning retention:

- `source_sha256` identifies the snapshot. Renew the baseline after geometry, paint, orientation, supports, or placement changes.
- Each root lists its component hierarchy and native subtypes, positive and functional-negative component counts, root bounds, volume basis, and non-watertight component count. Support/modifier meshes are excluded from positive product measurements.
- Each build instance lists plate membership, the actual build transform, transformed bounds, plate seating, and whether the current Prender3D adapter supports its pose. Measurement can report a tilted or scaled build even when that adapter must refuse it.
- `first_layer` gives a real horizontal section of the transformed positive mesh union, minus resolved functional-negative sections at that same plane. Check `section_complete` and warnings before using its area or optional geometry.

Resolve uncertain fixed walls, articulations, gears, sockets, and motion clearance with the model's design or the user. A component count or radial pattern does not prove that a component is a moving joint. For a mask plan, continue with `custom-footprint`; for octopus-specific retention, use `prender-polvo-3d`.

## Limits that affect decisions

First-layer area is a geometric section, not extruded contact area, an adhesion score, or native brim geometry. Face paint and material profiles are preserved by leaving the source untouched; this tool does not resolve a physical material from paint.

Negative subtraction is two-dimensional at each reported plane. It does not construct a complete Boolean solid, infer joint motion, or certify a functional hole at other heights. Volume is the sum of positive component volumes and can double-count overlapping parts. Incomplete or non-watertight sections need review before automation.

The shared reader separates disconnected boundary shells. A watertight inward-oriented shell can represent a cavity of another shell, so this preflight refuses it with `inward_boundary_shell_requires_solid_topology_adapter` instead of filling that cavity. Use a solid-topology-aware adapter for those models.

Build XY coordinates are the project's plater coordinates. Plate membership is reported, but the helper does not convert each plate's origin to machine coordinates, certify bed edges, or evaluate toolhead lift and travel clearance. A fresh native slice and a physical print remain separate validation steps.

~~~text
Complete saved 3MF → resolve geometry and transforms → section the first layer
    → identify fixed surfaces and keepouts → plan native support → slice and inspect
~~~
