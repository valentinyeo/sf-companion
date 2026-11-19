#!/usr/bin/env python3
import argparse
import io
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import select_verifier_scope as selector

API = "https://api.github.com"
WORKFLOW = "pstack-verifier.yml"
ARTIFACT = "verifier-proofs"
PROOF = "proof-head"
TRACES = "traces.json"
APP_CODE = ("apps/", "packages/")
CONTENT = ("apps/web/content/")
DEFAULT_REPO_PATH = str(Path(__file__).resolve().parent.parent)
DEFAULT_STATE_FILE = "~/.local/state/sf-companion/deployed-sha"
DEFAULT_FEATURES = ".claude/skills/verify-sf-companion/features"
LIVE_ONLY = "live-only.json"
TRACE_SUFFIXES = (".trace.zip", ".webm")


class GateError(Exception):
    pass


class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, new_url):
        next_request = super().redirect_request(
            request, fp, code, msg, headers, new_url
        )
        if next_request is None:
            return None
        if urllib.parse.urlsplit(new_url).netloc != urllib.parse.urlsplit(
            request.full_url
        ).netloc:
            next_request.remove_header("Authorization")
        return next_request


def open_url(request, timeout):
    return urllib.request.build_opener(Redirects()).open(request, timeout=timeout)


def api_token():
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value
    try:
        done = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, check=True, text=True
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return done.stdout.strip()


def api(path, token):
    request = urllib.request.Request(
        f"{API}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with open_url(request, 60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise GateError(f"GitHub answered {error.code} for {path}") from error
    except urllib.error.URLError as error:
        raise GateError(f"GitHub is unreachable for {path}: {error.reason}") from error


def api_pages(path, token, limit=10):
    separator = "&" if "?" in path else "?"
    items = []
    for page in range(1, limit + 1):
        payload = api(f"{path}{separator}per_page=100&page={page}", token)
        items.extend(payload)
        if len(payload) < 100:
            return items
    raise GateError(f"{path} holds more than {limit * 100} pages")


def artifact_bytes(repository, artifact_id, token):
    request = urllib.request.Request(
        f"{API}/repos/{repository}/actions/artifacts/{artifact_id}/zip",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with open_url(request, 300) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        raise GateError(
            f"GitHub answered {error.code} for artifact {artifact_id}"
        ) from error


def is_app_code(path):
    return path.startswith(APP_CODE) and not path.startswith(CONTENT)


def app_code_paths(paths):
    return [path for path in paths if is_app_code(path)]


def merged_in_range(pull_requests, commit_shas):
    found = []
    for pull_request in pull_requests:
        if pull_request.get("merged_at") is None:
            continue
        merged = pull_request.get("merge_commit_sha")
        head = (pull_request.get("head") or {}).get("sha")
        if merged in commit_shas or head in commit_shas:
            found.append(pull_request)
    return found


def live_only_journeys(features_dir):
    path = Path(features_dir).expanduser().parent / LIVE_ONLY
    if not path.is_file():
        raise GateError(f"{path} is missing, so no journey can be excused a trace")
    return json.loads(path.read_text(encoding="utf-8"))


def required_journeys(features, changed_paths):
    scope = selector.select_scope(changed_paths, features, [])
    return scope["journeys"], scope["features"]


def pick_run(runs, head_sha):
    for run in runs.get("workflow_runs") or []:
        if run.get("head_sha") != head_sha:
            continue
        if run.get("conclusion") != "success":
            continue
        return run
    return None


def pick_artifact(artifacts):
    for artifact in artifacts.get("artifacts") or []:
        if artifact.get("expired"):
            continue
        if artifact.get("name") != ARTIFACT:
            continue
        return artifact
    return None


def member_sizes(archive_bytes):
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        return {item.filename: item.file_size for item in archive.infolist()}


def read_traces(archive_bytes):
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        for name in archive.namelist():
            if name == f"{PROOF}/{TRACES}" or name.endswith(f"/{PROOF}/{TRACES}"):
                return json.loads(archive.read(name))
    return None


def check_traces(journeys, traces, members, live_only):
    if traces is None:
        return [
            f"the run uploaded no {PROOF}/{TRACES}, so no journey has a recorded trace"
        ]
    recorded = traces.get("journeys") or {}
    excused = {
        entry.get("journey")
        for entry in traces.get("untraced") or []
        if entry.get("journey") in live_only and entry.get("reason")
    }
    sizes = {name.rsplit("/", 1)[-1]: size for name, size in members.items()}
    problems = []
    for journey in journeys:
        names = recorded.get(journey) or []
        if not names:
            if journey in excused:
                continue
            problems.append(f"no trace or video for journey {journey}")
            continue
        for name in names:
            if not name.endswith(TRACE_SUFFIXES):
                problems.append(f"{name} for journey {journey} is not a trace or video")
                continue
            if sizes.get(name.rsplit("/", 1)[-1], 0) == 0:
                problems.append(
                    f"the proof artifact holds no {name} for journey {journey}"
                )
    return problems


def evaluate_pull_request(
    pull_request, files, runs, artifacts, archive, features, live_only
):
    number = pull_request["number"]
    title = pull_request.get("title") or ""
    changed = [entry["filename"] for entry in files]
    code = app_code_paths(changed)
    report = {
        "number": number,
        "title": title,
        "head": (pull_request.get("head") or {}).get("sha"),
        "features": [],
        "journeys": [],
        "run": None,
        "problems": [],
    }
    if not code:
        report["outcome"] = "no app code"
        return report
    journeys, touched = required_journeys(features, changed)
    report["features"] = touched
    report["journeys"] = journeys
    run = pick_run(runs, report["head"])
    if run is None:
        report["outcome"] = "failed"
        report["problems"] = [
            f"no successful {WORKFLOW} run for head {report['head']}"
        ]
        return report
    report["run"] = run.get("id")
    artifact = pick_artifact(artifacts)
    if artifact is None:
        report["outcome"] = "failed"
        report["problems"] = [
            f"run {run.get('id')} uploaded no {ARTIFACT} artifact"
        ]
        return report
    if archive is None:
        report["outcome"] = "failed"
        report["problems"] = [
            f"artifact {artifact.get('name')} for run {run.get('id')} could not be read"
        ]
        return report
    traces = read_traces(archive)
    problems = check_traces(journeys, traces, member_sizes(archive), live_only)
    revision = (traces or {}).get("revision")
    if revision is not None and revision != report["head"]:
        problems.insert(
            0,
            f"the proof records revision {revision}, not head {report['head']}",
        )
    report["problems"] = problems
    report["outcome"] = "failed" if report["problems"] else "passed"
    return report


def read_state(state_file):
    path = Path(state_file).expanduser()
    if not path.is_file():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def git(repo_path, *arguments):
    done = subprocess.run(
        ["git", "-C", str(Path(repo_path).expanduser()), *arguments],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        raise GateError(done.stderr.strip() or f"git {arguments[0]} failed")
    return done.stdout.strip()


def print_report(pull_request_reports):
    for report in pull_request_reports:
        label = f"#{report['number']} {report['title']}".rstrip()
        print(f"{label} [{report['outcome']}]")
        if report["features"]:
            print(f"  features: {', '.join(report['features'])}")
            print(f"  journeys: {', '.join(report['journeys'])}")
        if report["run"] is not None:
            print(f"  verifier run: {report['run']}")
        for problem in report["problems"]:
            print(f"  missing: {problem}")


def release(args):
    token = api_token()
    if not token:
        raise GateError(
            "no GitHub token. Set GITHUB_TOKEN, or run `gh auth login` on this host."
        )
    repository = args.repository
    base = args.base_sha or read_state(args.state_file)
    head = args.head_sha or git(args.repo_path, "rev-parse", "HEAD")
    if base is None:
        print(
            f"no deployed SHA in {args.state_file}, so nothing is deployed yet; "
            f"{head} needs no proof. Record that SHA after the next deploy."
        )
        return 0
    if base == head:
        print(f"{head} is already deployed; no pull request needs proof.")
        return 0
    print(f"release gate: {head} deploys after {base}")
    compare = api(f"/repos/{repository}/compare/{base}...{head}", token)
    if compare.get("status") not in {"ahead", "identical"}:
        raise GateError(
            f"the recorded SHA {base} is not an ancestor of {head}, "
            "so the merge range cannot be read. Record the deployed SHA again."
        )
    commits = compare.get("commits") or []
    if compare.get("total_commits", 0) > len(commits):
        raise GateError(
            f"{compare['total_commits']} commits between {base} and {head} exceed "
            f"the {len(commits)} GitHub returns; gate a shorter range"
        )
    shas = {commit["sha"] for commit in commits}
    closed = api_pages(
        f"/repos/{repository}/pulls?state=closed&sort=updated&direction=desc", token
    )
    merged = merged_in_range(closed, shas)
    if merged == []:
        code = app_code_paths(
            [entry["filename"] for entry in compare.get("files") or []]
        )
        if code:
            print(
                f"{len(commits)} commits since {base} changed app code with no "
                f"merged pull request to prove it: {', '.join(sorted(code))}",
                file=sys.stderr,
            )
            return 1
        print(f"{len(commits)} commits since {base} hold no merged app code change.")
        return 0
    features = selector.read_features(
        Path(args.repo_path).expanduser() / args.features_dir
    )
    live_only = live_only_journeys(Path(args.repo_path).expanduser() / args.features_dir)
    reports = []
    for pull_request in merged:
        number = pull_request["number"]
        files = api_pages(f"/repos/{repository}/pulls/{number}/files", token)
        head_sha = (pull_request.get("head") or {}).get("sha")
        runs = api(
            f"/repos/{repository}/actions/workflows/{WORKFLOW}/runs"
            f"?head_sha={head_sha}&per_page=20",
            token,
        )
        run = pick_run(runs, head_sha)
        artifacts = {"artifacts": []}
        archive = None
        if run is not None:
            artifacts = api(
                f"/repos/{repository}/actions/runs/{run['id']}/artifacts", token
            )
            artifact = pick_artifact(artifacts)
            if artifact is not None:
                archive = artifact_bytes(repository, artifact["id"], token)
        reports.append(
            evaluate_pull_request(
                pull_request, files, runs, artifacts, archive, features, live_only
            )
        )
    print_report(reports)
    failed = [report for report in reports if report["outcome"] == "failed"]
    if failed:
        print(
            f"release gate: {len(failed)} of {len(reports)} pull requests lack proof "
            "for a journey they changed.",
            file=sys.stderr,
        )
        return 1
    print(
        f"release gate: {len(reports)} pull requests since {base} hold a trace or "
        f"video for every journey they changed."
    )
    return 0


def proof(args):
    directory = Path(args.proof_dir).expanduser()
    traces_path = directory / TRACES
    if not traces_path.is_file():
        print(
            f"no {traces_path}: the run recorded no trace or video",
            file=sys.stderr,
        )
        return 1
    journeys = [value for value in (args.journeys or "").split(",") if value]
    members = {
        path.relative_to(directory).as_posix(): path.stat().st_size
        for path in directory.rglob("*")
        if path.is_file()
    }
    live_only = live_only_journeys(
        Path(args.repo_path).expanduser() / args.features_dir
    )
    problems = check_traces(
        journeys, json.loads(traces_path.read_text()), members, live_only
    )
    if problems:
        for problem in problems:
            print(f"missing: {problem}", file=sys.stderr)
        return 1
    print(f"proof: a trace or video covers {len(journeys)} journeys")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH)
    parser.add_argument("--repository", default="valentinyeo/sf-companion")
    parser.add_argument("--state-file", default=DEFAULT_STATE_FILE)
    parser.add_argument("--features-dir", default=DEFAULT_FEATURES)
    parser.add_argument("--base-sha")
    parser.add_argument("--head-sha")
    parser.add_argument("--proof-dir")
    parser.add_argument("--journeys")
    args = parser.parse_args()
    try:
        if args.proof_dir:
            return proof(args)
        return release(args)
    except GateError as error:
        print(f"release gate: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
