#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

README = ".claude/skills/verify-sf-companion/features/README.md"
FIXTURE = ".claude/skills/verify-sf-companion/fixture.json"
HUB_INDEX = ".claude/skills/verify-sf-companion/fixture-hub/index.json"
SCALE_HEADING = "## Scale"
COLUMNS = ["Measure", "Production", "Fixture"]
ANY_HEADING = re.compile(r"^## ")
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
INTEGER = re.compile(r"^\d+$")

MEASURES = [
    ("Hub reports", ("hub", "r/")),
    ("Hub explorations", ("hub", "x/")),
    ("Usage cards", ("feed", ("usage", "cards"))),
    ("Usage burn windows", ("feed", ("usage", "burn"))),
    ("KPI tiles", ("feed", ("kpis", "tiles"))),
    ("KPI notes", ("feed", ("kpis", "notes"))),
    ("Shipping days", ("feed", ("kpis", "shipping", "days"))),
    ("Shipping omissions", ("feed", ("kpis", "shipping", "omissions"))),
    ("Shipping notes", ("feed", ("kpis", "shipping", "notes"))),
]


def read(root, name):
    path = Path(root) / name
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def load(root, name):
    source = read(root, name)
    if source is None:
        raise FileNotFoundError(name)
    return json.loads(source)


def section(lines, heading):
    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    if start is None:
        return None
    body = []
    for line in lines[start:]:
        if ANY_HEADING.match(line):
            break
        body.append(line)
    return body


def cells(row):
    stripped = row.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def tables(lines):
    found = []
    current = []
    for line in lines + [""]:
        row = cells(line)
        if row is None:
            if current:
                found.append(current)
            current = []
            continue
        if all(re.fullmatch(r":?-{2,}:?", cell) for cell in row):
            continue
        current.append(row)
    return found


def count(measure, feed, hub):
    kind, where = measure
    if kind == "hub":
        return sum(
            1
            for entry in hub
            if isinstance(entry, dict) and str(entry.get("key", "")).startswith(where)
        )
    value = feed
    for step in where:
        value = value[step]
    return len(value)


def counts(feed, hub):
    return {name: count(measure, feed, hub) for name, measure in MEASURES}


def check(root):
    errors = []
    source = read(root, README)
    if source is None:
        return [
            f"{README} is missing, so the recorded production scale cannot be read. Fix: restore {README} with its Scale section."
        ]
    try:
        feed = load(root, FIXTURE)
        hub = load(root, HUB_INDEX)
    except FileNotFoundError as missing:
        return [
            f"{missing.args[0]} is missing, so the fixture scale cannot be counted. Fix: restore the fixture, or point scripts/check_fixture_scale.py at the file that replaced it."
        ]
    except json.JSONDecodeError as broken:
        return [
            f"{broken.doc[:40]} does not read as JSON, so the fixture scale cannot be counted. Fix: repair the JSON, or restore the fixture."
        ]
    body = section(source.split("\n"), SCALE_HEADING)
    if body is None:
        return [
            f"{README} has no \"{SCALE_HEADING}\" section, so no production scale is recorded and the fixture has no floor. Fix: add the section with the table columns Measure, Production, Fixture and the date production was measured."
        ]
    text = " ".join(body)
    if DATE.search(text) is None:
        errors.append(
            f"\"{SCALE_HEADING}\" never says when production was measured. A count with no date cannot be re-measured. Fix: name the date as YYYY-MM-DD in that section."
        )
    parsed = tables(body)
    if parsed == []:
        return errors + [
            f"\"{SCALE_HEADING}\" holds no table, so no measure is checked. Fix: add the table with the columns Measure, Production, Fixture."
        ]
    header = parsed[0][0]
    if header != COLUMNS:
        return errors + [
            f"The Scale table's header is {' | '.join(header)} instead of {' | '.join(COLUMNS)}. Fix: restore the three columns."
        ]
    actual = counts(feed, hub)
    known = dict(MEASURES)
    seen = set()
    for row in parsed[0][1:]:
        if len(row) != len(COLUMNS):
            errors.append(
                f"The Scale row {' | '.join(row)} has {len(row)} cells instead of {len(COLUMNS)}. Fix: give each row a measure, its production count and its fixture count."
            )
            continue
        name, production, fixture = row
        if name not in known:
            errors.append(
                f"The Scale table names \"{name}\", which scripts/check_fixture_scale.py cannot count. Fix: use one of {', '.join(known)}, or teach the check the new measure."
            )
            continue
        seen.add(name)
        if INTEGER.match(production) is None or INTEGER.match(fixture) is None:
            errors.append(
                f"The {name} row holds \"{production}\" and \"{fixture}\", and a count must be a whole number. Fix: write the measured count in both columns."
            )
            continue
        floor = int(production)
        recorded = int(fixture)
        if recorded != actual[name]:
            errors.append(
                f"The {name} row records a fixture count of {recorded} and the fixture holds {actual[name]}. A table that drifts from the fixture records a scale nothing drives. Fix: set the Fixture column to {actual[name]}, or change the fixture."
            )
        if actual[name] < floor:
            errors.append(
                f"The fixture holds {actual[name]} {name.lower()} and production ran {floor} on the recorded date, so every journey starts below the size users meet. Fix: grow the fixture to at least {floor}, or record the smaller production count with a new date."
            )
    for name, _ in MEASURES:
        if name not in seen:
            errors.append(
                f"The Scale table has no {name} row, so nothing stops that fixture count from falling. Fix: add the row with its production and fixture counts."
            )
    if errors:
        return errors
    margins = {
        row[0]: actual[row[0]] - int(row[1]) for row in parsed[0][1:]
    }
    lowest = min(margins, key=lambda name: margins[name])
    print(
        f"fixture scale: {len(MEASURES)} measures, every fixture count at or above production, lowest margin {lowest} at {margins[lowest]}"
    )
    return []


def measure(feed_path, hub_path):
    feed = (
        json.loads(Path(feed_path).read_text(encoding="utf-8")) if feed_path else None
    )
    hub = (
        json.loads(Path(hub_path).read_text(encoding="utf-8")) if hub_path else None
    )
    for name, (kind, where) in MEASURES:
        source = hub if kind == "hub" else feed
        if source is None:
            missing = "hub index" if kind == "hub" else "feed"
            print(f"{name}: not measured, no {missing} given")
            continue
        print(f"{name}: {count((kind, where), feed, hub)}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Check the journey fixture holds at least the scale production runs at."
    )
    parser.add_argument(
        "--measure",
        action="store_true",
        help="print the counts in a feed and a hub index instead of checking the fixture",
    )
    parser.add_argument("--feed", help="a factory feed JSON to count")
    parser.add_argument("--hub-index", help="a hub index.json to count")
    arguments = parser.parse_args()
    if arguments.measure:
        return measure(arguments.feed, arguments.hub_index)
    root = Path(__file__).resolve().parent.parent
    errors = check(root)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
