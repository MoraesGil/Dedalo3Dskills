# Dedalo3Dskills

[![License: MIT](https://img.shields.io/badge/License-MIT-64e3a6.svg)](LICENSE) · [Português brasileiro](README.pt-BR.md) · [All six skills](#skill-catalog) · [Install](#install)

Prepare an editable print project. These skills solve problems we ran into at the printer: a purge tower that breaks halfway up a tall part, a handle that rocks on the bed, or support that locks a joint. **For print preparation, the file you get back is the configured `.3mf`.** You can open it and slice it again. Only the slicer writes G-code; the skills read a temporary slice to check the result.

## Burj tower: a purge tower worth keeping

Ever lost a purge tower halfway through a tall print? We built **Burj** for that moment. Inspired by the **Burj Khalifa**, it starts with a broad, three-lobed base and narrows as the selected part gets slimmer. The base gives the tower more contact with the bed. After the last tool change, the part can keep growing without the tower. When you lift the tower off the plate, you can keep it as a miniature building.

[![Technical illustration of a tall part beside its Burj tower. The tower has a broad three-lobed base and a narrower top that stops below the part.](assets/previews/burj-tall-print.svg)](assets/previews/burj-tall-print.svg)

*In this example, the vase is 184.8 mm tall. The green Burj is 48 mm wide at the base and 24 mm at the top. It stops at the last tool change, at Z = 144 mm.*

We've used **PETG for the part and PLA for the support interface in the same print**, on separate physical toolheads. After each real change, the new tool prints a full pass on the Burj before touching the part or its support. The native prime tower stays off: there is only one tower on the plate.

[See the tower up close, the PETG/PLA setup and what was tested →](skills/printing/torre-burj/README.md)

## Prender3D: keep a tall handle steady

A tall handle can rock even when its first layer looks good. A wider brim helps at bed level but does not brace the wall above it. We built **Prender3D** to place low, removable slicer support against the *fixed* sides of the part. You choose which walls can take contact marks and which sockets, threads or joints must stay clear. The part keeps its original shape.

[See where the supports touch and how to check the contact →](skills/printing/prender-3d/README.md)

## Skill catalog

Open a skill name for its story, an example request and the result to expect. Click a thumbnail to enlarge the illustration or play the animation.

| Preview | Skill guide | When to use it |
| --- | --- | --- |
| [<img src="assets/previews/burj-tall-print.svg" width="156" alt="Burj tower beside a tall part">](assets/previews/burj-tall-print.svg) | [Burj tower](skills/printing/torre-burj/README.md) | Add one purge/priming tower matched to the part and its actual tool changes. |
| [<img src="assets/previews/prender-3d.gif" width="156" alt="Low supports on a handle">](assets/previews/prender-3d.gif) | [Prender3D](skills/printing/prender-3d/README.md) | Brace fixed walls without filling the socket or adding a solid base. |
| [<img src="assets/previews/analyze-3d-geometry.gif" width="156" alt="A cross-section through a part">](assets/previews/analyze-3d-geometry.gif) | [Analyze 3D geometry](skills/analysis/analyze-3d-geometry/README.md) | Measure the first-layer section and identify what must stay clear. Read-only report. |
| [<img src="assets/previews/custom-footprint.gif" width="156" alt="Contact zones around a footprint">](assets/previews/custom-footprint.gif) | [Custom footprint](skills/printing/custom-footprint/README.md) | Plan exactly where support may touch. The planner returns a JSON plan. |
| [<img src="assets/previews/prender-polvo-3d.gif" width="156" alt="Protected octopus joints">](assets/previews/prender-polvo-3d.gif) | [PrenderPolvo3D](skills/printing/prender-polvo-3d/README.md) | Hold the fixed body of a compatible octopus while leaving its eight arms free. |
| [<img src="assets/previews/destacar-relevo-3d.gif" width="156" alt="An outline raised from a part">](assets/previews/destacar-relevo-3d.gif) | [Raised relief](skills/printing/destacar-relevo-3d/README.md) | Turn a reference outline into a raised detail in the project. The planar helper makes an intermediate STL. |

The illustrations show the intended geometry. The [animation gallery](assets/previews/README.md) also has static versions; these are not print photos or slicer recordings.

## Slice without opening the GUI

Our [Snapmaker Orca MCP and Bash launcher](https://github.com/MoraesGil/snapmaker-orca-mcp) use the **native Snapmaker Orca engine installed on your Mac**. Select the saved `.3mf` and its production plate. The agent can run `slice_3mf`, or you can run the launcher directly. This saves the time spent opening the GUI, picking the plate and exporting it again for each change. [See the command and MCP example](docs/slicing.md).

Inspect the native slice. If the paths are wrong, correct the **project** and slice it again. Hand over the saved `.3mf` that reproduces the intended paths; keep validation G-code in the working folder.

## Install

Use the [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills@latest add MoraesGil/Dedalo3Dskills --skill analyze-3d-geometry custom-footprint prender-3d prender-polvo-3d torre-burj destacar-relevo-3d
```

Choose your agent when prompted. Installation is project-local by default. Analysis, footprint and octopus skills reuse `prender-3d`. For custom footprints, also install `analyze-3d-geometry`. Burj is self-contained. Install the dependencies named in each skill; the installer may not resolve them automatically.

For a checkout, create a Python virtual environment and install the geometry dependencies:

```bash
git clone https://github.com/MoraesGil/Dedalo3Dskills.git
cd Dedalo3Dskills
python -m pip install -r skills/printing/prender-3d/requirements.txt
```

Raised relief has [its own Python requirements](skills/printing/destacar-relevo-3d/requirements.txt). Python 3.12 is tested. Read the relevant `SKILL.md` before running helpers. No slicer, printer preset or printer connection is bundled.

## Repository layout

```text
skills/analysis/<name>/       Read-only inspection skills
skills/printing/<name>/       Print-preparation skills
  README*.md                 Skill guide in English and Brazilian Portuguese
  SKILL.md                   Agent instructions, scope and workflow
  scripts/                   Owning implementation, included in skill installation
  references/ or examples/   Detailed contracts and inputs where needed
tools/dedalo3d/               Thin checkout-only command wrappers
assets/previews/             Concept GIFs, static posters and catalog
tests/                       Synthetic fixtures and checks
```

Algorithms stay with their owning skill; wrappers do not duplicate them. [Tools and commands](tools/README.md) explain checkout and installed-skill layouts.

## Compatibility and checks

Project helpers target **complete Orca/Bambu-family 3MF projects with metadata**, not bare STL or mesh-only 3MF. The reference native engine is **Snapmaker Orca**. Other engines need their own compatibility check.

Tests cover synthetic geometry, metadata preservation and planning/audit invariants. Burj also has a small native U1 pilot: explicit-command checks passed, while opaque firmware macros leave the strict overall audit incomplete. These checks do not prove physical adhesion, joint freedom or cleaning on every material. Inspect final toolpaths and test a small physical print.

Read [compatibility](docs/compatibility.md), the [retention workflow](docs/retention-workflow.md) and [native slicing](docs/slicing.md). No tool starts or controls a printer.

```bash
python -m pip install -r requirements-dev.txt
python scripts/validate_repository.py
python -m unittest discover -s tests -v
```

Tests create projects in temporary folders. The optional [GitHub Actions recipe](docs/ci/README.md) is under `docs/ci`; it is not active CI. Preview rendering has a separate optional Pillow dependency.

## More skills to curate

Our local 3D garden also has candidates for PETG interface bridges, added weight, fragility review, multiview paint auditing and general print preparation. Each needs a focused public export and license review before joining the catalog. No placeholder skill or private customer model is included.

Contribute a concrete printing problem, bounded skill and reproducible check. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License and inspiration

Original skills, code, illustrations and documentation use **[MIT](LICENSE)**, permitting commercial use, modification and redistribution under its terms. Models, dependencies and printer software keep their licenses. [Burj NOTICE](skills/printing/torre-burj/NOTICE.md) records the limited provenance of the exported Burj modules.

The organization is inspired by [Matt Pocock's skills repository](https://github.com/mattpocock/skills): focused skills, a clear catalog and a short path to use. The Burj shape takes inspiration from the Burj Khalifa. Our print-preparation tools and synthetic illustrations are original work.
