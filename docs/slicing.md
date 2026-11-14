# Check the saved 3MF with Snapmaker Orca

[Skill catalog](../README.md#skill-catalog) · [Retention workflow](retention-workflow.md) · [Compatibility](compatibility.md)

The **configured 3MF is the print-preparation deliverable**. Use the target printer, materials and production plate stored in that project. Keep the document closed while editing it externally. The slicer generates validation G-code. If the paths are wrong, change the project and slice again. Never repair the G-code or publish it as a substitute for the project.

## With our launcher or MCP

The [snapmaker-orca-mcp project](https://github.com/MoraesGil/snapmaker-orca-mcp) calls the native engine in **your installed Snapmaker Orca on macOS**. It does not bundle a slicer or start a print. Both routes let you repeat a check without reopening the GUI, selecting the plate or exporting by hand.

**Bash** — from a checkout of *snapmaker-orca-mcp*, with Snapmaker Orca installed:

```sh
slice_run_dir="$(mktemp -d)"
bash bin/snapmaker-slice.sh "/absolute/path/prepared.3mf" 1 "$slice_run_dir/plate1.gcode"
```

Use the real project path and the 1-based production plate number. The output directory must exist and the filename must be new. This route needs no running MCP service.

**MCP** — in a client connected to `snapmaker-orca-mcp`, call the `slice_3mf` tool with:

```json
{
  "input_3mf": "/absolute/path/prepared.3mf",
  "plate": 1,
  "force": true,
  "allow_newer_file": false
}
```

Use a path visible to the MCP server. `force: true` requests a fresh slice; `allow_newer_file: false` keeps the native version check. The service returns paths and hashes for its working artifacts. They remain in its artifact store according to your installation; they are not delivery files. See the [MCP setup](https://github.com/MoraesGil/snapmaker-orca-mcp/blob/main/MACOS.md).

The [documented U1 pilot](../skills/printing/torre-burj/references/native-semantics.md#native-synthetic-verification-scope) is one known exception: the tested 2.4.1 application header needed the explicit Bash flag `--allow-newer-file` or MCP argument `allow_newer_file: true`. Keep the strict check for other inputs until their compatibility is established.

## With an existing native CLI

If you already invoke the engine directly, use separate working directories:

```sh
slice_run_dir="$(mktemp -d)"
mkdir -p "$slice_run_dir/output" "$slice_run_dir/profile" "$slice_run_dir/tmp"
TMPDIR="$slice_run_dir/tmp/" "$SNAPMAKER_ORCA_BIN" \
  --slice 1 \
  --outputdir "$slice_run_dir/output" \
  --datadir "$slice_run_dir/profile" \
  "/absolute/path/prepared.3mf"
```

Set `SNAPMAKER_ORCA_BIN` to your installed executable and check its supported flags. The [reference engine](https://github.com/Snapmaker/OrcaSlicer) used for the Burj pilot was build `9bf2f18`. If your engine rejects the project version, assess compatibility first. Do not change the printer or discard embedded settings to make the command pass.

## What to check

Record the saved project hash, engine version or hash, selected plate and native exit code. Inspect the paths that matter to the task: support contact and joint clearance for retention, material order and measured tower passages for Burj, or the root of a coloured detail for relief. Slicing successfully only proves the engine produced output.

For Burj, first slice the tower-free prepass. Build the tower **in the 3MF**, then slice that saved project on the same plate with the same engine. Compare the two native outputs as described in the [Burj instructions](../skills/printing/torre-burj/SKILL.md#procedure). Only the accepted, re-sliceable 3MF goes back to the user. A physical print is a separate check.
