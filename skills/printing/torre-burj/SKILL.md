---
name: torre-burj
description: Create and audit one Burj Khalifa inspired priming tower from a saved native Snapmaker Orca 3MF and its fresh prepass G-code. Use for PLA, PETG or their physical material combinations, multiple object sizes, broad adhesion, and a tower that stops at the last real toolchange. Measure complete contour and infill before every product or support pass; preserve approved temperatures and bed settings.
license: MIT
---

# Torre Burj

[English guide](README.md) · [Guia em português](README.pt-BR.md)

Build one sacrificial tower with a three-lobed footprint inspired by the **Burj Khalifa**. Its wide foundation improves available adhesion area. Its upper width follows the largest selected object's section at each height. Printed adhesion and cleaning still require a physical test.

For print preparation, deliver the configured, editable 3MF containing the tower, its material regions and native object order. Keep the native prepass and final G-code in a temporary directory for measurement and audit. Never write, patch or deliver custom G-code.

The tool is self-contained in `scripts/`. It needs Python 3.10+ and the standard library. It does not call a printer, install software, or send data to a service. Use an existing native Snapmaker Orca CLI to slice.

## Inputs and scope

Obtain the saved source 3MF, target production plate, selected product root IDs, physical material slots, size limits and any requested tower position. Use the project's approved bed, temperatures, cooling and quality settings. Do not substitute another printer or material to force a successful slice.

Inspect the geometry before planning. Use `analyze-3d-geometry` when available. A model of an architectural tower remains a product. Never remove it because its name contains “tower”. Remove only this tool's own hash-bound auxiliary. Ask for reviewed explicit removal of foreign/legacy auxiliaries.

Support one to four physical standard-flow PLA/PETG slots, including a PLA/PETG combination. An optional `interface_tool` creates a filled keyed core; it must be distinct from the model tools and already used externally at that height. Do not invent a new material change for tower growth. Recipe/mixed colour modes and adaptive/independent support layers need another validated backend.

## One physical tower and honest flags

Use **one Burj**, with native tower generation disabled. Persist `flush_into_objects=1` and `flush_into_infill=1` on the Burj object. These flags express the requested object role in the slicer UI. They do **not** perform native flush allocation in this mode.

On the Snapmaker U1's separate toolheads, the stock engine also gates native object flush allocation on `single_extruder_multi_material`. Do not change that printer identity to make the checkbox effective. Do not enable a second native tower.

The Burj performs commanded priming through its planned material regions and native object order. Validate positive extrusion, contour, infill and placement before the next product/support deposition after every real toolchange. Report these separately:

- `native_flush_effective: false` describes the checkbox's engine path.
- `custom_commanded_priming_passed: true` requires passing all explicit commanded G-code gates. `custom_priming_effective` stays null when active firmware macros have unverified semantics.
- `physical_cleaning_validated: false` remains false until a physical trial supplies that proof.

Read [native semantics](references/native-semantics.md) before changing the flags or adding a native mode.

## Procedure

1. Work on new paths with the document closed. Preserve the source. Prepare a native-off, tower-free prepass:
   ```sh
   python3 scripts/burj_tower.py prepare --input source.3mf --plate 1 --output prepass.3mf
   ```
2. Slice `prepass.3mf` with the approved native CLI. Keep its unmodified plain G-code (`prepass.gcode`) in the temporary working directory. The source and G-code hashes bind the plan. A hash alone does not prove which input a slicer used. Record the actual slicer command and executable hash.
3. Copy [options](references/options.example.json). Set IDs, tools, widths and any explicit constant-envelope foundation exception. Build from that exact prepass hash:
   ```sh
   python3 scripts/burj_tower.py build \
     --prepass-3mf prepass.3mf --prepass-gcode prepass.gcode \
     --expected-prepass-sha256 SHA256_FROM_PREPARE \
     --options options.json --output burj.3mf --receipt build.json
   ```
   Add `--engine-executable /path/to/native/slicer --engine-source-commit COMMIT` to record the selected engine. These arguments record provenance; they do not certify compatibility.
4. Slice the saved `burj.3mf` again with the same engine and plate. Do not edit painting, support, transforms, material settings or order between build and slice.
5. Audit the resulting plain G-code:
   ```sh
   python3 scripts/burj_tower.py audit \
     --project burj.3mf --gcode burj.gcode \
     --prepass-3mf prepass.3mf --prepass-gcode prepass.gcode --output audit.json
   ```
6. Exit code 0 plus `passed=true` confirms the implemented digital gates with no unverified active macro. Exit 2 means a gate failed or active firmware macros remain unverified. In the latter case, report `status=firmware_unverified` and the observed `commanded_gcode_passed` value. Exit 1 means the input or operation was invalid.
7. If deposition volume is insufficient, rebuild the tower in a new 3MF with `build --density-boost 5` or a reviewed comparison budget. For other failed checks, correct the 3MF and re-slice the affected plate. Audit the native slice of the rebuilt or corrected project. Report any unresolved check with the project.

## Geometry and audit rules

- Maximum width is twice minimum width. Brim is additional. The final width must be reached by the last real toolchange; never add a single-colour tail to finish tapering.
- Measure the maximum intrinsic section of selected objects **per labelled instance**. Distant copies do not form a bed-wide envelope. Include every product, support and native brim in occupancy and tool scheduling.
- Constant sections require explicit `foundation_height_mm`. `envelope_taper_power` 1–4 can bring taper forward after actual shrinkage. Reject an unsupported lateral step instead of creating an unstable shape.
- Filled, complementary nested regions leave no hollow core. Each active tool needs enough local width for its contour and infill.
- A real changed phase receives its complete measured explicit pass before any product/support. Unknown standard commands fail closed. Active opaque macros block overall approval; do not infer their motion or extrusion from their names. No visit after the product, empty tool selection, future-change prefill or new external colour is allowed.
- A no-change layer has target preparation volume zero and only the declared 5–25% structural infill. Measured structure is reported separately.
- Preserve external material schedule, exact phase signature and commanded temperature targets. Reject an enabled auxiliary fan.
- Check actual commanded bead occupancy, including native brim and arc margins. A conservative conflict is a rejection; it is not proof of a physical crash.
- Recompute after any geometry, painting, support, orientation, layout, temperature or slicing change. Slice and audit the exact 3MF being delivered before reporting it ready.

The ownership record and SHA-256 checks detect unintended changes. They are integrity tags, **not cryptographic signatures or authentication**.

Current bounded adapter rejects legacy ordinal-based range/cut/brim-ear payloads. It preserves native layer-height profiles only in format version 2; the tower still requires a constant common layer grid. Review and convert unsupported inputs instead of dropping their metadata.
