---
name: prender-polvo-3d
description: Specialize Prender3D for the supported articulated eight-arm octopus geometry pattern, with eight low lateral contacts, one internal contact, and protected tentacle joints. Use for PrenderPolvo3D; requires the sibling prender-3d skill.
license: MIT
---

# PrenderPolvo3D

Use [Prender3D](../prender-3d/SKILL.md) for its retention contract, source preservation, native slicing, and final validation. This specialization recognizes a narrow eight-arm geometry pattern and adds radial contact placement and tentacle keepouts. It does not turn an arbitrary octopus mesh into a supported design.

## Install the dependency

Install both prender-3d and prender-polvo-3d under the same parent directory. The scripts import the sibling helper directly. Installing only this directory is insufficient. Install Python requirements from the sibling prender-3d/requirements.txt. No separate local infrastructure, proprietary plugin, printer connector, or slicer is included.

## Confirm the geometry and region

Use [scripts/detect_octopus.py](scripts/detect_octopus.py) first. Detection requires eight regular radial chains, at least four distinct low-bed segments per arm, consistent radial rings, and a central body. Skull and Skeleton are explicit exclusions. The scale check is specific to the supported five-ring articulated family; another design or size needs a new geometry adapter and validation.

The reusable low profile has eight lateral contacts between the arms and one internal support, with a 3 mm support ceiling. **3 mm is a reference profile, not a measured half-height of every octopus.** Do not use half of the themed head. If the user requests a fraction, measure and identify the fixed retention-body region separately, then supply its actual height. Heights other than the reference 3 mm profile remain candidates requiring a contact/clearance design review.

- Keep intentional lateral contact on the fixed body. Protect the moving tentacles rather than moving every support away from the body.
- Keep the internal contact low and clear of a functional socket.
- The upper blocker is a circular band beginning at the support ceiling and extending 3 mm higher. Its radius comes from the fixed positive body inside that band, excluding the articulated chains, with a conservative discretization allowance. Check the mask against the purge tower and neighbours.
- Eight separate keepouts protect the measured tentacle directions. Preserve all existing functional negatives, geometry, paint, scale, pose, material assignments, and unrelated plates.
- The reference profile has no model, tentacle, or tree brim. Check the actual native first-layer paths; configuration alone does not establish this.

The enforcer is a slicing mask. It does not become a printable collar, base or support model. A circular upper blocker excludes contact points; it is not a physical cap that guarantees the tree stops there.

## Stage a candidate

The scripts require complete Orca/Bambu-family 3MF projects, millimetres, upright rigid builds seated on the bed, and configured multipart roots. Confirm the source is saved and closed, keep a backup, and bind its current SHA-256. The helper refuses to overwrite an existing output and writes only to the system temporary directory.

~~~sh
python scripts/detect_octopus.py source.3mf --compact
python scripts/apply_anchors.py source.3mf /tmp/octopus-candidate.3mf \
  --expect-sha256 CURRENT_SOURCE_SHA256 --height-mm 3
~~~

[scripts/apply_anchors.py](scripts/apply_anchors.py) applies to all geometrically matching roots in the source. Check the detection report before running it. Use its Python apply API when the authorized scope is a selected root. Reapplication preserves owned modifier IDs when the existing provenance and component scope are compatible; shared auxiliary assets outside that scope require an explicit adapter, not bypassing the ownership guard.

For a requested body fraction, use the mutually exclusive measured-region options instead of the explicit height:

~~~sh
python scripts/apply_anchors.py source.3mf /tmp/octopus-candidate.3mf \
  --expect-sha256 CURRENT_SOURCE_SHA256 \
  --body-height-mm MEASURED_FIXED_BODY_HEIGHT --height-ratio 0.5
~~~

Do not infer a region from the detector's top_z_local: that is the top of all positive geometry. The support ceiling, enforcer-band thickness and branch diameter remain separate parameters. Keep the physical support/interface filament selection explicit in the project and inspect it in the native slice.

## Required native gate

Supply the actual target slicer externally and slice the complete saved candidate. Verify all nine contacts from the first layer, low-body contact above that layer, continuity, the actual support ceiling, and no support in moving joints or sockets. Measure physical line widths and clearance across every support layer and every copy. Check zero brim on the octopus, tentacles and tree, plus clearance from towers, neighbours, bed boundaries and lift/travel paths.

The repository does not bundle a universal octopus G-code validator. Detection or helper exit code 0 proves neither support contact nor physical adhesion. Integrate only the reviewed delta into the current source and slice the final saved project again. Report hashes and digital checks separately from physical print results.

~~~text
Confirm the supported pattern → measure the fixed base → stage nine contacts
    → slice and verify joints, height and contact → physical print test
~~~
