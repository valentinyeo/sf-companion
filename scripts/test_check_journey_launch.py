#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

import check_journey_launch as launch

VERIFY = ".claude/skills/verify-sf-companion/verify.mjs"
FEATURE = ".claude/skills/verify-sf-companion/features/items.md"

MJS = """const seededFactoryJourneys = [
  "factory-entry",
];
const seededHubJourneys = [
  "home-links",
  "items-invalid",
];
const shareJourneys = [
  "share-publish",
];
const seededJourneys = [
  ...seededFactoryJourneys,
  ...seededHubJourneys,
  ...shareJourneys,
];
const sparseJourneys = [
  "shipping-missing",
];
const runEmpty = [
  "home-empty",
  "reports-index-empty",
].some(wants);
const runLive = wants("access-anonymous");
"""

FEATURES = """- `factory-entry` opens the factory.
- `home-links` opens the indexes.
- `items-invalid` answers 400.
- `share-publish` publishes.
- `shipping-missing` says the chart is gone.
- `home-empty` says a section holds nothing.
- `reports-index-empty` says the index holds nothing.
- `access-anonymous` redirects to the login.
"""


class JourneyLaunchCheckTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.write(VERIFY, MJS)
        self.write(FEATURE, FEATURES)

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def test_every_listed_journey_is_launched(self):
        self.assertEqual(launch.check(str(self.root)), [])

    def test_a_seeded_journey_missing_from_its_launch_group_fails(self):
        self.write(FEATURE, FEATURES + "- `items-invalid-slug` answers 400.\n")
        errors = launch.check(str(self.root))
        self.assertEqual(len(errors), 1)
        self.assertIn("items-invalid-slug", errors[0])
        self.assertIn("run.sh --journeys=items-invalid-slug", errors[0])

    def test_an_empty_state_journey_missing_from_run_empty_fails(self):
        self.write(
            VERIFY,
            MJS.replace('  "reports-index-empty",\n', ""),
        )
        errors = launch.check(str(self.root))
        self.assertEqual(len(errors), 1)
        self.assertIn("reports-index-empty", errors[0])

    def test_a_launched_journey_no_feature_file_lists_fails(self):
        self.write(
            VERIFY,
            MJS.replace(
                'const seededHubJourneys = [\n',
                'const seededHubJourneys = [\n  "home-ghost",\n',
            ),
        )
        errors = launch.check(str(self.root))
        self.assertEqual(len(errors), 1)
        self.assertIn("home-ghost", errors[0])
        self.assertIn("no feature file lists it", errors[0])

    def test_a_missing_runner_fails(self):
        (self.root / VERIFY).unlink()
        errors = launch.check(str(self.root))
        self.assertEqual(len(errors), 1)
        self.assertIn("verify.mjs is missing", errors[0])


if __name__ == "__main__":
    unittest.main()
