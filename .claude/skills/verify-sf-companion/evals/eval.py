import argparse
import json
import re
import sys
from pathlib import Path

VERDICT = re.compile(r"^(PASS\+NOTES|PASS|FAIL)\s*$", re.MULTILINE)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def matrix(spec):
    include = []
    for family in spec["families"]:
        for case in spec["cases"]:
            include.append(
                {
                    "case": case["id"],
                    "patch": case["patch"] or "",
                    "expect": case["expect"],
                    "family": family["family"],
                    "provider": family["provider"],
                    "model": family["model"],
                }
            )
    print(f"matrix={json.dumps({'include': include}, separators=(',', ':'))}")


def journeys(spec):
    print(",".join(spec["journeys"]))


def text_of(trace):
    text = ""
    for line in trace.read_text(encoding="utf-8").splitlines():
        if line.strip() == "":
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "message_end":
            continue
        message = event.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        parts = message.get("content")
        if not isinstance(parts, list):
            continue
        spoken = [
            part.get("text", "")
            for part in parts
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        if spoken:
            text = "\n".join(spoken)
    return text


def verdict_of(trace):
    match = VERDICT.search(text_of(trace))
    return match.group(1) if match else "NO VERDICT"


def accepted(expect, actual):
    if expect == "FAIL":
        return actual == "FAIL"
    return actual in ("PASS", "PASS+NOTES")


def tabulate(spec, records, run_url):
    rows = []
    mismatches = []
    for family in spec["families"]:
        for case in spec["cases"]:
            trace = Path(records) / f"cell-{family['family']}-{case['id']}" / "verdict.jsonl"
            actual = verdict_of(trace) if trace.is_file() else "NO VERDICT"
            ok = accepted(case["expect"], actual)
            if not ok:
                mismatches.append(f"{family['family']} {case['id']}: expected {case['expect']}, got {actual}")
            rows.append(
                f"| {family['family']} | {case['id']} | {case['expect']} | {actual} | {'ok' if ok else 'mismatch'} |"
            )
    lines = [
        "# Verify-skill evaluation",
        "",
        f"Run: {run_url}",
        "",
        "| Family | Case | Expected | Actual | Result |",
        "| --- | --- | --- | --- | --- |",
        *rows,
        "",
        f"{len(rows)} cells, {len(mismatches)} mismatches.",
    ]
    if mismatches:
        lines.extend(["", *[f"- {mismatch}" for mismatch in mismatches]])
    table = "\n".join(lines) + "\n"
    print(table)
    return table, mismatches


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["matrix", "journeys", "tabulate"])
    parser.add_argument("--cases", required=True)
    parser.add_argument("--records")
    parser.add_argument("--run-url", default="")
    parser.add_argument("--summary")
    parser.add_argument("--table")
    args = parser.parse_args()
    spec = load(args.cases)
    if args.command == "matrix":
        matrix(spec)
        return 0
    if args.command == "journeys":
        journeys(spec)
        return 0
    table, mismatches = tabulate(spec, args.records, args.run_url)
    if args.table:
        Path(args.table).write_text(table, encoding="utf-8")
    if args.summary:
        with Path(args.summary).open("a", encoding="utf-8") as summary:
            summary.write(table)
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
