---
name: prender-3d
description: Plan localized native slicer supports and connected brims to brace tall or small-footprint FDM parts against lateral movement. Use for Prender3D, support collars made from slicer support, grip batches, and protected moving joints in complete Orca/Bambu-family 3MF projects.
license: MIT
---

# Prender3D

Help a small footprint resist movement with a low, removable band of native slicer support. Measure the part, put contact on fixed walls, and keep moving joints and functional openings clear. Support placement is a geometric proposal until the saved project has been sliced and checked.

## Scope and prerequisites

Use a complete Orca/Bambu-family project with Metadata/model_settings.config and Metadata/project_settings.config. The editing helpers require millimetres, a configured multipart root, upright rigid builds seated on the plate, and reviewed native manual-support settings. Plain mesh 3MF, STL, arbitrary slicer formats, tilted builds, and nonuniform scale need a separate adapter. Do not rename the printer or discard metadata to bypass a refusal.

Install the Python dependencies from requirements.txt in this skill directory. The scripts do not include a slicer, printer connector, cloud service, or automatic open-document detector. Use the user's installed slicer, supplied CLI, or approved slicer tool for the final native slice.

The octopus specialization is a separate skill, prender-polvo-3d. If using it, install both skill directories side by side under the same parent; its scripts import this skill's helpers.

## Define the retention contract

Before editing, record the target root and plate, orientation, measured first-layer contact, maximum support height, fixed surfaces allowed to receive contact, and protected joints, gears, holes, sockets, and nearby objects. Separate the support's total height, the enforcer's Z thickness, and the tree branch diameter.

- Generate only support_enforcer and support_blocker modifiers. A printable collar, raft, solid foot, rib, or connector is a different product and does not satisfy this skill.
- Require real low lateral contact above the first layer. A detached support island cannot restrain the part.
- Choose a cylinder for radial geometry, a measured contour for other shapes, and a narrow local box only for a planar contact patch. A large convenience box can overlap a neighbouring part or purge tower.
- Protect the actual moving surfaces and joint clearances in every support layer. Positive-mesh projection does not subtract negative volumes or certify a functional void; add explicit keepouts for those regions.
- Resolve the physical filament for the part, support, and support interface. Per-face paint can override a default extruder. Do not assign a material to a blocker as though it were a printable part.
- Preserve the product meshes, paint, negative parts, scale, assembly structure, user profiles, materials, cooling, temperatures, and unrelated plates. Change only the agreed retention settings and placement.

Use one independent multipart root per repeated unit. If a connected network is requested, form it with native brim and support paths. Measure spacing from the product and all generated support feet; do not model solid bridges between units.

## Helpers

- [scripts/apply_retention.py](scripts/apply_retention.py) is the entry point for one existing root. It measures the positive product's root-local bed/top and applies only the explicit contact regions and reviewed process supplied by the caller. It does not create a plate, copy, orientation, or layout. Provide support and interface filament slots explicitly; those slots must already exist in the project.
- [scripts/geometry_project.py](scripts/geometry_project.py) reads positive geometry recursively. Its conformal_blocker function chooses a conservative radial cylinder or a rounded convex outline and checks coverage. A convex outline can still cover concavities; supply a more faithful mask near other objects and verify clearance.
- [scripts/prender3d_core.py](scripts/prender3d_core.py) exposes apply_regions(data, root_id, frame, regions, settings, height_limit_mm=...). It accepts explicit cube, cylinder, or mesh shapes only as native support modifiers. It updates the ZIP-member mapping only after validation, records ownership, preserves reusable IDs, and invalidates affected embedded slice caches. It does not write files or slice. This is a low-level writer: it assumes the caller has validated every settings field and does not enforce the CLI retention-only allowlist. Use apply_retention.py for the guarded public entry point.
- [scripts/assemblies.py](scripts/assemblies.py) separates linked instances into independent roots without rewriting product mesh resources. Additional copies and placement require an explicit layout.
- [scripts/prepare_retention_grid.py](scripts/prepare_retention_grid.py) stages an explicit grip-style batch with a connected-brim proposal. Read its help before use. It requires a current source hash, reviewed process JSON, native profile JSON, and source root. Its automatic layout adds a plate and refuses changes to the existing native plate-grid width. Existing batches can be updated without reflow; placement changes require the explicit reflow option.

For an existing root, use the explicit-region entry point. The regions file is a JSON list of role, label, subtype, shape and values descriptors in root-local millimetres. The process file is a JSON object of reviewed native process fields. [examples/regions.json](examples/regions.json) and [examples/process.json](examples/process.json) describe a **synthetic 20 mm diameter cylinder**, not an automatic profile for the user's part. Measure and replace those coordinates and settings before use.

~~~sh
python scripts/apply_retention.py source.3mf /tmp/retention-candidate.3mf \
  --expect-sha256 CURRENT_SOURCE_SHA256 --root-id ROOT_ID \
  --regions-json reviewed-regions.json --process-json reviewed-process.json \
  --height-mm REVIEWED_HEIGHT
~~~

Shapes use the core helper arguments: cube values are [size_xyz, center_xyz, optional_angle_degrees], cylinder values are [radius, height, center_xyz, optional_segments], and mesh values are [vertices, triangle_indices]. Enforcers must stay inside the declared support ceiling; blockers may cover a protected band above it. The apply_retention.py CLI requires explicit enabled manual support. It accepts retention settings only: enable_support, support_*, tree_support_*, brim_*, raft_* (with raft_layers disabled), and independent_support_layer_height. Machine integration, multi-bed selection, G-code hooks, product extruder, temperatures, filament profiles, and quality overrides are rejected. A successful edit is not a successful native slice.

The optional grid helper requires at least 10% product spacing and a manual native support process. Those are limits of that adapter, not universal printing recommendations. It does not rotate a product; the orientation label describes the existing pose. Use explicit regions when the default four contact patches do not suit the measured geometry.

Grid command structure, after identifying the real root and replacing the placeholders:

~~~sh
python scripts/prepare_retention_grid.py source.3mf /tmp/retention-candidate.3mf \
  --expect-sha256 CURRENT_SOURCE_SHA256 --root-id ROOT_ID \
  --process-json reviewed-process.json --native-profile-json reviewed-native-profile.json \
  --support-extruder FILAMENT_SLOT --count 4 --height-mm REVIEWED_HEIGHT
~~~

Output must be a new file in the system temporary directory. Never pass the original as the output. The CLI stages a candidate; source publication and final slicing are separate actions. A hash check does not prove that a document is closed.

The grid's native-profile JSON is an object describing patch/envelope parameters, optional explicit regions, and retention process overrides. It is different from the plain regions list consumed by apply_retention.py. Do not reuse the two JSON files interchangeably.

## Validate before publishing the result

1. Confirm the original is saved and closed. Record its current hash and keep a private backup. Rebase a repair onto the current source if the owner saved a newer version.
2. Compare the staged archive against that source: product geometry and paint, functional negatives, components, transforms, assemblies, unrelated plates, and material settings must remain intact. Owned retention geometry must be modifiers only.
3. Slice the complete staged project with the actual target slicer. No native-slice command is bundled here. Do not present a successful mesh edit as a successful slice.
4. Inspect the emitted support, support-interface, and brim paths with their physical line widths. Check supported feet, continuity, lateral contact, maximum Z, moving-joint clearance, overlap between copies, purge-tower clearance, bed edges, and lift/travel arcs. The slicer may expand support feet despite zero configured expansion.
5. Integrate only the accepted delta into the current source, invalidate old G-code, slice the final saved artifact, and report file, plate, count, slicer exit code, hashes, and observed limits. Confirm the existing machine/material requirements from the emitted G-code.

No universal G-code validator is included. Physical adhesion, vibration reduction, surface marks, and removal force require a print test. Do not start or control a printer through this skill unless the user separately requests that action.

~~~text
Measure fixed walls and keepouts → stage low native supports → slice
    → verify contact, continuity, joints and travel → test the print
~~~
