# Footprint options

The options JSON is a single object. All coordinates and lengths use root-local millimetres. Angles are counterclockwise degrees from root-local +X. JSON numbers must be finite. Unknown options are rejected.

## Required decisions

| Field | Meaning |
| --- | --- |
| `height_mm` | Native support ceiling above the product's measured root-local bed. Positive and below the product top. |
| `fixed_part_ids` | Explicit positive component IDs allowed to receive contact. Nested component IDs are supported. |
| `all_positive_fixed` | Alternative to fixed IDs, explicitly `true` after checking that every positive part is fixed. |
| `contact_angles_deg` | 1–64 distinct rays from `center_xy`. Each patch is placed at the farthest measured fixed-wall boundary hit on that ray. |

Provide fixed IDs or the all-fixed confirmation, never both. Every target build instance must have a supported pose. Repeated linked instances receive the same root-local plan; separate roots before independent editing.

## Profile and coverage

| Field | Default | Meaning |
| --- | --- | --- |
| `shape` | `auto` | `auto`, `circle`, `ellipse`, `rounded_rectangle`, `hull`, or `polygon`. |
| `shape_parameters` | `{}` | Profile-specific values below. |
| `margin_mm` | `0.6` | Outward coverage margin over the measured fixed-body blocker band. |
| `center_xy` | Measured band bounds centre | Root-local centre used for contact rays and centred profiles. |
| `segments` | `128` | Circle/ellipse approximation, integer 16–256. |

The measurement uses clipped mesh boundary triangles plus actual section interiors in the complete upper blocker band, rather than a full-height bounding box. Coverage must contain that measured projection and margin; an undersized profile is rejected. Curved outlines are polygonal with a coverage check.

- `auto`: use a circle when its area overhead is at most 15% over the buffered measured hull; otherwise use the hull. This is a mask heuristic, not a shape or articulation classifier.
- `circle`: optional `radius_mm`; otherwise fit the measured band. Includes the margin and compensates for polygon facets.
- `ellipse`: optional `radii_mm: [rx, ry]` and `rotation_deg`. Automatic radii fit an axis-aligned measured band. A rotated or explicitly sized ellipse must still pass coverage.
- `rounded_rectangle`: optional `size_mm: [width, depth]`, `corner_radius_mm`, and `rotation_deg`. Defaults to band dimensions and zero corner radius. Rounded corners can remove coverage at corners; enlarge the reviewed dimensions if necessary.
- `hull`: measured convex hull plus margin. It can fill concavities and needs more room than an explicit conforming outline.
- `polygon`: required `points_xy`, a simple 3–512 point XY outline, followed by the margin. Concave outlines are supported and triangulation is checked. Holes and disconnected outlines are not supported in one mask; protect holes with keepouts instead.

## Height and contact band

| Field | Default | Meaning |
| --- | --- | --- |
| `upper_band_height_mm` | `3` | Blocker thickness immediately above the ceiling. |
| `contact_band_height_mm` | `min(3, height_mm)` | Enforcer thickness ending at the ceiling. It cannot exceed the total support ceiling. |
| `contact_depth_mm` | `2` | Radial patch width, centred on the measured fixed wall. |
| `contact_width_mm` | `2` | Tangential patch width. |

For a root-local bed Z of zero and `height_mm: 3`, the default enforcers occupy Z=0..3 and the upper blocker occupies Z=3..6. These are mask dimensions. Tree branch diameter and native support/contact gaps belong to the separately reviewed process. A compact upper blocker is not a hard toolpath height clip; confirm actual support Z in the fresh slice.

Contact wall measurement occurs halfway through the enforcer band. A strong taper can change contact along Z. Check the emitted support and interface paths throughout that band.

## Keepouts and neighbours

| Field | Default | Meaning |
| --- | --- | --- |
| `keepout_part_ids` | `[]` | Additional positive parts to protect. |
| `protect_unselected_parts` | `true` | Protect positive parts outside the reviewed fixed selection. |
| `keepout_polygons_xy` | `[]` | Explicit simple XY polygons for gears, joints, openings or other protected space. |
| `keepout_clearance_mm` | `0.6` | Outward margin of protected regions. |
| `obstacle_polygons_xy` | `[]` | Explicit neighbouring envelopes; both contacts and upper masks must avoid them. |
| `check_neighbor_parts` | `true` | Check actual printable same-plate instances against upper and contact mask bands. |
| `skip_unsafe_contacts` | `false` | Allow explicitly requested dropping of unsafe contact angles. |
| `min_contacts` | All requested | Required safe contact count when dropping is allowed. |

Functional negatives are always protected. Selected protected meshes use conservative XY hulls over bed..ceiling+blocker-height, not inferred joint motion. Add the real motion envelope when the static hull is insufficient. Neighbour checks use positive band projections without subtracting functional negatives; this can refuse a safe placement inside another part's void. Disable that check only with a separate measured clearance analysis. Build membership uses native plate IDs and project plater coordinates; no plate-to-machine origin conversion is claimed.

## Optional native brim patch

`brim` accepts `type`, `width_mm`, and optional `tree_width_mm`. Type is `no_brim`, `outer_only`, `inner_only`, or `outer_and_inner`. `no_brim` requires zero width; enabled brim requires a positive width. Tree brim width can be zero.

The output is a small process patch with `brim_type`, `brim_width`, and optionally `tree_support_brim_width`. It does not include manual support enablement, a material, temperatures, speed, quality, raft, or G-code. Merge it into a reviewed complete retention process before applying. It does not make the native brim follow a supplied custom polygon.
