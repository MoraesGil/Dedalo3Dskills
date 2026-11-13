# Register the image and protect the surface

Use the same recognizable motif throughout the comparison. Identify the image's crop, orientation and intended target face before tracing it. Use supplied vector art when available; raster tracing requires checking silhouette, holes and narrow tips against the image.

## Scale, projection and intent

- A planar image with enough non-collinear corresponding points can be rectified into a planar model frame. Record those correspondences and the physical scale. Do not stretch the art independently in X and Y merely to fit a bounding box.
- A curved target requires its measured surface. Map a local patch, inspect side views and avoid projection onto the back face, overhangs or another shell. Check self-intersections and changes of normal. Unknown hidden geometry stays unknown.
- Raised outline is the boundary band of the approved mask; a filled emblem occupies its interior except protected holes. Selected accents use only approved regions. Negative space between legs or letters belongs to the artwork.
- Keep intentional small holes. Tiny gaps from floating-point projection need a measured tolerance and explicit classification before repair; never delete all interior rings to obtain a watertight result.

## Root and keepouts

Measure the wall behind the relief and the functional voids after negatives are applied. Positive mesh bounds alone do not describe a threaded hole. Burial must remain outside threads, sockets, moving clearances and the far wall. If available wall depth is insufficient, reduce burial with a stated limitation or propose a different attachment; do not seal the opening.

For a planar surface at Z=3 mm, rise 0.64 mm and root 0.40 mm place the relief at Z=2.60..3.64 mm. That is a mesh contract. In a layered slice, the expected buried toolpaths occupy the layers intersecting Z=2.60..3.00, while exposed paths occupy the layers above Z=3.00. Layer discretization changes the exact first/last sampled Z; inspect extrusion thickness and region, not only an equality with the nominal boundary.

In Orca-family projects, component/volume order can decide which solid owns an overlap. An illustrative failure is a white mesh spanning the buried band while only the black substrate extrudes there. Put the intended root volume at the correct priority for the actual engine, or make disjoint color volumes with a shared interface, then refit the full saved project and inspect fresh paths. Do not assume a universal priority direction across slicers.

## Compatibility boundary

The helper accepts one valid, planar Polygon with optional holes in millimetres. Separate islands require separate calls; integrate each as intended. It rejects invalid polygons, nonfinite dimensions and an outline width that consumes the entire mask. Narrow local tips may still become filled as the inset collapses locally: review those tips and their toolpaths. Minimum-feature checks and image registration are agent responsibilities.

The helper does not modify the substrate, subtract functional negatives, resolve a 3MF's color inheritance or certify native engine compatibility. Mesh generation is tested with synthetic fixtures. Project integration, curved-surface mapping, material priority, layer coverage and physical adhesion require case-specific validation.
