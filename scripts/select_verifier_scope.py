import argparse
import json
import os
import re
import sys


SMOKE_JOURNEY = "factory-entry"
SKILL_DIRECTORY = ".claude/skills/verify-sf-companion/"


def parse_feature(text):
    code_paths = []
    journeys = []
    for raw_line in text.splitlines():
        code_match = re.match(r"(?i)\s*code paths:\s*(.*)$", raw_line)
        if code_match is not None:
            for part in code_match.group(1).split(","):
                value = part.strip().strip("`")
                if value:
                    code_paths.append(value)
        journey_match = re.match(r"-\s+`([a-z0-9][a-z0-9-]*)`", raw_line)
        if journey_match is not None:
            journeys.append(journey_match.group(1))
    return {"codePaths": code_paths, "journeys": journeys}


def parse_repro_journeys(body):
    journeys = []
    for raw_line in body.splitlines():
        match = re.match(r"(?i)\s*repro journey:\s*(.*)$", raw_line)
        if match is None:
            continue
        for part in match.group(1).split(","):
            value = part.strip().strip("`")
            if value:
                journeys.append(value)
    return journeys


def matches_code_path(changed_path, code_path):
    prefix = code_path.removesuffix("/**").removesuffix("/")
    return changed_path == prefix or changed_path.startswith(f"{prefix}/")


def select_scope(changed_paths, features, repro_journeys):
    known = {journey for feature in features for journey in feature["journeys"]}
    unknown_repro = [journey for journey in repro_journeys if journey not in known]
    if unknown_repro:
        return {
            "status": "fail",
            "reason": (
                f"Unknown repro journey: {', '.join(unknown_repro)}. "
                f"Known journeys: {', '.join(sorted(known))}."
            ),
        }
    harness = any(path.startswith(SKILL_DIRECTORY) for path in changed_paths)
    touched = []
    journeys = set(repro_journeys)
    if harness:
        touched = [feature["id"] for feature in features]
        journeys.update(known)
    else:
        for feature in features:
            matched = any(
                matches_code_path(changed_path, code_path)
                for code_path in feature["codePaths"]
                for changed_path in changed_paths
            )
            if not matched:
                continue
            touched.append(feature["id"])
            journeys.update(feature["journeys"])
    fallback = not journeys
    if fallback:
        journeys.add(SMOKE_JOURNEY)
    return {
        "changedPaths": len(changed_paths),
        "fallback": fallback,
        "features": touched,
        "harness": harness,
        "journeys": sorted(journeys),
        "repro": list(repro_journeys),
        "status": "ok",
    }


def read_features(directory):
    features = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".md") or name == "README.md":
            continue
        with open(os.path.join(directory, name), encoding="utf-8") as handle:
            feature = parse_feature(handle.read())
        features.append({**feature, "id": name.removesuffix(".md")})
    return features


def read_list(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features-dir", required=True)
    parser.add_argument("--diff-list", required=True)
    parser.add_argument("--pr-body-file")
    args = parser.parse_args()
    with open(args.diff_list, encoding="utf-8") as handle:
        changed_paths = read_list(handle.read())
    body = ""
    if args.pr_body_file:
        with open(args.pr_body_file, encoding="utf-8") as handle:
            body = handle.read()
    scope = select_scope(
        changed_paths,
        read_features(args.features_dir),
        parse_repro_journeys(body),
    )
    json.dump(scope, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
