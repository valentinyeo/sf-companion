#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path

FEATURES_DIR = Path(".claude/skills/verify-sf-companion/features")
ROUTE_FILE = Path("apps/web/src/features/route.ts")
ITEM_FILE = Path("apps/web/src/content/item.ts")
FACTORY_FILE = Path("apps/web/src/features/factory.ts")
SHARE_FILE = Path("apps/web/src/content/share.ts")
WEBSITE_FILE = Path("apps/web/src/website.ts")
VERIFIER_FILE = Path(".github/workflows/pstack-verifier.yml")
README = "README.md"

ROUTE_UNION = re.compile(r"Route\.defineRouteUnion\(\{((?:.|\n)*?)\n\}\)")
ROUTE_KEY = re.compile(r"^  ([A-Z][A-Za-z0-9]*):", re.MULTILINE)
SECTION_LITERALS = re.compile(r"export const Section = Schema\.Literals\(\[([^\]]*)\]\)")
FACTORY_HEADING = re.compile(r"h\.h2\(\[\], \[\s*\"([^\"]+)\"\]\)")
SHARE_HANDLER = re.compile(r"^export const ([A-Za-z0-9]+Item) =", re.MULTILINE)
DEPLOY_WEBSITE = re.compile(r"Cloudflare\.Website\.Foldkit<Website>\(\)\(\"Website\"")
COVERS = re.compile(r"(?im)^covers:\s*(.+)$")
COVERAGE_LINE = re.compile(
    r"^Coverage: (?P<covered>\d+) of (?P<total>\d+) features across (?P<files>\d+) files\.$"
)
NO_FEED = "No factory numbers yet."


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def coverage_line(covered, total, files):
    return f"Coverage: {covered} of {total} features across {files} files."


def read(root, relative):
    path = Path(root) / relative
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def route_features(source):
    union = ROUTE_UNION.search(source)
    if union is None:
        return set(), [
            f"{ROUTE_FILE.as_posix()} has no `Route.defineRouteUnion` block, so no route feature can be read. Fix: restore the route union or point scripts/feature_coverage.py at the file that owns it."
        ]
    names = ROUTE_KEY.findall(union.group(1))
    if not names:
        return set(), [
            f"{ROUTE_FILE.as_posix()} names no routes inside `Route.defineRouteUnion`. Fix: declare each route on its own two-space-indented line."
        ]
    return {f"route:{name}" for name in names}, []


def section_features(source):
    literals = SECTION_LITERALS.search(source)
    if literals is None:
        return set(), [
            f"{ITEM_FILE.as_posix()} has no `Section = Schema.Literals` line, so no hub section feature can be read. Fix: restore the section literal or point scripts/feature_coverage.py at the file that owns it."
        ]
    names = re.findall(r"\"([a-z0-9-]+)\"", literals.group(1))
    if not names:
        return set(), [
            f"{ITEM_FILE.as_posix()} declares no hub section name. Fix: list each section inside the `Section` literal."
        ]
    return {f"section:{name}" for name in names}, []


def factory_features(source):
    headings = FACTORY_HEADING.findall(source)
    if not headings:
        return set(), [
            f"{FACTORY_FILE.as_posix()} renders no `h.h2` section heading, so no factory section feature can be read. Fix: restore the factory sections or point scripts/feature_coverage.py at the file that renders them."
        ]
    keys = {f"factory:{slug(heading)}" for heading in headings}
    if NO_FEED in source:
        keys.add("factory:no-feed")
    return keys, []


def share_features(source):
    handlers = SHARE_HANDLER.findall(source)
    if not handlers:
        return set(), [
            f"{SHARE_FILE.as_posix()} exports no `*Item` handler, so no share feature can be read. Fix: restore the share handlers or point scripts/feature_coverage.py at the file that owns them."
        ]
    return {f"share:{name.removesuffix('Item').lower()}" for name in handlers}, []


def deploy_features(source):
    if DEPLOY_WEBSITE.search(source) is None:
        return set(), [
            f"{WEBSITE_FILE.as_posix()} declares no `Cloudflare.Website.Foldkit` resource, so the deployed Website feature cannot be read. Fix: restore the Website resource or point scripts/feature_coverage.py at the file that owns deployment."
        ]
    return {"deploy:website"}, []


def verifier_features(source):
    if re.search(r"\bpython3\s+scripts/pick_verifier\.py\b", source):
        return {"ci:verifier-selection"}, []
    return set(), []


def derived_features(root):
    sources = {
        (route_features, ROUTE_FILE),
        (section_features, ITEM_FILE),
        (factory_features, FACTORY_FILE),
        (share_features, SHARE_FILE),
        (deploy_features, WEBSITE_FILE),
        (verifier_features, VERIFIER_FILE),
    }
    keys = set()
    errors = []
    for reader, relative in sources:
        source = read(root, relative)
        if source is None:
            errors.append(
                f"`{relative.as_posix()}` is missing, so its features cannot be derived. Fix: restore the file or point scripts/feature_coverage.py at the file that owns those features."
            )
            continue
        found, failures = reader(source)
        keys.update(found)
        errors.extend(failures)
    return keys, errors


def covered_features(root):
    directory = Path(root) / FEATURES_DIR
    if not directory.is_dir():
        return {}, [], [
            f"`{FEATURES_DIR.as_posix()}` is missing, so no feature file can cover a feature. Fix: restore the feature map."
        ]
    files = sorted(path for path in directory.glob("*.md") if path.name != README)
    if not files:
        return {}, [], [
            f"`{FEATURES_DIR.as_posix()}` holds no feature file. Fix: add one file per feature with a `Covers:` line."
        ]
    covers = {}
    errors = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        match = COVERS.search(text)
        if match is None:
            errors.append(
                f"`{path.name}` has no `Covers:` line, so nothing it documents is counted as coverage. Fix: add a `Covers:` line naming the source features the file proves."
            )
            continue
        keys = [part.strip() for part in match.group(1).split(",") if part.strip()]
        if not keys:
            errors.append(
                f"`{path.name}` has an empty `Covers:` line. Fix: name at least one source feature it proves."
            )
            continue
        for key in keys:
            covers.setdefault(key, []).append(path.name)
    return covers, files, errors


def evaluate(root):
    derived, errors = derived_features(root)
    covers, files, feature_errors = covered_features(root)
    errors.extend(feature_errors)
    for key in sorted(covers):
        if key not in derived:
            errors.append(
                f"`{', '.join(covers[key])}` covers `{key}`, which the source no longer has. A feature map that names a dead feature is not honest. Fix: drop `{key}` from its `Covers:` line, or restore the source behaviour that made it a feature."
            )
        elif len(covers[key]) > 1:
            errors.append(
                f"`{key}` is covered by {', '.join(sorted(covers[key]))}. Two files claiming one feature double-count it and leave the real count unclear. Fix: keep the claim in one file and drop it from the others."
            )
    for key in sorted(derived - set(covers)):
        errors.append(
            f"`{key}` is user-facing in source but no feature file covers it. Fix: add it to the `Covers:` line of the file that drives it, or add a feature file for it."
        )
    covered = len(derived & set(covers))
    return errors, covered, len(derived), len(files)


def read_coverage_line(root):
    readme = Path(root) / FEATURES_DIR / README
    if not readme.is_file():
        return None, [
            f"`{FEATURES_DIR.as_posix()}/{README}` is missing, so the map has no coverage count. Fix: restore the index with a coverage line."
        ]
    for line in readme.read_text(encoding="utf-8").splitlines():
        if line.strip() == "":
            continue
        return line, []
    return "", [
        f"`{FEATURES_DIR.as_posix()}/{README}` is empty. Fix: open it with the coverage line."
    ]


def write_coverage_line(root, covered, total, files):
    readme = Path(root) / FEATURES_DIR / README
    lines = readme.read_text(encoding="utf-8").splitlines()
    line = coverage_line(covered, total, files)
    if lines:
        lines[0] = line
    else:
        lines = [line]
    readme.write_text("\n".join(lines) + "\n", encoding="utf-8")


def check(root):
    errors, covered, total, files = evaluate(root)
    if errors:
        return errors
    line, line_errors = read_coverage_line(root)
    if line_errors:
        return line_errors
    expected = coverage_line(covered, total, files)
    if line != expected:
        return [
            f"the coverage line in `{FEATURES_DIR.as_posix()}/{README}` reads `{line}` but the map covers `{expected}`. A stale count hides a feature that lost its file. Fix: run `scripts/feature_coverage.py --write`."
        ]
    print(f"feature coverage: {covered} of {total} features across {files} files")
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    if args.write:
        errors, covered, total, files = evaluate(root)
        if errors or total == 0 or files == 0:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        write_coverage_line(root, covered, total, files)
    errors = check(root)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
