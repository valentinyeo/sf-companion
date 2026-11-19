#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

import pstack_pin_drift as pin

SKILL = """---
name: verify-sf-companion
---

pstack: 0.15.44
"""

SOURCE = '{"name": "pstack", "version": "0.15.44"}'


class PinDriftTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def write(self, name, text):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def report(self, skill=SKILL, source=SOURCE):
        return pin.report(self.write("SKILL.md", skill), self.write("plugin.json", source))

    def one(self, skill=SKILL, source=SOURCE):
        errors = self.report(skill, source)
        self.assertEqual(len(errors), 1)
        return errors[0]

    def test_matching_versions_are_aligned(self):
        self.assertEqual(self.report(), [])

    def test_newer_pinned_source_is_drift(self):
        error = self.one(source='{"version": "0.15.45"}')
        self.assertIn("0.15.44", error)
        self.assertIn("0.15.45", error)
        self.assertIn("/maintain-verification-skill", error)

    def test_missing_recorded_line_is_drift(self):
        error = self.one(skill="---\nname: verify-sf-companion\n---\n")
        self.assertIn("pstack:", error)

    def test_a_line_with_trailing_text_is_not_a_recorded_version(self):
        error = self.one(skill="pstack: 0.15.44 extra\n")
        self.assertIn("pstack:", error)

    def test_unreadable_manifest_is_drift(self):
        error = self.one(source="{not json")
        self.assertIn("version", error)

    def test_manifest_without_a_version_is_drift(self):
        error = self.one(source='{"name": "pstack"}')
        self.assertIn("version", error)

    def test_manifest_that_is_not_an_object_is_drift(self):
        error = self.one(source='["pstack"]')
        self.assertIn("version", error)

    def test_missing_skill_is_drift(self):
        source = self.write("plugin.json", SOURCE)
        errors = pin.report(self.root / "missing.md", source)
        self.assertEqual(len(errors), 1)
        self.assertIn("--skill", errors[0])

    def test_missing_source_is_drift(self):
        skill = self.write("SKILL.md", SKILL)
        errors = pin.report(skill, self.root / "missing.json")
        self.assertEqual(len(errors), 1)
        self.assertIn("--source", errors[0])


if __name__ == "__main__":
    unittest.main()
