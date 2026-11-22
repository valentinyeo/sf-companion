import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pick_verifier as picker


class FamilyTest(unittest.TestCase):
    def test_reads_a_family_from_anywhere_in_the_model_string(self):
        self.assertEqual(picker.family_of("deepseek/deepseek-v4.1-flash"), "deepseek")
        self.assertEqual(picker.family_of("opencode-go/deepseek-v4.1-flash"), "deepseek")
        self.assertEqual(picker.family_of("openai-codex/gpt-5.4"), "openai")
        self.assertEqual(picker.family_of("openai/gpt-6.1-sol"), "openai")
        self.assertEqual(picker.family_of("anthropic/claude-sonnet"), "anthropic")
        self.assertEqual(picker.family_of("google/gemini-4-neon"), "google")
        self.assertEqual(picker.family_of("x-ai/grok-4"), "xai")
        self.assertEqual(picker.family_of("meta-llama/llama-4"), "meta")
        self.assertEqual(picker.family_of("z-ai/glm-5"), "zai")
        self.assertEqual(picker.family_of("cursor/composer-2.5"), "cursor")
        self.assertIsNone(picker.family_of("stealth/ox-alpha"))
        self.assertIsNone(picker.family_of(""))

    def test_known_families_are_distinct(self):
        self.assertEqual(len(set(picker.KNOWN_FAMILIES)), len(picker.KNOWN_FAMILIES))


class AuthorTest(unittest.TestCase):
    def test_parses_one_author_line_per_author(self):
        authors, unknown = picker.parse_author_lines(
            "## Why\n\nAuthor model: deepseek/deepseek-v4.1-flash\n"
            "Author model: openai/gpt-6.1-sol\n"
        )
        self.assertEqual(unknown, [])
        self.assertEqual(
            authors,
            [
                {"family": "deepseek", "value": "deepseek/deepseek-v4.1-flash"},
                {"family": "openai", "value": "openai/gpt-6.1-sol"},
            ],
        )


class PickTest(unittest.TestCase):
    def test_fails_a_body_with_no_author_line(self):
        result = picker.pick_verifier("## Why\n\nNo authors named here.\n")
        self.assertEqual(result["status"], "fail")
        self.assertIn("No Author model line", result["reason"])

    def test_fails_an_unknown_family(self):
        result = picker.pick_verifier("Author model: stealth/ox-alpha\n")
        self.assertEqual(result["status"], "fail")
        self.assertIn("Unknown author model family", result["reason"])

    def test_fails_an_empty_author_line(self):
        result = picker.pick_verifier("Author model:\n")
        self.assertEqual(result["status"], "fail")
        self.assertIn("Unknown author model family", result["reason"])

    def test_picks_deepseek_flash_when_no_author_is_deepseek(self):
        result = picker.pick_verifier("Author model: anthropic/claude-sonnet\n")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["family"], "deepseek")
        self.assertEqual(result["provider"], "opencode-go")
        self.assertEqual(result["model"], "deepseek-v4.1-flash")
        self.assertEqual(result["secret"], "OPENCODE_API_KEY")

    def test_prefers_glm_flash_on_vercel_gateway_when_an_author_is_deepseek(self):
        result = picker.pick_verifier("Author model: deepseek/deepseek-v4.1-flash\n")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["family"], "zai")
        self.assertEqual(result["provider"], "vercel-ai-gateway")
        self.assertEqual(result["model"], "zai/glm-5.3-flash")
        self.assertEqual(result["secret"], "AI_GATEWAY_API_KEY")

    def test_treats_opencode_go_deepseek_as_a_deepseek_author(self):
        result = picker.pick_verifier("Author model: opencode-go/deepseek-v4.1-flash\n")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["family"], "zai")

    def test_skips_a_used_glm_family_and_picks_openai(self):
        result = picker.pick_verifier(
            "Author model: deepseek/deepseek-v4.1-flash\n"
            "Author model: zai/glm-5.3-flash\n"
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["family"], "openai")
        self.assertEqual(result["provider"], "openrouter")
        self.assertEqual(result["model"], "openai/gpt-6.1-sol")

    def test_fails_when_every_verifier_family_wrote_the_change(self):
        result = picker.pick_verifier(
            "Author model: deepseek/deepseek-v4.1-flash\n"
            "Author model: zai/glm-5.3-flash\n"
            "Author model: openai/gpt-6.1-sol\n"
        )
        self.assertEqual(result["status"], "fail")
        self.assertIn("Every verifier family", result["reason"])

    def test_fails_before_picking_when_any_author_family_is_unknown(self):
        result = picker.pick_verifier(
            "Author model: deepseek/deepseek-v4.1-flash\nAuthor model: stealth/ox-alpha\n"
        )
        self.assertEqual(result["status"], "fail")
        self.assertIn("stealth/ox-alpha", result["reason"])


class CommandLineTest(unittest.TestCase):
    def test_prints_json_from_a_body_file(self):
        with tempfile.TemporaryDirectory() as directory:
            body_file = Path(directory, "body.txt")
            body_file.write_text("Author model: deepseek/deepseek-v4.1-flash\n")
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/pick_verifier.py",
                    "--body-file",
                    str(body_file),
                ],
                capture_output=True,
                check=False,
                cwd=Path(__file__).resolve().parent.parent,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["family"], "zai")


if __name__ == "__main__":
    unittest.main()
