#!/usr/bin/env python3
import re
import sys
from pathlib import Path

FOLDER = Path(".github") / "workflows"
SCOPED = "pstack-verifier.yml"
NIGHTLY = "nightly-journeys.yml"
BROWSER = re.compile(r"verify-sf-companion/run\.sh|playwright|chromium", re.IGNORECASE)
PULL_TRIGGERS = {"pull_request", "pull_request_target"}
TRIGGER = re.compile(r"^  ([A-Za-z_][A-Za-z0-9_-]*):")
INLINE = re.compile(r"^on:\s*(.+?)\s*$")
INLINE_VALUE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
QUOTING = re.compile(r"[\"'\\]")


def inline_triggers(value):
    return set(INLINE_VALUE.findall(value.split("#", 1)[0]))


def triggers(source):
    found = set()
    inside = False
    for line in source.split("\n"):
        if not inside:
            match = INLINE.match(line)
            if match is not None:
                found.update(inline_triggers(match.group(1)))
                inside = True
            elif re.fullmatch(r"on:\s*", line):
                inside = True
            continue
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            break
        match = TRIGGER.match(line)
        if match is not None:
            found.add(match.group(1))
    return found


def read(folder, name):
    path = folder / name
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def check_pull_requests(folder, workflows):
    errors = []
    for name, source in workflows.items():
        if triggers(source) & PULL_TRIGGERS == set():
            continue
        if name == NIGHTLY:
            errors.append(
                f"{NIGHTLY} triggers on pull requests. The full journey suite costs more than a pull request should pay and its failures block every change. Fix: drop `pull_request` from the `on` block so `schedule` and `workflow_dispatch` stay the only entries."
            )
            continue
        if name == SCOPED:
            if "--journeys=" not in source:
                errors.append(
                    f"{SCOPED} drives journeys on pull requests without `--journeys`. A full suite per pull request spends the job budget the cheap path protects and hides which journey the change touched. Fix: pass the selector's list, as `--journeys=$JOURNEYS`."
                )
            continue
        match = BROWSER.search(source)
        if match is not None:
            errors.append(
                f"{name} runs `{match.group(0)}` on pull requests. A browser run there is slow, flaky for reasons the change did not cause, and already covered by {SCOPED} and {NIGHTLY}. Fix: move the step into {NIGHTLY}, or leave only the scoped `--journeys` run in {SCOPED}."
            )
    return errors


def check_nightly(folder):
    source = read(folder, NIGHTLY)
    if source is None:
        return [
            f"{NIGHTLY} is missing. Nothing then drives every journey on the default branch, so the only proof of a full run is the scoped pull request path. Fix: add `{FOLDER / NIGHTLY}` with `schedule` and `workflow_dispatch`."
        ]
    errors = []
    found = triggers(source)
    if "schedule" not in found:
        errors.append(
            f"{NIGHTLY} has no `schedule` trigger. A nightly that only runs when a person dispatches it stops proving the full suite the day the schedule is dropped. Fix: add `schedule` with a `cron` entry to its `on` block."
        )
    if "workflow_dispatch" not in found:
        errors.append(
            f"{NIGHTLY} has no `workflow_dispatch` trigger. Without it the suite cannot be re-run by hand after a failure. Fix: add `workflow_dispatch` to its `on` block."
        )
    if "refs/heads/main" not in source:
        errors.append(
            f"{NIGHTLY} never names `refs/heads/main`. A run on a feature branch proves nothing about the default branch and races the work there. Fix: guard the job with `github.ref == 'refs/heads/main'` and keep `workflow_dispatch` for the hand-started proof."
        )
    if "verify-sf-companion/run.sh" not in source:
        errors.append(
            f"{NIGHTLY} never runs `verify-sf-companion/run.sh`. The workflow then proves something other than the journeys it exists for. Fix: run `.claude/skills/verify-sf-companion/run.sh` in a step."
        )
    if "cancel-in-progress: true" not in source:
        errors.append(
            f"{NIGHTLY} never sets `cancel-in-progress: true`. A superseded nightly then keeps a runner busy and its files upload beside the newer proof. Fix: add `concurrency` with `cancel-in-progress: true`."
        )
    if "--journeys" in QUOTING.sub("", source):
        errors.append(
            f"{NIGHTLY} narrows its run with `--journeys`, quoted or not. A nightly that drives a subset leaves the journeys it dropped driven by nobody, and the map then claims coverage no run checks. Fix: run `.claude/skills/verify-sf-companion/run.sh --live` with no journey selector."
        )
    if "actions/upload-artifact" not in source:
        errors.append(
            f"{NIGHTLY} uploads no proof. A failed case then leaves nothing to read, and the run only says something broke. Fix: upload the `PROOF_DIR` directory with `actions/upload-artifact` and `if: always()`."
        )
    return errors


def check(root):
    folder = Path(root) / FOLDER
    if not folder.is_dir():
        return [
            f"`{FOLDER.as_posix()}` is missing. No workflow scope can be read, so a browser could slip back onto pull requests. Fix: restore {FOLDER.as_posix()} and its workflows."
        ]
    workflows = {}
    for path in sorted(folder.iterdir()):
        if path.suffix in {".yml", ".yaml"} and path.is_file():
            workflows[path.name] = path.read_text(encoding="utf-8")
    return check_pull_requests(folder, workflows) + check_nightly(folder)


def main():
    errors = check(Path(__file__).resolve().parent.parent)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
