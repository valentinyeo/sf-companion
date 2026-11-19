#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

VERDICT = re.compile(r"^VERDICT: (CLEAN|DRIFT)\s*$", re.MULTILINE)


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
    reasons = []
    if outcomes.get("pstack") != "success":
        reasons.append("The pstack pin check did not pass.")
    if outcomes.get("journeys") != "success":
        reasons.append("The full journey run did not pass.")
    if outcomes.get("review") != "success":
        reasons.append("The review step did not finish cleanly.")
    if outcomes.get("clean") != "success":
        reasons.append("The review changed a tracked file.")
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
    outcomes = {
        "pstack": os.environ.get("PSTACK_OUTCOME"),
        "journeys": os.environ.get("JOURNEYS_OUTCOME"),
        "review": os.environ.get("REVIEW_OUTCOME"),
        "clean": os.environ.get("CLEAN_OUTCOME"),
    }
    print(json.dumps(decide(outcomes, os.environ.get("RECORDS", "."))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
