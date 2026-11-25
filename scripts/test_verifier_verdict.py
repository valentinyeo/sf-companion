#!/usr/bin/env python3
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pick_verifier as picker
import verifier_verdict as parsed

FIXTURES = Path("scripts/fixtures/verifier")
BASE_LINE = re.compile(r"^(PASS\+NOTES|PASS|FAIL)\s*$", re.MULTILINE)


def reply_of(trace):
    return parsed.read_reply(trace)[0]


def messages_of(trace):
    return [
        json.loads(line)
        for line in Path(trace).read_text(encoding="utf-8").split("\n")
        if line.strip()
    ]


def text_of(message):
    return "\n".join(
        part["text"] for part in message["message"]["content"] if part["type"] == "text"
    )


class CutResponseTest(unittest.TestCase):
    def test_reads_the_verdict_a_bold_line_hid_from_the_base_rule(self):
        trace = FIXTURES / "bolded-verdict.jsonl"
        text = reply_of(trace)
        self.assertIsNone(BASE_LINE.search(text))
        self.assertEqual(parsed.find_verdict(text), "PASS+NOTES")

    def test_keeps_the_whole_reply_for_the_comment(self):
        text = reply_of(FIXTURES / "bolded-verdict.jsonl")
        self.assertIn("## What I ran", text)
        self.assertTrue(text.endswith("the layout handle it."))

    def test_decides_the_stored_run(self):
        result = parsed.decide([FIXTURES / "bolded-verdict.jsonl"])
        self.assertEqual(result["verdict"], "PASS+NOTES")
        self.assertEqual(result["lane"], 1)
        self.assertIsNone(result["reason"])


class WholeTraceTest(unittest.TestCase):
    def test_reads_a_verdict_the_last_message_dropped(self):
        trace = FIXTURES / "verdict-in-earlier-turn.jsonl"
        self.assertIsNone(parsed.find_verdict(text_of(messages_of(trace)[-1])))
        self.assertEqual(parsed.decide([trace])["verdict"], "PASS+NOTES")

    def test_reads_the_first_lane_that_answers(self):
        trace = FIXTURES / "bolded-verdict.jsonl"
        self.assertEqual(parsed.decide([trace, trace])["lane"], 1)


class NoVerdictTest(unittest.TestCase):
    def test_reports_a_run_that_never_wrote_a_reply(self):
        result = parsed.decide([FIXTURES / "progress-only.jsonl"])
        self.assertIsNone(result["verdict"])
        self.assertIn("tool call", result["reason"])

    def test_reports_a_missing_trace(self):
        result = parsed.decide([FIXTURES / "absent.jsonl"])
        self.assertIsNone(result["verdict"])
        self.assertIn("no reply", result["reason"])

    def test_reports_a_reply_without_a_verdict_line(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory, "trace.jsonl")
            trace.write_text(
                json.dumps(
                    {
                        "type": "message_end",
                        "message": {
                            "role": "assistant",
                            "stopReason": "stop",
                            "content": [{"type": "text", "text": "The head looks fine."}],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result = parsed.decide([trace])
            self.assertIsNone(result["verdict"])
            self.assertIn("no verdict line", result["reason"])
            self.assertIn("The head looks fine.", result["reply"])

    def test_the_second_lane_supplies_a_verdict_the_first_lane_lost(self):
        result = parsed.decide(
            [FIXTURES / "progress-only.jsonl", FIXTURES / "bolded-verdict.jsonl"]
        )
        self.assertEqual(result["verdict"], "PASS+NOTES")
        self.assertEqual(result["lane"], 2)


class DecorationTest(unittest.TestCase):
    def test_accepts_the_shapes_a_model_writes(self):
        for line, expected in (
            ("PASS", "PASS"),
            ("**PASS+NOTES**", "PASS+NOTES"),
            ("__FAIL__", "FAIL"),
            ("`FAIL`", "FAIL"),
            ("## PASS", "PASS"),
            ("- FAIL", "FAIL"),
            ("> PASS+NOTES", "PASS+NOTES"),
            ("PASS+NOTES.", "PASS+NOTES"),
            ("Verdict: PASS", "PASS"),
            ("**Verdict: FAIL**", "FAIL"),
            ("fail", "FAIL"),
        ):
            with self.subTest(line=line):
                self.assertEqual(
                    parsed.find_verdict(f"findings above\n\n{line}\n\nfindings below"),
                    expected,
                )

    def test_accepts_a_verdict_line_with_a_short_reason_after_it(self):
        self.assertEqual(
            parsed.find_verdict("**PASS+NOTES**: one regression risk below."),
            "PASS+NOTES",
        )
        self.assertEqual(
            parsed.find_verdict("FAIL — the head drops the age line."), "FAIL"
        )

    def test_ignores_a_verdict_word_inside_a_sentence(self):
        for body in (
            "The head does not PASS.",
            "I would not call this a FAIL.",
            "PASS+NOTES means every case passed.",
            "3. Finish with exactly one standalone line: PASS, PASS+NOTES, or FAIL.",
        ):
            with self.subTest(body=body):
                self.assertIsNone(parsed.find_verdict(body))

    def test_prefers_a_bare_line_over_a_quoted_rubric_line(self):
        body = "- FAIL: a case failed, a person would see something wrong.\n\n**PASS**"
        self.assertEqual(parsed.find_verdict(body), "PASS")


class CommandLineTest(unittest.TestCase):
    def test_writes_the_verdict_file_the_workflow_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory, "verdict.json")
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/verifier_verdict.py",
                    "--trace",
                    str(FIXTURES / "bolded-verdict.jsonl"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            written = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(written["verdict"], "PASS+NOTES")
            self.assertEqual(json.loads(result.stdout)["lane"], 1)


class LaneTest(unittest.TestCase):
    def test_lists_a_second_lane_behind_the_first_when_an_author_is_deepseek(self):
        result = picker.pick_verifier("Author model: deepseek/deepseek-v4.1-flash\n")
        self.assertEqual([lane["family"] for lane in result["lanes"]], ["zai", "openai"])
        self.assertEqual(result["family"], "zai")

    def test_offers_the_one_lane_an_author_left(self):
        result = picker.pick_verifier("Author model: zai/glm-5.3-flash\n")
        self.assertEqual([lane["family"] for lane in result["lanes"]], ["deepseek"])


if __name__ == "__main__":
    unittest.main()
