# Native flush allocation versus a single custom Burj

The custom Burj is a normal sacrificial object with per-tool complementary volumes. The native engine generates its walls and infill. The deterministic planner selects native object/tool order; the audit measures the final positive extrusion after every real toolchange. No G-code is rewritten.

`Flush into this object` and `Flush into objects' infill` are native object settings. Their tooltips state that they need the prime tower enabled. The stock engine's multi-nozzle path additionally calls `mark_wiping_extrusions()` only when both `purge_in_prime_tower` and `single_extruder_multi_material` are true. The U1 uses independent toolheads. Setting SEMM to true would misrepresent the printer and is not a supported fix.

Primary source, pinned to the locally tested engine's declared source commit:

- [Native flush settings and tooltips](https://github.com/Snapmaker/OrcaSlicer/blob/9bf2f18eaff7cc0655cbdeef6a215660085ecb0f/src/libslic3r/PrintConfig.cpp).
- [Multi-nozzle allocation gate in Print.cpp](https://github.com/Snapmaker/OrcaSlicer/blob/9bf2f18eaff7cc0655cbdeef6a215660085ecb0f/src/libslic3r/Print.cpp#L3430).
- [Overridable object/infill policy](https://github.com/Snapmaker/OrcaSlicer/blob/9bf2f18eaff7cc0655cbdeef6a215660085ecb0f/src/libslic3r/GCode/ToolOrdering.cpp).

This tool retains the two requested object checkboxes but reports `native_flush_effective=false`. The functional cleaning/priming path is the Burj's audited commanded extrusion. Passing explicit command checks reports `custom_commanded_priming_passed=true`. Active opaque firmware macros keep `firmware_semantics_verified=false`, `custom_priming_effective=null`, overall `passed=false` and exit code 2. No macro body is simulated or approved by its name. A fixture with only supported explicit G-code can pass the overall audit; that still does not prove a physical cleaning result or native allocation.

Turning the native tower on to activate these checkboxes is not an accepted substitute: it creates a separate physical tower. A synthetic installed-engine pilot with `prime_volume=12` generated `WIPE_TOWER_START` blocks at the native tower's independent position even though the Burj object already had both flush flags. `prime_volume=0` was rejected by the stock engine with exit code 238: its supported range starts at 1. The tool therefore provides no two-tower mode, no SEMM override and no postprocessed-G-code workaround.

The demonstration comparison and the unit regressions establish software behavior only. They do not establish PETG/PLA bed adhesion, mixed-material bonding or a universal minimum priming volume. Preserve the user's approved material temperatures and physical bed, and calibrate comparison budgets through actual prints.

The custom-only installed-engine comparison contained 152 equal phases and 72 real toolchanges. With the two object flags OFF or ON, executable command SHA-256 was identical: `90815eb47391110dc329c78da644253ee0afa07f97929cf64d935c9c36aa40a7`. Both had zero native `WIPE_TOWER_START` blocks and tower top equal to the last change at 16 mm. Explicit contour, infill, positive volume, order, temperature, speed and occupancy checks passed. The U1 output also contained active firmware macros, so the strict overall status remains partial (`firmware_unverified`). This is a synthetic digital comparison, not a production model or physical print.


## Native synthetic verification scope

The current portable adapter was exercised with two physical PETG slots and with a PETG shell plus PLA interface core. Each final saved 3MF was sliced again with the installed native engine, then read by the public CLI. Both cases passed the explicit command gates for 72 toolchanges and stopped at 16 mm. Both retained strict `status=firmware_unverified` and exit code 2 because active U1 firmware macro bodies were unavailable. No client model or real printer was used.

The native pilot used this command shape, with separate empty data/output directories and the selected executable supplied by the operator:

```sh
"$SNAPMAKER_ORCA_CLI" --allow-newer-file --slice 1 \
  --outputdir native-output --datadir native-data prepared-or-final.3mf
```

`--allow-newer-file` was explicit in this pilot because the installed CLI rejected the 2.4.1 application header without it. Do not silently change application metadata to bypass that check. Select and review the compatible native engine for production.

The recorded engine executable SHA-256 was `6a6d765161bfcf37649cbcd14833bdf36592457c7252acd0c980adaadfc16b7c`. Its operator-declared source commit was `9bf2f18eaff7cc0655cbdeef6a215660085ecb0f`. An executable hash does not independently prove a source-to-binary build mapping.
