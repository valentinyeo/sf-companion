import argparse
import hashlib
import json
import os
import re
import sys


SMOKE_JOURNEY = "factory-entry"
SKILL_DIRECTORY = ".claude/skills/verify-sf-companion/"
FEATURE_FILE = re.compile(
    r"^\.claude/skills/verify-sf-companion/features/([a-z0-9][a-z0-9-]*)\.md$"
)


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


def feature_file_id(changed_path, features):
    match = FEATURE_FILE.match(changed_path)
    if match is None:
        return None
    name = match.group(1)
    return name if any(feature["id"] == name for feature in features) else None


def digest_of(journeys):
    return hashlib.sha256(",".join(journeys).encode("utf-8")).hexdigest()[:16]


def names(paths):
    return ", ".join(os.path.basename(path) for path in paths)


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
    skill_paths = [path for path in changed_paths if path.startswith(SKILL_DIRECTORY)]
    feature_files = [
        path for path in skill_paths if feature_file_id(path, features) is not None
    ]
    helpers = [path for path in skill_paths if feature_file_id(path, features) is None]
    harness = helpers != []
    touched = []
    journeys = set(repro_journeys)
    reasons = []
    if harness:
        touched = [feature["id"] for feature in features]
        journeys.update(known)
        reasons.append(
            f"every journey, because the shared helper {names(helpers)} changed"
        )
    else:
        for path in feature_files:
            identifier = feature_file_id(path, features)
            if identifier not in touched:
                touched.append(identifier)
            journeys.update(
                next(
                    feature["journeys"]
                    for feature in features
                    if feature["id"] == identifier
                )
            )
        if feature_files:
            reasons.append(f"the feature map changed in {names(feature_files)}")
        matched = []
        for feature in features:
            if not any(
                matches_code_path(changed_path, code_path)
                for code_path in feature["codePaths"]
                for changed_path in changed_paths
            ):
                continue
            if feature["id"] not in touched:
                touched.append(feature["id"])
            journeys.update(feature["journeys"])
            matched.append(feature["id"])
        if matched:
            reasons.append(f"the diff touched {', '.join(matched)}")
    fallback = not journeys
    if fallback:
        journeys.add(SMOKE_JOURNEY)
        reasons.append(f"no feature matched, so the {SMOKE_JOURNEY} smoke journey runs")
    ordered = sorted(journeys)
    return {
        "changedPaths": len(changed_paths),
        "digest": digest_of(ordered),
        "fallback": fallback,
        "features": touched,
        "harness": harness,
        "journeys": ordered,
        "reason": "; ".join(reasons),
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
