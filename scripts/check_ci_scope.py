#!/usr/bin/env python3
import re
import sys
from pathlib import Path

FOLDER = Path(".github") / "workflows"
SCOPED = "pstack-verifier.yml"
VERIFIER_JOB = "pstack-verifier"
NIGHTLY = "nightly-journeys.yml"
MAINTAIN = "verify-skill-maintain.yml"
BROWSER = re.compile(r"verify-sf-companion/run\.sh|playwright|chromium", re.IGNORECASE)
PULL_TRIGGERS = {"pull_request", "pull_request_target"}
PINNED_SOURCE = re.compile(r"repository:\s*cursor/plugins\s*\n\s*ref:\s*([0-9a-f]{40})\s*$", re.MULTILINE)
TRIGGER = re.compile(r"^  ([A-Za-z_][A-Za-z0-9_-]*):")
JOB = re.compile(r"^  ([A-Za-z_][A-Za-z0-9_-]*):\s*$")
INLINE = re.compile(r"^on:\s*(.+?)\s*$")
INLINE_VALUE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
QUOTING = re.compile(r"[\"'\\]")
FORK_REFUSAL = re.compile(r"head\.repo\.full_name\s*!=\s*github\.repository[\s\S]*?exit 1")
FEATURE_MAP = re.compile(r"name:\s*Feature map matches source[\s\S]*?feature_coverage\.py")


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


def job_block(source):
    lines = source.split("\n")
    for index, line in enumerate(lines):
        match = JOB.match(line)
        if match is None or match.group(1) != VERIFIER_JOB:
            continue
        block = []
        for following in lines[index + 1 :]:
            if following.strip() != "" and not following.startswith("    "):
                break
            block.append(following)
        return "\n".join(block)
    return None


def check_verifier_job(source):
    block = job_block(source)
    if block is None:
        return [
            f"{SCOPED} declares no `{VERIFIER_JOB}` job. The required check on `main` then reports nothing at all, and a pull request with no verification passes the branch protection it rests on. Fix: keep one job named `{VERIFIER_JOB}` so its result is the required status."
        ]
    errors = []
    if [line for line in block.split("\n") if line.startswith("    if:")]:
        errors.append(
            f"`{VERIFIER_JOB}` carries a job-level `if:`. A job its own `if:` skips reports neither success nor failure, and a skipped required check counts as passing, so the change lands unverified. Fix: drop the job-level `if:` and end the job red inside a step instead, so every pull request settles the required check one way or the other."
        )
    if FORK_REFUSAL.search(block) is None:
        errors.append(
            f"`{VERIFIER_JOB}` never refuses a fork pull request. A fork run gets no secrets, so its steps quietly wait and the required check can settle without verifying anything. Fix: add one step that runs on `github.event.pull_request.head.repo.full_name != github.repository`, says the fork cannot be verified, and exits 1."
        )
    if FEATURE_MAP.search(block) is None:
        errors.append(
            f"`{VERIFIER_JOB}` never runs the feature map check, `scripts/feature_coverage.py`. A pull request that adds a user-facing feature no file covers then passes the required check, and the feature map loses a feature while every run stays green. Fix: add a `Feature map matches source` step that runs `python3 scripts/feature_coverage.py` before the journeys."
        )
    if "hashFiles(" in block:
        errors.append(
            f"`{VERIFIER_JOB}` keys its base proof on `hashFiles(`, which hashes the head checkout where a shared helper may have changed. The key then hides the one fact that decides whether a saved proof is safe to serve, and another pull request reading the key cannot tell which helper built the proof. Fix: key the proof on the base commit and the journey digest, and skip the reuse whenever a shared helper changed."
        )
    return errors


def check_pull_requests(folder, workflows):
    errors = []
    for name, source in workflows.items():
        if name == MAINTAIN or triggers(source) & PULL_TRIGGERS == set():
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
            errors.extend(check_verifier_job(source))
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


def check_maintain(folder):
    source = read(folder, MAINTAIN)
    if source is None:
        return [
            f"{MAINTAIN} is missing. Nothing then reviews the feature map against source on a schedule, so the map rots while every other check still passes. Fix: add `{FOLDER / MAINTAIN}` with `schedule` and `workflow_dispatch`, a pinned `cursor/plugins` checkout, and a full `.claude/skills/verify-sf-companion/run.sh` run."
        ]
    errors = []
    found = triggers(source)
    if "schedule" not in found:
        errors.append(
            f"{MAINTAIN} has no `schedule` trigger. A maintenance pass that only runs when a person dispatches it stops keeping the map honest the day the schedule is dropped. Fix: add `schedule` with a `cron` entry to its `on` block."
        )
    if "workflow_dispatch" not in found:
        errors.append(
            f"{MAINTAIN} has no `workflow_dispatch` trigger. Without it a person cannot re-run the pass by hand after a drift report. Fix: add `workflow_dispatch` to its `on` block."
        )
    if found & PULL_TRIGGERS:
        errors.append(
            f"{MAINTAIN} triggers on pull requests. Its full journey run and its drift review cost more than a pull request should pay and would block every change. Fix: keep `schedule` and `workflow_dispatch` as the only entries so heavy maintenance stays off pull requests."
        )
    if "refs/heads/main" not in source:
        errors.append(
            f"{MAINTAIN} never names `refs/heads/main`. A scheduled pass on a feature branch proves nothing about the default branch. Fix: guard the job with `github.event_name == 'workflow_dispatch' || github.ref == 'refs/heads/main'` and keep `workflow_dispatch` for the hand-started proof."
        )
    if "cancel-in-progress: true" not in source:
        errors.append(
            f"{MAINTAIN} never sets `cancel-in-progress: true`. A superseded pass then keeps a runner busy and its proof uploads beside the newer one. Fix: add `concurrency` with `cancel-in-progress: true`."
        )
    if PINNED_SOURCE.search(source) is None:
        errors.append(
            f"{MAINTAIN} checks out no `cursor/plugins` source pinned to a full 40-character commit. The pstack demands then follow a moving branch, so the same commit can pass one week and fail the next. Fix: check out `cursor/plugins` at a pinned `ref` and pass its plugin manifest to `scripts/pstack_pin_drift.py`."
        )
    if "verify-sf-companion/run.sh" not in source:
        errors.append(
            f"{MAINTAIN} never runs `verify-sf-companion/run.sh`. The pass then reviews the map without exercising the app it describes. Fix: run `.claude/skills/verify-sf-companion/run.sh` in a step and hand its proof to the review."
        )
    if "actions/upload-artifact" not in source:
        errors.append(
            f"{MAINTAIN} uploads no proof. A drift report then cannot be checked against what the journeys saw. Fix: upload the proof directory with `actions/upload-artifact` and `if: always()`."
        )
    if "verify map drift" not in source or "issues: write" not in source:
        errors.append(
            f"{MAINTAIN} does not record drift in one `verify map drift` issue with `issues: write`. Drift then fails a run nobody reads. Fix: grant `issues: write` and open or update one issue titled `verify map drift`."
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
    return check_pull_requests(folder, workflows) + check_nightly(folder) + check_maintain(folder)


def main():
    errors = check(Path(__file__).resolve().parent.parent)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
