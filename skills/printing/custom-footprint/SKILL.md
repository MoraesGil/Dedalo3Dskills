---
name: custom-footprint
description: Configure geometry-matched native retention masks for small-footprint FDM parts. Plan circular, elliptical, rounded-rectangle, measured-hull or custom-polygon support coverage with explicit fixed-wall contacts and protected joints, without adding a printable base.
license: MIT
---

# Custom Footprint

Evolve a small-footprint retention proposal into a measured, configurable mask layout. Put short native support contacts on reviewed fixed walls. Match the upper support blocker to the body, and protect functional negatives and other parts. The footprint here is a support-mask envelope; the final brim and support feet come from the slicer.

## Dependencies and scope

Install `prender-3d`, `analyze-3d-geometry`, and this skill together. Install the packages listed in `prender-3d/requirements.txt`. Both sibling installed skills and the categorized repository layout work.

Use a complete millimetre Orca/Bambu-family 3MF, with upright unscaled rigid instances seated on the plate. The planner reads the source and produces JSON only. It does not alter product meshes, create solid collars or bridges, assign materials, arrange copies, slice, or publish a 3MF.

## Plan the masks

Start with the geometry preflight. Identify the target root, plate, allowed support ceiling, fixed component IDs, contact angles, protected components, and neighbouring objects. A fixed-wall selection is required: use `fixed_part_ids`, or set `all_positive_fixed: true` only after confirming that every positive part is fixed. The planner does not classify joints.

Read [references/options.md](references/options.md) for shape parameters, coordinates, clearances, and the exact meaning of height. [examples/cylinder.json](examples/cylinder.json) is a synthetic 20 mm cylinder proposal. [examples/custom-polygon.json](examples/custom-polygon.json) shows an explicit concave profile and protected region. Measure and replace example dimensions; they are not universal print profiles.

~~~sh
python scripts/plan_footprint.py source.3mf /tmp/retention-regions.json   --root-id ROOT_ID --expect-sha256 CURRENT_SOURCE_SHA256   --options-json reviewed-footprint.json --report /tmp/footprint-report.json
~~~

The JSON list in `retention-regions.json` is directly consumable by Prender3D's `apply_retention.py`. Every region is a native `support_enforcer` or `support_blocker`. The report includes measured coverage, real fixed-section overlap, rejected contacts, conservative keepouts, and same-plate neighbour checks. A mask that overlaps a fixed section is a proposed contact, not proof that the native slicer generates a restraining support there.

By default, unselected positive parts and all resolved functional negatives receive conservative keepout blockers. Contact patches that reach those keepouts fail. Dropping a contact requires explicit `skip_unsafe_contacts: true` and `min_contacts`; inspect all rejected angles. The planner checks both the upper blocker band and the lower enforcer band against printable neighbours on the same plate. Keep those checks enabled unless a separate verified layout analysis replaces them.

The optional `brim` object emits native brim settings only. Add `--process-patch-output /tmp/brim-patch.json` to save that small mapping. Merge it into the reviewed native manual-support process; it is not a complete process profile. Arbitrary polygon outlines do not become arbitrary native brim toolpaths.

## Apply and validate

Use the new regions with Prender3D's guarded editor, an explicit manual-support process, physical support/interface filament slots, and the same approved height ceiling. The editor stages a new temporary 3MF. Confirm that the original is closed before integrating any accepted delta; a hash check does not detect an open document.

Compare the staged product geometry, paint, functional negatives, transforms, assemblies, profiles, and unrelated plates with the current source. Slice the complete candidate in the target slicer. Inspect real brim and support widths, low lateral contact, height, continuity, joint clearances, neighbouring objects, tower clearance, bed edges, and travel arcs. Native support feet can expand beyond a mask. A print test is still required to assess adhesion and removal.

This tool uses projected static geometry, not a motion model. Keepouts are conservative XY hulls over the reviewed band. Negative sections support 2D contact checks; no 3D negative Boolean is performed. Native plate-origin conversion, actual support/brim paths, and machine travel are outside this plan's certification.

Inward-oriented disconnected boundary shells require a solid-topology-aware adapter and are refused. Treating such a shell as an independent filled part could erase a cavity and produce an unsafe contact proposal.

~~~text
Preflight → select fixed walls and keepouts → choose measured profile
    → plan native masks → review contacts and clearance → apply → slice → print test
~~~
