import tempfile
import unittest
from pathlib import Path

import check_ci_scope as scope

CLEAN_CI = """name: CI
on:
  push:
    branches: [main]
  pull_request:
"""

VERIFIER = """name: Pstack verifier
on:
  pull_request:
"""

NIGHTLY = """name: Nightly journeys
on:
  schedule:
    - cron: "17 3 * * *"
  workflow_dispatch:
concurrency:
  group: nightly-journeys
  cancel-in-progress: true
jobs:
  journeys:
    if: github.event_name == 'workflow_dispatch' || github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - run: .claude/skills/verify-sf-companion/run.sh --live
      - uses: actions/upload-artifact@v4
        if: always()
"""


class ScopeTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.folder = self.root / ".github" / "workflows"
        self.folder.mkdir(parents=True)

    def write(self, name, source):
        (self.folder / name).write_text(source, encoding="utf-8")

    def clean(self):
        self.write("ci.yml", CLEAN_CI)
        self.write("pstack-verifier.yml", VERIFIER + "steps:\n  - run: run.sh --journeys=$JOURNEYS\n")
        self.write("nightly-journeys.yml", NIGHTLY)

    def test_clean_setup_has_no_errors(self):
        self.clean()
        self.assertEqual(scope.check(self.root), [])

    def test_inline_pull_request_trigger_cannot_hide_a_browser(self):
        self.clean()
        self.write("smoke.yml", "on: [pull_request]\njobs:\n  x:\n    steps:\n      - run: pnpm exec playwright test\n")
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("playwright", errors[0])

    def test_browser_on_pull_requests_is_rejected(self):
        self.clean()
        self.write("ci.yml", CLEAN_CI + "steps:\n  - uses: actions/setup-node\n  - run: pnpm exec playwright test\n")
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("ci.yml", errors[0])
        self.assertIn("playwright", errors[0])

    def test_journey_helper_on_pull_requests_is_rejected(self):
        self.clean()
        self.write("smoke.yml", "on:\n  pull_request:\njobs:\n  x:\n    steps:\n      - run: .claude/skills/verify-sf-companion/run.sh\n")
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("smoke.yml", errors[0])

    def test_verifier_without_a_journey_list_is_rejected(self):
        self.clean()
        self.write("pstack-verifier.yml", VERIFIER + "steps:\n  - run: run.sh\n")
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("--journeys", errors[0])

    def test_nightly_on_pull_requests_is_rejected(self):
        self.clean()
        self.write("nightly-journeys.yml", NIGHTLY.replace("  workflow_dispatch:", "  workflow_dispatch:\n  pull_request:"))
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("pull_request", errors[0])

    def test_nightly_without_a_schedule_is_rejected(self):
        self.clean()
        self.write("nightly-journeys.yml", NIGHTLY.replace("  schedule:\n    - cron: \"17 3 * * *\"\n", ""))
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("schedule", errors[0])

    def test_nightly_without_any_branch_guard_is_rejected(self):
        self.clean()
        self.write("nightly-journeys.yml", NIGHTLY.replace("    if: github.event_name == 'workflow_dispatch' || github.ref == 'refs/heads/main'\n", ""))
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("refs/heads/main", errors[0])

    def test_missing_nightly_is_rejected(self):
        self.clean()
        (self.folder / "nightly-journeys.yml").unlink()
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("nightly-journeys.yml", errors[0])

    def test_missing_workflows_folder_is_rejected(self):
        self.assertEqual(len(scope.check(tempfile.mkdtemp())), 1)

    def test_trigger_reader_finds_block_and_inline_keys(self):
        self.assertEqual(scope.triggers("on:\n  push:\n  schedule:\n"), {"push", "schedule"})
        self.assertEqual(scope.triggers("on:\n  workflow_dispatch:\nconcurrency:\n  group: x\n"), {"workflow_dispatch"})
        self.assertEqual(scope.triggers("on: [pull_request, push]\n"), {"pull_request", "push"})
        self.assertEqual(scope.triggers("on: pull_request\n"), {"pull_request"})
        self.assertEqual(scope.triggers("on: {pull_request: {}}\n"), {"pull_request"})
        self.assertEqual(scope.triggers("on:\n  pull_request: {}\n"), {"pull_request"})


if __name__ == "__main__":
    unittest.main()
