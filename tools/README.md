# Deterministic tools

These commands are thin entry points for a **repository checkout**. Algorithms live inside their owning skills so a skill installation carries its own implementation. Python 3.12 and the [shared geometry requirements](../skills/printing/prender-3d/requirements.txt) are tested.

| Wrapper | Owning skill | Operation |
| --- | --- | --- |
| `python tools/dedalo3d/geometry_preflight.py --help` | [Analyze 3D geometry](../skills/analysis/analyze-3d-geometry/SKILL.md) | Read-only sections and project inventory. |
| `python tools/dedalo3d/footprint.py --help` | [Custom footprint](../skills/printing/custom-footprint/SKILL.md) | Parameterized native-mask JSON plan. |
| `python tools/dedalo3d/relief.py --help` | [Destacar relevo 3D](../skills/printing/destacar-relevo-3d/SKILL.md) | Reviewed planar polygon to raised STL; install its own requirements. |
| `python tools/dedalo3d/burj.py --help` | [Burj tower](../skills/printing/torre-burj/SKILL.md) | `prepare`, `build`, and `audit`, using actual prepass G-code. |

For retention application, use [apply_retention.py](../skills/printing/prender-3d/scripts/apply_retention.py). It accepts only reviewed retention settings. Its source hash, explicit root, temporary output and process validation are part of the guarded CLI contract.

## Source checkout versus installed skills

From a checkout, run wrappers from the repository root. With `npx skills`, use the scripts inside the installed skill, at the path selected by the installer. Install `prender-3d` beside skills that depend on it. Their resolvers support the categorized repository and flat sibling installation layouts.

Do not copy only a wrapper out of the repository: it has no independent implementation. Do not rename dependency directories without updating their explicit imports.

## Burj inputs and proof

The Burj calculator takes a **complete saved 3MF**, its **fresh tower-free G-code**, reviewed options and expected source hash. The workflow is:

```text
prepare 3MF → native prepass slice → build Burj → native final slice → audit
```

Read the [Burj instructions and examples](../skills/printing/torre-burj/SKILL.md) for exact commands. The tool does not fabricate a tower plan from a guessed model height and does not rewrite G-code after slicing. Source hashes bind artifacts; they do not prove which process produced a caller-supplied G-code.

The final audit compares the bound external tool sequence, tower passages and extrusion volume. It is a focused digital check, not a printer or universal collision certification. Materials retain their existing settings. Physical cleaning, adhesion and removal require a test print.

## Concept preview renderer

```bash
python -m pip install -r tools/requirements-previews.txt
python tools/render_previews.py
```

This optional renderer produces five procedural GIFs and preserves the contributed relief GIF and poster byte-for-byte. It writes the six-entry catalog and collection banner. It consumes no client models and makes no measurements of an actual print. See [preview details](../assets/previews/README.md).
