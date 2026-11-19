#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import drift_decision as drift

CLEAN = {
    "pstack": "success",
    "journeys": "success",
    "review": "success",
    "clean": "success",
}


def trace(verdict):
    return "\n".join(
        json.dumps(event)
        for event in [
            {"type": "message_start", "message": {"role": "assistant", "content": []}},
            {
                "type": "message_end",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": f"Checked every feature file.\n\nVERDICT: {verdict}\n\n## Findings\n- None."}],
                },
            },
        ]
    )


class DriftDecisionTest(unittest.TestCase):
    def setUp(self):
        self.records = Path(tempfile.mkdtemp())

    def write(self, text):
        (self.records / "review.jsonl").write_text(text, encoding="utf-8")

    def test_every_step_passing_with_a_clean_verdict_reports_no_drift(self):
        self.write(trace("CLEAN"))
        decision = drift.decide(CLEAN, self.records)
        self.assertFalse(decision["drift"])
        self.assertEqual(decision["verdict"], "CLEAN")
        self.assertEqual(decision["reasons"], [])

    def test_a_failed_journey_run_is_drift_even_when_the_review_says_clean(self):
        self.write(trace("CLEAN"))
        decision = drift.decide({**CLEAN, "journeys": "failure"}, self.records)
        self.assertTrue(decision["drift"])
        self.assertEqual(decision["reasons"], ["The full journey run did not pass."])

    def test_a_failed_review_step_is_drift_even_when_it_wrote_a_clean_verdict(self):
        self.write(trace("CLEAN"))
        decision = drift.decide({**CLEAN, "review": "failure"}, self.records)
        self.assertTrue(decision["drift"])
        self.assertIn("The review step did not finish cleanly.", decision["reasons"])

    def test_a_failed_pstack_pin_is_drift(self):
        self.write(trace("CLEAN"))
        decision = drift.decide({**CLEAN, "pstack": "failure"}, self.records)
        self.assertTrue(decision["drift"])
        self.assertEqual(decision["reasons"], ["The pstack pin check did not pass."])

    def test_a_changed_tracked_file_is_drift(self):
        self.write(trace("CLEAN"))
        decision = drift.decide({**CLEAN, "clean": "failure"}, self.records)
        self.assertTrue(decision["drift"])
        self.assertEqual(decision["reasons"], ["The review changed a tracked file."])

    def test_a_drift_verdict_is_drift(self):
        self.write(trace("DRIFT"))
        decision = drift.decide(CLEAN, self.records)
        self.assertTrue(decision["drift"])
        self.assertEqual(decision["verdict"], "DRIFT")
        self.assertEqual(decision["reasons"], ["The review found drift."])

    def test_a_missing_verdict_line_is_drift(self):
        self.write(json.dumps({"type": "message_end", "message": {"role": "assistant", "content": []}}))
        decision = drift.decide(CLEAN, self.records)
        self.assertTrue(decision["drift"])
        self.assertIsNone(decision["verdict"])
        self.assertEqual(decision["reasons"], ["The review returned no verdict line."])

    def test_an_empty_or_missing_trace_is_drift(self):
        self.assertTrue(drift.decide(CLEAN, self.records)["drift"])
        self.write("")
        self.assertTrue(drift.decide(CLEAN, self.records)["drift"])
        self.assertTrue(drift.decide(CLEAN, self.records / "absent")["drift"])

    def test_malformed_trace_lines_are_skipped(self):
        self.write("{not json\n" + trace("CLEAN"))
        decision = drift.decide(CLEAN, self.records)
        self.assertFalse(decision["drift"])
        self.assertEqual(decision["verdict"], "CLEAN")

    def test_the_command_writes_the_decision_from_the_environment(self):
        self.write(trace("CLEAN"))
        environment = {
            **os.environ,
            "RECORDS": str(self.records),
            "PSTACK_OUTCOME": "success",
            "JOURNEYS_OUTCOME": "failure",
            "REVIEW_OUTCOME": "success",
            "CLEAN_OUTCOME": "success",
        }
        output = subprocess.run(
            [sys.executable, Path(__file__).with_name("drift_decision.py")],
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        decision = json.loads(output)
        self.assertTrue(decision["drift"])
        self.assertEqual(decision["reasons"], ["The full journey run did not pass."])


if __name__ == "__main__":
    unittest.main()
