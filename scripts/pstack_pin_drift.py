#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

SKILL = Path(".claude/skills/verify-sf-companion/SKILL.md")
SOURCE = Path("pstack-source/pstack/.cursor-plugin/plugin.json")
RECORDED = re.compile(r"^pstack:\s*(\S+)\s*$", re.MULTILINE)


def recorded(skill_text):
    match = RECORDED.search(skill_text)
    return None if match is None else match.group(1)


def pinned(source_text):
    try:
        manifest = json.loads(source_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(manifest, dict):
        return None
    version = manifest.get("version")
    return version if isinstance(version, str) and version else None


def compare(skill_text, source_text):
    current = recorded(skill_text)
    if current is None:
        return [
            f"{SKILL.as_posix()} records no `pstack:` line, so the setup cannot be compared with the pinned pstack source. Fix: add `pstack: <version>` as a standalone line in that file."
        ]
    version = pinned(source_text)
    if version is None:
        return [
            f"{SOURCE.as_posix()} has no readable `version`, so the pinned pstack source cannot be compared. Fix: point `--source` at a pstack plugin manifest."
        ]
    if current != version:
        return [
            f"{SKILL.as_posix()} records pstack {current}, but the pinned pstack source is {version}. A newer pstack changes what the map and the journeys must cover, so the setup is stale. Fix: run `/maintain-verification-skill` against pstack {version}, then update the `pstack:` line."
        ]
    return []


def report(skill_path, source_path):
    skill = Path(skill_path)
    source = Path(source_path)
    errors = []
    if not skill.is_file():
        errors.append(
            f"{skill} is missing, so no pstack version is recorded. Fix: restore {SKILL.as_posix()} or pass `--skill`."
        )
    if not source.is_file():
        errors.append(
            f"{source} is missing, so the pinned pstack source cannot be read. Fix: check out cursor/plugins at the pinned commit and pass `--source`."
        )
    if errors:
        return errors
    return compare(skill.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill", default=SKILL.as_posix())
    parser.add_argument("--source", default=SOURCE.as_posix())
    args = parser.parse_args()
    errors = report(args.skill, args.source)
    for error in errors:
        print(error)
    if errors:
        return 1
    print(
        f"{SKILL.as_posix()} records pstack {recorded(Path(args.skill).read_text(encoding='utf-8'))}, matching the pinned source at {args.source}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
