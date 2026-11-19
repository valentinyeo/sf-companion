#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path

from select_verifier_scope import parse_feature

SKILL = Path(".claude") / "skills" / "verify-sf-companion"
VERIFY = SKILL / "verify.mjs"
FEATURES = SKILL / "features"

JOURNEY_GROUP = re.compile(r"^const (\w*Journeys) = \[((?:.|\n)*?)\];", re.MULTILINE)
EMPTY_GROUP = re.compile(r"^const runEmpty = \[((?:.|\n)*?)\]\.some\(wants\);", re.MULTILINE)
LIVE_GROUP = re.compile(r'^const runLive = wants\("([a-z0-9][a-z0-9-]*)"\);', re.MULTILINE)
QUOTED_ID = re.compile(r'"([a-z0-9][a-z0-9-]*)"')


def launch_groups(source):
    groups = {}
    for name, body in JOURNEY_GROUP.findall(source):
        ids = set(QUOTED_ID.findall(body))
        if ids:
            groups[name] = ids
    empty = EMPTY_GROUP.search(source)
    if empty is not None:
        ids = set(QUOTED_ID.findall(empty.group(1)))
        if ids:
            groups["runEmpty"] = ids
    live = set(LIVE_GROUP.findall(source))
    if live:
        groups["runLive"] = live
    return groups


def listed_journeys(directory):
    listed = {}
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for journey in parse_feature(text)["journeys"]:
            listed.setdefault(journey, set()).add(path.name)
    return listed


def check(root):
    verify = Path(root) / VERIFY
    directory = Path(root) / FEATURES
    if not verify.is_file():
        return [
            f"{VERIFY.as_posix()} is missing, so no journey can be checked against the launch groups. Fix: restore the runner or point scripts/check_journey_launch.py at the file that launches the states."
        ]
    if not directory.is_dir():
        return [
            f"{FEATURES.as_posix()} is missing, so no journey id can be read. Fix: restore the feature map."
        ]
    groups = launch_groups(verify.read_text(encoding="utf-8"))
    if not groups:
        return [
            f"{VERIFY.as_posix()} declares no launch group of journey ids. A journey with no launch group starts no state, so a scoped run of it fails. Fix: restore the `Journeys` arrays and the `runEmpty` and `runLive` gates."
        ]
    launched = {}
    for name, ids in groups.items():
        for journey in ids:
            launched.setdefault(journey, []).append(name)
    listed = listed_journeys(directory)
    errors = []
    for journey in sorted(set(listed) - set(launched)):
        files = ", ".join(f"`{FEATURES / name}`" for name in sorted(listed[journey]))
        errors.append(
            f"`{journey}` is listed in {files} but no launch group in {VERIFY.as_posix()} names it, so `run.sh --journeys={journey}` starts no state, records no action, and fails the run. Fix: add it to the launch group that seeds the state it drives, or move the check to a journey that is launched."
        )
    for journey in sorted(set(launched) - set(listed)):
        names = ", ".join(f"`{name}`" for name in sorted(launched[journey]))
        errors.append(
            f"`{journey}` sits in launch group {names} in {VERIFY.as_posix()} but no feature file lists it, so `run.sh --journeys={journey}` rejects it as unknown and no run can select it. Fix: list it as a sub-feature, or drop it from the launch group."
        )
    if errors:
        return errors
    print(f"journey launch: {len(listed)} journeys across {len(groups)} launch groups")
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    args = parser.parse_args()
    errors = check(args.root)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
