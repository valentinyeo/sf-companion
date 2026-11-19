#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

VERDICT = re.compile(r"^VERDICT: (CLEAN|DRIFT)\s*$", re.MULTILINE)
PASSED = "success"
STEPS = (
    ("pstack", "The pstack pin check did not pass."),
    ("journeys", "The full journey run did not pass."),
    ("review", "The review step did not finish cleanly."),
    ("clean", "The review changed a tracked file."),
)


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def review_text(records):
    events = []
    for line in read_text(Path(records) / "review.jsonl").split("\n"):
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    messages = [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("type") == "message_end"
        and isinstance(event.get("message"), dict)
        and event["message"].get("role") == "assistant"
    ]
    if not messages:
        return ""
    content = messages[-1]["message"].get("content") or []
    return "\n".join(
        part["text"]
        for part in content
        if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)
    )


def decide(outcomes, records):
    text = review_text(records)
    match = VERDICT.search(text)
    reasons = [reason for step, reason in STEPS if outcomes.get(step) != PASSED]
    if match is None:
        reasons.append("The review returned no verdict line.")
    elif match.group(1) == "DRIFT":
        reasons.append("The review found drift.")
    return {
        "verdict": None if match is None else match.group(1),
        "text": text,
        "drift": bool(reasons),
        "reasons": reasons,
    }


def main():
    outcomes = {step: os.environ.get(f"{step.upper()}_OUTCOME") for step, _ in STEPS}
    print(json.dumps(decide(outcomes, os.environ.get("RECORDS", "."))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
