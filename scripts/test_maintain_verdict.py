#!/usr/bin/env python3
import itertools
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import maintain_verdict as verdict

STEPS = ("pstack", "journeys", "review", "clean")
REASONS = {
    "pstack": "The pstack pin check did not pass.",
    "journeys": "The full journey run did not pass.",
    "review": "The review step did not finish cleanly.",
    "clean": "The review changed a tracked file.",
}
CLEAN = {step: "success" for step in STEPS}
NOT_SUCCESS = ("failure", "skipped", "cancelled", "", None)


def trace(text):
    return "\n".join(
        json.dumps(event)
        for event in [
            {"type": "message_start", "message": {"role": "assistant", "content": []}},
            {
                "type": "message_end",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": f"Checked every feature file.\n\nVERDICT: {text}\n\n## Findings\n- None."}],
                },
            },
        ]
    )


class MaintainVerdictTest(unittest.TestCase):
    def setUp(self):
        self.records = Path(tempfile.mkdtemp())

    def write(self, text):
        (self.records / "review.jsonl").write_text(text, encoding="utf-8")

    def decide(self, outcomes, review="CLEAN"):
        self.write(trace(review))
        return verdict.decide(outcomes, self.records)

    def test_every_step_passing_with_a_clean_verdict_reports_no_drift(self):
        decision = self.decide(CLEAN)
        self.assertFalse(decision["drift"])
        self.assertEqual(decision["verdict"], "CLEAN")
        self.assertEqual(decision["reasons"], [])

    def test_any_step_that_is_not_success_is_drift_even_when_the_review_says_clean(self):
        for step in STEPS:
            for outcome in NOT_SUCCESS:
                with self.subTest(step=step, outcome=outcome):
                    decision = self.decide({**CLEAN, step: outcome})
                    self.assertTrue(decision["drift"])
                    self.assertIn(REASONS[step], decision["reasons"])

    def test_only_all_success_can_report_no_drift(self):
        values = ("success",) + NOT_SUCCESS
        for combination in itertools.product(values, repeat=len(STEPS)):
            outcomes = dict(zip(STEPS, combination))
            with self.subTest(outcomes=outcomes):
                decision = self.decide(outcomes)
                self.assertEqual(decision["drift"], combination != ("success",) * len(STEPS))

    def test_a_failed_journey_run_is_never_clean(self):
        decision = self.decide({**CLEAN, "journeys": "failure"})
        self.assertTrue(decision["drift"])
        self.assertEqual(decision["verdict"], "CLEAN")
        self.assertEqual(decision["reasons"], [REASONS["journeys"]])

    def test_a_skipped_journey_run_is_never_clean(self):
        decision = self.decide({**CLEAN, "journeys": "skipped"})
        self.assertTrue(decision["drift"])
        self.assertEqual(decision["reasons"], [REASONS["journeys"]])

    def test_a_skipped_review_is_never_clean(self):
        decision = self.decide({**CLEAN, "review": "skipped"})
        self.assertTrue(decision["drift"])
        self.assertEqual(decision["reasons"], [REASONS["review"]])

    def test_a_failed_review_step_is_drift_even_when_it_wrote_a_clean_verdict(self):
        decision = self.decide({**CLEAN, "review": "failure"})
        self.assertTrue(decision["drift"])
        self.assertIn(REASONS["review"], decision["reasons"])

    def test_a_failed_pstack_pin_is_drift(self):
        decision = self.decide({**CLEAN, "pstack": "failure"})
        self.assertTrue(decision["drift"])
        self.assertEqual(decision["reasons"], [REASONS["pstack"]])

    def test_a_changed_tracked_file_is_drift(self):
        decision = self.decide({**CLEAN, "clean": "failure"})
        self.assertTrue(decision["drift"])
        self.assertEqual(decision["reasons"], [REASONS["clean"]])

    def test_a_drift_verdict_is_drift(self):
        decision = self.decide(CLEAN, review="DRIFT")
        self.assertTrue(decision["drift"])
        self.assertEqual(decision["verdict"], "DRIFT")
        self.assertEqual(decision["reasons"], ["The review found drift."])

    def test_a_missing_verdict_line_is_drift(self):
        self.write(json.dumps({"type": "message_end", "message": {"role": "assistant", "content": []}}))
        decision = verdict.decide(CLEAN, self.records)
        self.assertTrue(decision["drift"])
        self.assertIsNone(decision["verdict"])
        self.assertEqual(decision["reasons"], ["The review returned no verdict line."])

    def test_an_empty_or_missing_trace_is_drift(self):
        self.assertTrue(verdict.decide(CLEAN, self.records)["drift"])
        self.write("")
        self.assertTrue(verdict.decide(CLEAN, self.records)["drift"])
        self.assertTrue(verdict.decide(CLEAN, self.records / "absent")["drift"])

    def test_malformed_trace_lines_are_skipped(self):
        self.write("{not json\n" + trace("CLEAN"))
        decision = verdict.decide(CLEAN, self.records)
        self.assertFalse(decision["drift"])
        self.assertEqual(decision["verdict"], "CLEAN")

    def test_every_failure_is_listed_in_step_order(self):
        decision = self.decide({step: "failure" for step in STEPS}, review="DRIFT")
        self.assertEqual(decision["reasons"], [REASONS[step] for step in STEPS] + ["The review found drift."])

    def test_a_missing_outcome_is_drift(self):
        self.write(trace("CLEAN"))
        self.assertTrue(verdict.decide({}, self.records)["drift"])

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
            [sys.executable, Path(__file__).with_name("maintain_verdict.py")],
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        decision = json.loads(output)
        self.assertTrue(decision["drift"])
        self.assertEqual(decision["reasons"], [REASONS["journeys"]])

    def test_the_command_treats_a_skipped_journey_run_as_drift(self):
        self.write(trace("CLEAN"))
        output = subprocess.run(
            [sys.executable, Path(__file__).with_name("maintain_verdict.py")],
            env={
                **os.environ,
                "RECORDS": str(self.records),
                "PSTACK_OUTCOME": "success",
                "JOURNEYS_OUTCOME": "skipped",
                "REVIEW_OUTCOME": "skipped",
                "CLEAN_OUTCOME": "success",
            },
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        decision = json.loads(output)
        self.assertTrue(decision["drift"])
        self.assertEqual(decision["reasons"], [REASONS["journeys"], REASONS["review"]])


if __name__ == "__main__":
    unittest.main()
