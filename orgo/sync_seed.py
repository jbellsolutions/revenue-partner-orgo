#!/usr/bin/env python3
"""Install Revenue Partner's public profile without overwriting later owner edits."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync_tree(source: Path, target: Path, prior: dict[str, str], current: dict[str, str]) -> None:
    for source_file in sorted(path for path in source.rglob("*") if path.is_file()):
        relative = source_file.relative_to(source)
        target_file = target / relative
        key = target_file.as_posix()
        source_digest = digest(source_file)
        previous_digest = prior.get(key)
        replace = not target_file.exists()
        if target_file.exists() and previous_digest:
            replace = digest(target_file) == previous_digest
        if replace:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_file)
            current[key] = source_digest
        else:
            current[key] = previous_digest or digest(target_file)


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: sync_seed.py REPOSITORY_ROOT HERMES_HOME")
    root = Path(sys.argv[1]).resolve()
    hermes_home = Path(sys.argv[2]).resolve()
    hermes_home.mkdir(parents=True, exist_ok=True)
    marker = hermes_home / ".revenue-partner-orgo-profile"
    manifest_path = hermes_home / ".revenue-partner-orgo-seed.json"
    try:
        prior = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    except (OSError, ValueError):
        prior = {}
    current: dict[str, str] = {}

    soul = hermes_home / "SOUL.md"
    if not marker.exists():
        if soul.exists() and soul.read_bytes() != (root / "files/SOUL.md").read_bytes():
            shutil.copy2(soul, hermes_home / "SOUL.md.before-revenue-partner")
        shutil.copy2(root / "files/SOUL.md", soul)
        marker.write_text("Revenue Partner Orgo profile installed.\n")

    for source, target in (
        (root / "files/agent-knowledge", hermes_home / "agent-knowledge"),
        (root / "files/skills", hermes_home / "skills"),
        (root / "files/local-packages/super-browser/skills", hermes_home / "skills/browser"),
    ):
        sync_tree(source, target, prior, current)

    manifest_path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
