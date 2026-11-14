# Custom footprint

[Skill catalog](../../../README.md) · [Português brasileiro](README.pt-BR.md) · [Agent instructions and commands](SKILL.md)

A rectangular support mask can extend across the empty corner of an L-shaped part and reach a neighbouring object. Custom footprint lets you choose a contour that follows the fixed body, place contacts at measured walls and reserve space for openings or joints.

## Plan the contact area

> Plan support for this L-shaped housing up to 3 mm high. Use the measured outline, place contacts on the fixed walls and keep the recess by the hinge clear. Show me the plan first.

1. Use a complete Orca/Bambu-family 3MF in millimetres. The assembly's copies must sit upright on the bed at their original scale. From the geometry report and the design, select the fixed components, contact directions and space the hinge needs to move. [Geometry guide](../../analysis/analyze-3d-geometry/README.md)
2. Choose the shape and set the height limit. The example uses a concave polygon and a protected area in the recess. Replace its measurements with those from your project. [Polygon example](examples/custom-polygon.json) · [Shape and clearance options](references/options.md)
3. Review the **JSON plan** and its report. Check the proposed contacts, rejected angles, upper blocker coverage and mask overlaps with nearby parts. The planner reads the 3MF. Its CLI writes a JSON **list** of native support enforcers and blockers to the regions file.

A planning request ends with the region list. For print preparation, pass that list to Prender3D with a separate, reviewed manual-support process. If you used the Python API, the list is in `result["regions"]`. In a fresh native slice, check line widths around the hinge. Support feet and brim can extend past the mask. Deliver the prepared **3MF** and keep the slicer's unchanged G-code in a temporary folder. A physical test checks hinge movement and support removal. [Prender3D guide](../prender-3d/README.md)

[Concept illustration of the support masks](../../../assets/previews/custom-footprint.gif)
