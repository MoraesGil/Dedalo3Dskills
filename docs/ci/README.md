# Optional GitHub Actions checks

[Back to the catalog](../../README.md)

[validate.yml](validate.yml) is a ready-to-use workflow for Python 3.12 on a standard GitHub-hosted Ubuntu runner. It installs the declared dependencies, validates public skill metadata and documentation links, and runs the synthetic test suite. The two GitHub actions are pinned to exact official release commits.

A workflow stored under docs does not run automatically. To enable it in your own repository:

1. Copy this file to `.github/workflows/validate.yml`.
2. Commit it with credentials authorized to write workflows. OAuth credentials need the `workflow` scope; GitHub Apps need the corresponding workflow permission.
3. Push and inspect the resulting Actions run before claiming a passing build.

You can run the same checks locally without GitHub credentials:

    python -m pip install -r skills/printing/prender-3d/requirements.txt
    python scripts/validate_repository.py
    python -m unittest discover -s tests -v

These checks exercise synthetic projects. They do not invoke a slicer or printer.
