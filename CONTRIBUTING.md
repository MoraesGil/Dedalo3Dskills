# Contributing

Help us share small, useful skills for practical 3D printing.

## Propose a change

Open an issue for a printing problem, a reproducible bug or an idea for a new skill. Describe the expected result and the limits that matter. For a change to an existing skill, include the smallest example that shows why the change is needed.

Pull requests are welcome. Keep each one focused on a single problem.

## What a skill needs

- A clear trigger and scope in `SKILL.md`, including the geometry and project formats it can handle.
- Explicit contact zones, height limits and protected features when the skill creates supports or other geometry.
- Reusable helpers and a small reproducible check when code is needed.
- Honest validation: separate a geometry check, a successful slice, G-code inspection and a physical print.
- A catalog entry and usage example, with dependencies and compatibility limits.

Place read-only analysis skills under `skills/analysis/<skill-name>/` and print-preparation skills under `skills/printing/<skill-name>/`. Keep helpers in their owning skill and declare dependencies instead of duplicating them. Test both the categorized checkout and the flat sibling layout used by skill installers. Checkout-only entry points belong in `tools/dedalo3d/` and must remain thin wrappers.

Give each catalogued skill an original synthetic GIF under `assets/previews/`, a static PNG fallback and an entry in the preview catalog. Label concept diagrams clearly; a diagram is not evidence of slicing or a successful print. Keep the renderer reproducible and free of private fonts or models. Add focused references or examples when they make the skill easier to use.

## Use files that can be shared

Prefer synthetic fixtures that isolate one behavior. Include customer models or third-party assets only if you have explicit permission to redistribute them under terms compatible with this repository.

Keep personal data, credentials, local machine paths, private customer information, job history, proprietary presets and temporary work files out of commits. Screenshots and print photos also need redistribution permission. Review the staged files before opening a pull request.

## Check the result

Run the relevant tests and document what you observed. A support change needs checks of the saved project and a fresh slice in the engine being claimed as supported. Inspect contact, continuity, height, joint clearance and nearby objects or towers in the actual toolpaths. Report physical print results separately.

For a new engine or format, add a reproducible compatibility case. Do not generalize a successful test into support for every printer or material.

```text
Small reproducible case → focused change → relevant checks → clear validation limits
```

## License

Submit only work you have the right to contribute. Contributions are offered under this repository's [MIT license](LICENSE), which permits commercial use. Preserve copyright notices and license terms for any included third-party material.
