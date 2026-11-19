#!/usr/bin/env python3
import subprocess
import unittest
from pathlib import Path

import select_verifier_scope as selector

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / ".claude/skills/verify-sf-companion/evals/eval.py"
CASES = ROOT / ".claude/skills/verify-sf-companion/evals/cases.json"
FEATURES = ROOT / ".claude/skills/verify-sf-companion/features"
NON_EVAL = {"access-anonymous"}


def journeys_from_map():
    known = sorted(
        {
            journey
            for feature in selector.read_features(FEATURES)
            for journey in feature["journeys"]
        }
    )
    return [journey for journey in known if journey not in NON_EVAL]


class TestVerifyEvalJourneys(unittest.TestCase):
    def test_eval_journeys_match_feature_map(self):
        completed = subprocess.run(
            ["python3", str(EVAL), "journeys", "--cases", str(CASES)],
            capture_output=True,
            text=True,
            check=True,
        )
        got = completed.stdout.strip().split(",") if completed.stdout.strip() else []
        self.assertEqual(got, journeys_from_map())


if __name__ == "__main__":
    unittest.main()
