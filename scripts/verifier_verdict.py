#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

WORD = r"(PASS\+NOTES|PASS|FAIL)"
EMPHASIS = r"[ \t*_`#~]*"
ANY_DECORATION = r"[ \t>*_`#~\-]*"
LABEL = r"(?:verdict\s*[:\-]?\s*)?"
STRONG = re.compile(
    rf"^{EMPHASIS}{LABEL}{EMPHASIS}{WORD}{EMPHASIS}[.!]?{EMPHASIS}$",
    re.IGNORECASE | re.MULTILINE,
)
WEAK = re.compile(
    rf"^{ANY_DECORATION}{LABEL}{ANY_DECORATION}{WORD}(?:{EMPHASIS}[.]?$|{EMPHASIS}[:,.!—–\-]\s*\S[^\n]{{0,160}}$)",
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


def lines_of(pattern, text):
    return [match.group(1).upper() for match in pattern.finditer(text)]


def find_verdict(text):
    strong = lines_of(STRONG, text)
    weak = lines_of(WEAK, text)
    if "FAIL" in strong or "FAIL" in weak:
        return "FAIL"
    if strong:
        return strong[-1]
    if weak:
        return weak[-1]
    return None


def why_no_verdict(text, stop):
    if not text.strip():
        if stop in TURN_ENDS_ON_A_TOOL_CALL:
            return "The verifier stopped on a tool call and never wrote a reply."
        return "The verifier produced no reply."
    return "The reply holds no verdict line."


def decide(trace):
    text, stop = read_reply(trace)
    verdict = find_verdict(text)
    return {
        "verdict": verdict,
        "reply": text,
        "reason": None if verdict is not None else why_no_verdict(text, stop),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True)
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
