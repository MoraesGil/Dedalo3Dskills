"""Validate public skill metadata, local documentation links and publication hygiene."""
from pathlib import Path
import json
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main():
    failures = []
    skills = list((ROOT / "skills").rglob("SKILL.md"))
    names = []
    for path in skills:
        text = path.read_text()
        if not text.startswith("---\n") or "\n---\n" not in text[4:]:
            failures.append((str(path.relative_to(ROOT)), "missing frontmatter"))
            continue
        front = text.split("---", 2)[1]
        found = {key: re.search(r"^" + key + r":\s*(.+)$", front, re.M)
                 for key in ("name", "description", "license")}
        if any(value is None for value in found.values()):
            failures.append((str(path.relative_to(ROOT)), "name, description and license required"))
            continue
        name = found["name"][1].strip()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64 or name != path.parent.name:
            failures.append((str(path.relative_to(ROOT)), "invalid skill name or directory"))
        if len(found["description"][1]) > 1024:
            failures.append((str(path.relative_to(ROOT)), "description too long"))
        if found["license"][1].strip() != "MIT":
            failures.append((str(path.relative_to(ROOT)), "skill license must match repository MIT license"))
        names.append(name)
    if not skills or len(names) != len(set(names)):
        failures.append(("skills", "missing skills or duplicate names"))

    private_roots = ("/" + "Users/", "/" + "Volumes/", "file:" + "//")
    secret_patterns = (
        re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
        re.compile(r"AKIA[A-Z0-9]{16}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    )
    excluded = {".git", ".venv", "__pycache__", ".agents", ".claude", "node_modules"}
    banned_suffixes = {".3mf", ".stl", ".obj", ".gcode", ".step", ".stp", ".zip"}
    count = 0
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if not path.is_file() or any(part in excluded for part in relative.parts):
            continue
        count += 1
        if path.suffix.lower() in banned_suffixes or path.name == "garden.json":
            failures.append((str(relative), "private/generated model or local registry metadata is not a public fixture"))
        if path.suffix.lower() not in {".md", ".py", ".txt", ".json", ".svg", ".yml", ".yaml"}:
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            failures.append((str(relative), "expected UTF-8 text"))
            continue
        if any(marker in text for marker in private_roots):
            failures.append((str(relative), "machine-specific path found"))
        if path.name != Path(__file__).name and any(pattern.search(text) for pattern in secret_patterns):
            failures.append((str(relative), "possible secret; inspect locally without printing it"))
        if path.suffix == ".md":
            for target in re.findall(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)", text):
                target = target.strip("<>")
                parsed = urlsplit(target)
                if parsed.scheme or not parsed.path:
                    continue
                resolved = (path.parent / unquote(parsed.path)).resolve()
                if not resolved.is_relative_to(ROOT) or not resolved.exists():
                    failures.append((str(relative), "broken or external local link: " + target))

    if "MIT License" not in (ROOT / "LICENSE").read_text():
        failures.append(("LICENSE", "MIT license missing"))
    result = {"passed": not failures, "skills": sorted(names), "files_checked": count,
              "failures": [{"file": file, "reason": reason} for file, reason in failures]}
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
