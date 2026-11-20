#!/usr/bin/env python3
import argparse
import io
import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

API = "https://api.github.com"
PREFIX = "base-proof-v1"
PROOF = "proof-base"


def artifact_name(base_sha, digest):
    return f"{PREFIX}-{base_sha}-{digest}"


def headers(token):
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "sf-companion-base-proof-cache",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_json(url, token):
    request = urllib.request.Request(url, headers=headers(token))
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def github_bytes(url, token):
    request = urllib.request.Request(url, headers=headers(token))
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def saved_artifacts(repo, name, token, fetch_json=github_json):
    found = []
    page = 1
    while True:
        payload = fetch_json(
            f"{API}/repos/{repo}/actions/artifacts?name={name}&per_page=100&page={page}",
            token,
        )
        batch = payload.get("artifacts") or []
        found.extend(
            artifact
            for artifact in batch
            if artifact.get("name") == name and not artifact.get("expired")
        )
        if not batch or len(found) >= (payload.get("total_count") or 0):
            return found
        page += 1


def newest(artifacts):
    if not artifacts:
        return None
    return max(artifacts, key=lambda artifact: artifact.get("created_at") or "")


def place(archive, proof_dir):
    holding = Path(tempfile.mkdtemp(prefix="base-proof-cache."))
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            bundle.extractall(holding)
        candidates = [holding] + sorted(
            path for path in holding.iterdir() if path.is_dir()
        )
        for candidate in candidates:
            if not (candidate / "result.json").is_file():
                continue
            if proof_dir.exists():
                shutil.rmtree(proof_dir)
            proof_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(candidate), str(proof_dir))
            return True
        return False
    finally:
        shutil.rmtree(holding, ignore_errors=True)


def report(output, result):
    if output is None:
        return
    lines = [f"hit={'true' if result['hit'] else 'false'}"]
    if result["run"]:
        lines.append(f"run={result['run']}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def restore(repo, base_sha, digest, proof_dir, token, output=None, fetch_json=None, fetch_zip=None):
    fetch_json = fetch_json or github_json
    fetch_zip = fetch_zip or github_bytes
    name = artifact_name(base_sha, digest)
    try:
        chosen = newest(saved_artifacts(repo, name, token, fetch_json))
    except OSError as error:
        return miss(output, f"base proof cache miss: could not ask GitHub for {name}: {error}")
    if chosen is None:
        return miss(output, f"base proof cache miss: no earlier run saved {name}")
    run = str((chosen.get("workflow_run") or {}).get("id") or "")
    try:
        archive = fetch_zip(
            f"{API}/repos/{repo}/actions/artifacts/{chosen['id']}/zip", token
        )
    except OSError as error:
        return miss(output, f"base proof cache miss: could not download {name}: {error}")
    if not place(archive, Path(proof_dir)):
        return miss(output, f"base proof cache miss: {name} holds no {PROOF}/result.json")
    message = (
        f"base proof cache hit: {name} from run {run} "
        f"{(chosen.get('workflow_run') or {}).get('html_url') or ''}".rstrip()
    )
    print(message)
    result = {"hit": True, "message": message, "name": name, "run": run}
    report(output, result)
    return result


def miss(output, message):
    print(message)
    result = {"hit": False, "message": message, "name": "", "run": ""}
    report(output, result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["name", "restore"])
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--repo")
    parser.add_argument("--proof-dir")
    parser.add_argument("--token", default=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--output", default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args()
    if args.command == "name":
        print(artifact_name(args.base_sha, args.digest))
        return 0
    if not args.repo or not args.proof_dir:
        parser.error("restore needs --repo and --proof-dir")
    if not args.token:
        parser.error("restore needs --token, GH_TOKEN, or GITHUB_TOKEN")
    restore(
        repo=args.repo,
        base_sha=args.base_sha,
        digest=args.digest,
        proof_dir=Path(args.proof_dir),
        token=args.token,
        output=Path(args.output) if args.output else None,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
