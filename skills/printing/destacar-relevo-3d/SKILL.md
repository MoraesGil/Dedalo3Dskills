---
name: destacar-relevo-3d
description: Use when a reference image or existing model should become a raised contrasting outline, filled emblem or local highlight on a 3D-printable part, especially when preserving multipart colors and functional features in an Orca/Bambu-family 3MF.
license: MIT
---

# Destacar relevo 3D

Turn a visual reference into a measured, separately colored relief. A picture describes appearance; the target geometry supplies scale, surface depth and protected features. A colored overlay alone is not proof of a printable embedded root.

## Resolve the image against the part

Inspect the supplied image visually and the target mesh geometrically. Identify the selected motif, target root/plate, reference viewpoint, physical color slot and protected holes, threads, joints and fitting faces. Use a model edge or supplied measurement for scale. A perspective photo needs correspondences; its pixels do not supply hidden depth.

Choose **outline**, **filled emblem** or **selected accents** from the request and reference. If that choice or registration remains materially ambiguous, show a small annotated proposal and ask only for the missing choice. Do not invent an unseen side or silently fill intentional holes. Read [image and surface registration](references/image-and-surface.md) for curved surfaces, projection and fragile details.

Record the local coordinate frame, outline width, external rise, buried depth, substrate thickness and keepouts. Derive them from the part, nozzle, material and appearance. Example values of 0.85 mm width, 0.64 mm rise and 0.40 mm burial are an illustration, not universal defaults. A thin wall or a functional void can make burial impossible.

## Construct and integrate

1. Confirm the original is saved and closed. Record its current hash; stage a candidate and backup outside the product directory.
2. Trace approved closed polygons, retain holes/islands and check minimum printable features. Build a closed relief solid with a measured root inside adequate substrate. On a curved face, offset along reviewed local surface normals; a straight Z extrusion is only a planar adapter.
3. Assign a separate normal part and the existing physical filament slot. Preserve root/resource IDs, component references/transforms, paint, functional negatives, assemblies and unrelated settings. Convert root-local versus world coordinates explicitly. A flattened STL is not a replacement for the multicolor project.
4. Update every linked instance requested by the user; isolate instances first if only some should change. Preserve the generating source when present. Reapply the accepted delta to the latest original after checking its hash again; a staging variant is not the final source.

The optional [planar helper](scripts/build_relief.py) makes **only a relief mesh**, from a reviewed XY polygon in millimetres. It does not read an image, project onto a curved surface, edit a 3MF, detect open documents, assign materials, or slice. Install [requirements.txt](requirements.txt) separately. Its [synthetic mask](examples/shield-mask.json) preserves a central functional opening.

~~~sh
python scripts/build_relief.py examples/shield-mask.json /tmp/highlight.stl \
  --mode outline --width 0.85 --surface-z 3 --rise 0.64 --root 0.40
~~~

## Prove the saved result

Reread the candidate: check closed/wound solids, dimensions, surface registration, substrate and keepout clearance, colors and preserved project data. Invalidate affected embedded G-code and stale slice metadata. Slice affected production plates with the actual target engine.

Inspect **material-assigned extrusion paths inside the buried band and above the original surface**. Overlapping volumes can lose the buried color to slicer priority; change priority or partition geometry only after checking the actual engine. Geometry overlap, a configured slot and exit code 0 are three different observations. Repeat the slice after any priority edit.

Report the final path/hash, affected roots/plates, dimensions, slicer/version/exit code, observed root and surface paths, protected openings and any unverified result. Do not claim a screenshot, mesh check or successful slice proves physical bonding, appearance, removal or strength. Printing requires its own user request.

Run the included synthetic checks from this skill directory with `python -m unittest discover -s tests -v` after installing its requirements. These tests do not run a slicer.
