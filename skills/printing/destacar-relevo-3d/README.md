# Raised relief

[Skill catalog](../../../README.md) · [Português brasileiro](README.pt-BR.md) · [Agent instructions and commands](SKILL.md)

A reference image can show the outline of an emblem. The part determines how high the outline can stand and how deep its coloured root can sit without reaching a hole. This skill connects the two measurements so the highlight has printable geometry above and inside the face.

## Turn an image into a raised outline

> Add a raised white outline around the shield on this plate. Match its width to the reference, keep the centre opening clear and show where the white filament prints below the surface.

1. Align the design to a measured edge on the target face. Mark the opening and check the wall thickness behind the outline. Choose a rise and a buried depth that fit that wall. [Image and surface registration](references/image-and-surface.md)
2. On a flat face, the optional helper turns a **reviewed polygon in millimetres** into a closed STL of the relief. The included shield example has a centre opening. A curved face needs a separate projection onto the measured surface. [Example polygon](examples/shield-mask.json) · [Planar helper](scripts/build_relief.py)
3. Add the relief to the existing 3MF assembly as a separate part assigned to the white filament slot. Preserve the hole, original paint and other components. Slice the saved project. Inspect **white extrusion below and above the original face**. If the slicer gives the buried layers to the base colour, correct the volume priority or partition the solids in the 3MF and slice again.

**Deliver the configured 3MF for print preparation.** A request for just the relief mesh on a flat face can end with the checked STL. Inspect the slicer's unchanged G-code in a temporary folder. A physical print shows how well the root bonds to the base, how the raised edge feels and how the colour looks.

[Concept illustration of the outline and buried root](../../../assets/previews/destacar-relevo-3d.gif)
