import argparse
import json
import re
import sys
from pathlib import Path


FAMILY_PATTERNS = (
    ("deepseek", (r"deepseek",)),
    ("anthropic", (r"anthropic", r"claude")),
    ("openai", (r"openai", r"gpt", r"(?:^|[^\da-z])o[134](?:[^\da-z]|$)")),
    ("google", (r"google", r"gemini", r"gemma")),
    ("xai", (r"x-ai", r"xai", r"grok")),
    ("meta", (r"meta", r"llama")),
    ("mistral", (r"mistral", r"devstral", r"codestral")),
    ("qwen", (r"qwen", r"alibaba")),
    ("moonshot", (r"moonshot", r"kimi")),
    ("zai", (r"z-ai", r"zai", r"\bglm\b")),
    ("cohere", (r"cohere", r"command-r")),
    ("microsoft", (r"microsoft", r"\bphi-")),
    ("nvidia", (r"nvidia", r"nemotron")),
    ("amazon", (r"amazon", r"\bnova-")),
    ("cursor", (r"cursor", r"composer")),
)

KNOWN_FAMILIES = tuple(family for family, _ in FAMILY_PATTERNS)

DEEPSEEK_VERIFIER = {
    "family": "deepseek",
    "model": "deepseek-v4.1-flash",
    "provider": "opencode-go",
    "secret": "OPENCODE_API_KEY",
}

OTHER_VERIFIERS = (
    {
        "family": "zai",
        "model": "zai/glm-5.3-flash",
        "provider": "vercel-ai-gateway",
        "secret": "AI_GATEWAY_API_KEY",
    },
    {
        "family": "openai",
        "model": "openai/gpt-6.1-sol",
        "provider": "openrouter",
        "secret": "OPENROUTER_API_KEY",
    },
)


def family_of(model_id):
    value = model_id.lower()
    for family, patterns in FAMILY_PATTERNS:
        if any(re.search(pattern, value) for pattern in patterns):
            return family
    return None


def parse_author_lines(body):
    authors = []
    unknown = []
    for raw_line in body.splitlines():
        match = re.match(r"\s*author model:\s*(.*)$", raw_line, re.IGNORECASE)
        if match is None:
            continue
        value = match.group(1).strip()
        family = family_of(value) if value else None
        if family is None:
            unknown.append(value or "(empty)")
            continue
        authors.append({"family": family, "value": value})
    return authors, unknown


def pick_verifier(body):
    authors, unknown = parse_author_lines(body)
    if unknown:
        return {
            "status": "fail",
            "reason": (
                f"Unknown author model family in: {', '.join(unknown)}. "
                f"Known families: {', '.join(KNOWN_FAMILIES)}."
            ),
        }
    if not authors:
        return {
            "status": "fail",
            "reason": (
                "No Author model line in the PR body. Add one line per author, "
                "such as Author model: deepseek/deepseek-v4.1-flash."
            ),
        }
    used = {author["family"] for author in authors}
    candidates = OTHER_VERIFIERS if "deepseek" in used else (DEEPSEEK_VERIFIER,)
    choice = next(
        (candidate for candidate in candidates if candidate["family"] not in used),
        None,
    )
    if choice is None:
        return {
            "authors": authors,
            "status": "fail",
            "reason": (
                "Every verifier family was used by an author. "
                f"Authors: {', '.join(sorted(used))}. "
                f"Verifier families: {', '.join(c['family'] for c in candidates)}."
            ),
        }
    return {"authors": authors, "status": "ok", **choice}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--body-file")
    args = parser.parse_args()
    body = Path(args.body_file).read_text() if args.body_file else sys.stdin.read()
    json.dump(pick_verifier(body), sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
