# PrenderPolvo3D

[Skill catalog](../../../README.md) · [Português brasileiro](README.pt-BR.md) · [Agent instructions and commands](SKILL.md)

The centre of an articulated octopus needs support, while the gaps between its arm segments need to stay open. PrenderPolvo3D adapts Prender3D to one eight-arm design family. It places **eight low contacts between the arms and one inside the fixed body**, clear of the socket.

## Prepare a compatible octopus

> Check whether my octopus matches the supported geometry. If it does, brace only the lowest 3 mm of the fixed base. Leave the tentacle joints and socket clear, with no brim on the octopus or the support tree.

1. Install PrenderPolvo3D alongside Prender3D. Run the detector on the complete, saved Orca/Bambu-family 3MF. The command-line editor acts on **all matching assemblies** in the file. If the request covers just one of several matches, use the Python API with its root ID. [Detector](scripts/detect_octopus.py) · [Prender3D guide](../prender-3d/README.md)
2. Close the saved project before staging the native support masks. Eight blockers protect the arms. An upper blocker follows the fixed body. The reference ceiling of 3 mm is measured from the bed along the **common base**. The height of a decorative head can vary independently.
3. In a fresh native slice, trace all nine supports from the bed to the fixed body. Check contact above the first layer, the highest support layer, the open socket and each joint on every copy. On the first layer, verify that the slicer omitted brim around the octopus and the support tree.

Save the accepted changes in the current project and reslice. **Deliver the prepared 3MF** with its articulated geometry, paint and placement preserved. Keep the slicer's G-code temporary and inspect it unchanged. A small physical print checks whether the support comes away cleanly and the arms move freely.

[Concept illustration of the nine contacts](../../../assets/previews/prender-polvo-3d.gif)
