#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

DECORATION = r"[ \t>*_`#~\-]*"
BARE = re.compile(
    rf"^{DECORATION}(?:verdict\s*[:\-]?\s*)?{DECORATION}(PASS\+NOTES|PASS|FAIL){DECORATION}[.!]?{DECORATION}$",
    re.IGNORECASE | re.MULTILINE,
)
LABELLED = re.compile(
    rf"^{DECORATION}(?:verdict\s*[:\-]?\s*)?{DECORATION}(PASS\+NOTES|PASS|FAIL){DECORATION}(?=[:,.!—–-]\s*\S)[^\n]{{0,140}}$",
    re.IGNORECASE | re.MULTILINE,
)
TURN_ENDS_ON_A_TOOL_CALL = ("toolUse", "tool_use")


def read_reply(trace):
    path = Path(trace)
    if not path.is_file():
        return "", None
    texts = []
    stop = None
    for line in path.read_text(encoding="utf-8", errors="replace").split("\n"):
        if not line.strip():
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
        stop = message.get("stopReason") or message.get("rawStopReason") or stop
        content = message.get("content") or []
        body = "\n".join(
            part["text"]
            for part in content
            if isinstance(part, dict)
            and part.get("type") == "text"
            and isinstance(part.get("text"), str)
        )
        if body.strip():
            texts.append(body)
    if not texts:
        return "", stop
    return "\n\n".join(texts), stop


def find_verdict(text):
    for pattern in (BARE, LABELLED):
        match = pattern.search(text)
        if match is not None:
            return match.group(1).upper()
    return None


def why_no_verdict(reads):
    if not any(text.strip() for text, _ in reads):
        stop = reads[-1][1] if reads else None
        if stop in TURN_ENDS_ON_A_TOOL_CALL:
            return "The verifier stopped on a tool call and never wrote a reply."
        return "The verifier produced no reply."
    return "The reply holds no verdict line."


def decide(traces):
    reads = [read_reply(trace) for trace in traces]
    for lane, (text, _) in enumerate(reads, start=1):
        verdict = find_verdict(text)
        if verdict is not None:
            return {
                "verdict": verdict,
                "lane": lane,
                "reply": text,
                "reason": None,
            }
    longest = max(reads, key=lambda read: len(read[0]))[0] if reads else ""
    return {
        "verdict": None,
        "lane": None,
        "reply": longest,
        "reason": why_no_verdict(reads),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", action="append", default=[])
    parser.add_argument("--out")
    args = parser.parse_args()
    result = decide(args.trace)
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    json.dump({key: value for key, value in result.items() if key != "reply"}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
