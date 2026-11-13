# Validate with the native slicer

[Retention workflow](retention-workflow.md) · [Compatibility](compatibility.md)

Keep the project closed during external editing. Use the saved 3MF and the printer, materials and plate that it already defines. This package does not bundle or download a slicer.

For Snapmaker Orca, the reference engine's CLI accepts this structure:

```bash
# Set this to your installed Snapmaker Orca executable.
# SNAPMAKER_ORCA_BIN is a user-supplied path, not a bundled binary.
retention_run_dir="$(mktemp -d)"
mkdir -p "$retention_run_dir/output" "$retention_run_dir/profile" "$retention_run_dir/tmp"

TMPDIR="$retention_run_dir/tmp/" "$SNAPMAKER_ORCA_BIN" \
  --slice 1 \
  --outputdir "$retention_run_dir/output" \
  --datadir "$retention_run_dir/profile" \
  retained.3mf
```

Use an absolute path for `retained.3mf` and select the correct 1-based plate number. Verify the flags with the installed engine's help. The reference native build used during development was `9bf2f18`; different versions require their own checks.

Do not add a newer-file compatibility override unless you have assessed that source format against the target engine. Do not substitute another printer or discard embedded settings just to get an exit code.

Keep the output G-code and native diagnostics in a temporary run folder while evaluating. Inspect the complete paths and then publish only the accepted 3MF/G-code. No physical printer operation is part of this command.

Record the executable version/hash, source 3MF hash, command, plate and exit code. Compare what the project requested with what the output actually commands, including native support features, material slots, temperatures and fans.

For GUI-only slicers, open the staged copy for inspection, preserve the source document, and close the copy when finished. A visual support preview complements measurements; it does not replace toolpath or physical validation.

See the official [Snapmaker Orca repository](https://github.com/Snapmaker/OrcaSlicer) for the installed product's documentation.
