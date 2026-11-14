# Analyze 3D geometry

[Skill catalog](../../../README.md) · [Português brasileiro](README.pt-BR.md) · [Agent instructions and commands](SKILL.md)

A handle can look wide from above and touch the bed only on a narrow rim. Its overall dimensions include the empty space inside the rim. This skill measures a horizontal section through the first layer so you can choose support contacts from the geometry of the saved assembly.

## Ask for a measurement

> My handle has an open socket. Use its configured first-layer height. For each copy, show how much material crosses that layer and flag any incomplete sections. Leave the project as it is.

1. Supply a saved Orca/Bambu-family 3MF with its project metadata. Install the skill alongside Prender3D for its shared geometry reader. [Installation](../../../README.md#install)
2. Set the first-layer height for that project. With a 0.20 mm first layer on a bed at Z = 0, the reader cuts at Z = 0.10 mm. It applies the placement of each copy and subtracts the sections of any resolved negative volumes at that height.
3. In the JSON report, find the assembly and plate you asked about. Check `on_bed`, `section_complete` and `warnings` before using `net_geometric_area_mm2`. The recorded source hash identifies the measured 3MF.

**The result is a read-only geometry report.** The project stays intact. The section describes material at a single height. A native slice shows the lines the printer is asked to deposit. A physical test establishes adhesion.

[Concept illustration of the measurement](../../../assets/previews/analyze-3d-geometry.gif)
