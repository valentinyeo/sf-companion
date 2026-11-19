#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from select_verifier_scope import read_features

BUG_LABEL = "bug"
FIX_TITLE = re.compile(r"(?i)^fix\b")
REPRO_LINE = re.compile(r"(?i)^\s*repro journey:\s*(.*)$")
APP_ROOTS = ("apps/", "packages/")
TEST_FILE = re.compile(
    r"(^|/)(test|tests|__tests__)/"
    r"|\.(test|spec)\.[cm]?[jt]sx?$"
    r"|(^|/)test_[^/]*\.py$"
    r"|(^|/)[^/]*_test\.py$"
)
JOURNEY_HARNESS = ".claude/skills/verify-sf-companion/"
FEATURES_DIR = ".claude/skills/verify-sf-companion/features"


def git(root, *arguments):
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env={
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_")
        },
    )
    if completed.returncode != 0:
        raise RuntimeError(
            completed.stderr.strip() or completed.stdout.strip() or "git failed"
        )
    return completed.stdout


def is_bug_pr(title, labels):
    lowered = {label.strip().lower() for label in labels if label.strip()}
    return BUG_LABEL in lowered or FIX_TITLE.match(title.strip()) is not None


def repro_journeys(body):
    found = []
    for line in body.splitlines():
        match = REPRO_LINE.match(line)
        if match is None:
            continue
        for part in match.group(1).split(","):
            value = part.strip().strip("`")
            if value:
                found.append(value)
    return found


def known_journeys(root):
    directory = Path(root) / FEATURES_DIR
    if not directory.is_dir():
        raise RuntimeError(
            f"`{FEATURES_DIR}` is missing, so no repro journey can be checked. Fix: restore the verification map."
        )
    return {journey for feature in read_features(directory) for journey in feature["journeys"]}


def test_path(path):
    return TEST_FILE.search(path) is not None or path.startswith(JOURNEY_HARNESS)


def app_path(path):
    return path.startswith(APP_ROOTS) and TEST_FILE.search(path) is None


def commit_order(root, base, head):
    try:
        log = git(
            root,
            "log",
            "--reverse",
            "--no-merges",
            "--format=%H",
            f"{base}..{head}",
        )
    except RuntimeError as error:
        raise RuntimeError(
            f"The branch order cannot be read from `{base}..{head}`: {error}. Fix: pass the pull request base and head SHAs."
        ) from error
    shas = [line.strip() for line in log.splitlines() if line.strip()]
    if not shas:
        raise RuntimeError(
            f"The branch order cannot be read: `{base}..{head}` holds no commit. Fix: pass the pull request base and head SHAs."
        )
    commits = []
    for sha in shas:
        entries = []
        for line in git(
            root, "show", "--name-status", "--no-renames", "--format=", sha
        ).splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            entries.append((parts[0].strip(), parts[1].strip()))
        commits.append({"sha": sha, "paths": entries})
    return commits


def first(commits, wants):
    for commit in commits:
        for status, path in commit["paths"]:
            if status.startswith("D"):
                continue
            if wants(path):
                return commit["sha"], path
    return None


def first_app_commit(commits):
    for commit in commits:
        for path in (path for _, path in commit["paths"]):
            if app_path(path):
                return commit["sha"], path
    return None


def read_body(path):
    return Path(path).read_text(encoding="utf-8")


def check(root, title, labels, body, base, head):
    if not is_bug_pr(title, labels):
        print("bug pr: not a bug fix, nothing to check")
        return []

    errors = []
    known = known_journeys(root)
    requested = repro_journeys(body)
    if not requested:
        errors.append(
            f'"{title}" is a bug fix but its body names no repro journey. A bug fix with no failing journey proves nothing about the bug. Fix: add the line `Repro journey: <id>` to the pull request body, where `<id>` is a journey in `{FEATURES_DIR}`.'
        )
    for journey in requested:
        if journey not in known:
            errors.append(
                f'Repro journey "{journey}" is not in the verification map, so no run drives it. Fix: list the journey in its feature file as a sub-feature, gate it in `verify.mjs`, or name one of: {", ".join(sorted(known))}.'
            )
    if errors:
        return errors

    commits = commit_order(root, base, head)
    order = [commit["sha"] for commit in commits]
    failing = first(commits, test_path)
    app = first_app_commit(commits)
    if failing is None:
        errors.append(
            "No commit on this branch adds a failing test. A fix that lands without its test can never be shown to fix anything. Fix: commit the failing test or repro journey first, then the fix on top."
        )
        return errors
    if app is not None and order.index(app[0]) < order.index(failing[0]):
        errors.append(
            f"The commit that changes app code `{app[1]}` ({app[0][:10]}) comes before the first commit that adds the failing test `{failing[1]}` ({failing[0][:10]}). A fix that lands before its test was never seen to fail. Fix: reorder the branch so the failing test or journey lands first, then the fix on top."
        )
    if errors:
        return errors
    print(
        f"bug pr: repro journey {', '.join(requested)}; failing test {failing[0][:10]} lands before the fix {app[0][:10] if app else 'none'}"
    )
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="")
    parser.add_argument("--labels", default="")
    parser.add_argument("--body-file", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    args = parser.parse_args()
    try:
        errors = check(
            args.root,
            args.title,
            args.labels.split(","),
            read_body(args.body_file),
            args.base,
            args.head,
        )
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
