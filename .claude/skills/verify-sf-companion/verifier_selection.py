import json
import subprocess
import sys
from pathlib import Path


repo = Path(sys.argv[1]).resolve()
entry = {"id": "verifier-selection", "status": "failed", "actions": []}
cases = (
    (
        "Author model: deepseek/deepseek-v4.1-flash\n",
        {
            "status": "ok",
            "family": "zai",
            "model": "zai/glm-5.3-flash",
            "provider": "vercel-ai-gateway",
            "secret": "AI_GATEWAY_API_KEY",
        },
    ),
    (
        "Author model: deepseek/deepseek-v4.1-flash\nAuthor model: zai/glm-5.3-flash\n",
        {"status": "ok", "family": "openai", "model": "openai/gpt-6.1-sol"},
    ),
    (
        "Author model: deepseek/deepseek-v4.1-flash\nAuthor model: zai/glm-5.3-flash\nAuthor model: openai/gpt-6.1-sol\n",
        {"status": "fail"},
    ),
    (
        "Author model: moonshotai/kimi-k3\n",
        {"status": "ok", "family": "deepseek", "model": "deepseek-v4.1-flash"},
    ),
    ("Author model: stealth/ox-alpha\n", {"status": "fail"}),
)
errors = []
try:
    for body, expected in cases:
        completed = subprocess.run(
            [sys.executable, str(repo / "scripts/pick_verifier.py")],
            input=body,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
            cwd=repo,
        )
        actual = json.loads(completed.stdout)
        entry["actions"].append(
            {
                "action": "Run pick_verifier.py with PR author lines on stdin",
                "journey": "verifier-selection",
                "body": body,
                "expected": expected,
                "actual": actual,
            }
        )
        for key, value in expected.items():
            if actual.get(key) != value:
                errors.append(f"{body.strip()}: expected {key}={value!r}, got {actual.get(key)!r}")
    if errors:
        entry["error"] = "\n".join(errors)
    else:
        entry["status"] = "passed"
except (OSError, subprocess.SubprocessError, ValueError) as error:
    entry["error"] = str(error)
print(json.dumps(entry, indent=2))
sys.exit(0 if entry["status"] == "passed" else 1)
