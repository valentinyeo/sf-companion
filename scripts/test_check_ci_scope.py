#!/usr/bin/env python3
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
permissions:
  contents: read
  actions: read
  pull-requests: write
concurrency:
  group: pstack-verifier-${{ github.event.pull_request.number }}
  cancel-in-progress: true
jobs:
  pstack-verifier:
    runs-on: ubuntu-latest
    steps:
      - name: Refuse what cannot be verified
        if: github.event.pull_request.head.repo.full_name != github.repository
        run: |
          echo "pstack-verifier cannot verify a fork pull request" >&2
          exit 1
      - name: Select the touched journeys
        run: python3 scripts/select_verifier_scope.py
      - name: Run the head journeys
        run: .claude/skills/verify-sf-companion/run.sh --journeys=$JOURNEYS
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


MAINTAIN = """name: Verify skill maintenance
on:
  schedule:
    - cron: "23 4 * * 1"
  workflow_dispatch:
permissions:
  contents: read
  issues: write
concurrency:
  group: verify-skill-maintain
  cancel-in-progress: true
jobs:
  maintain:
    if: github.event_name == 'workflow_dispatch' || github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          repository: cursor/plugins
          ref: 0123456789abcdef0123456789abcdef01234567
          path: pstack-source
      - run: scripts/pstack_pin_drift.py --source pstack-source/pstack/.cursor-plugin/plugin.json
      - run: .claude/skills/verify-sf-companion/run.sh --live
      - run: echo "verify map drift"
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
        self.write("pstack-verifier.yml", VERIFIER)
        self.write("nightly-journeys.yml", NIGHTLY)
        self.write("verify-skill-maintain.yml", MAINTAIN)

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
        self.write(
            "pstack-verifier.yml",
            VERIFIER.replace(" --journeys=$JOURNEYS", ""),
        )
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("--journeys", errors[0])

    def test_a_verifier_job_that_can_skip_is_rejected(self):
        self.clean()
        self.write(
            "pstack-verifier.yml",
            VERIFIER.replace(
                "  pstack-verifier:\n    runs-on",
                "  pstack-verifier:\n    if: github.event.pull_request.head.repo.full_name == github.repository\n    runs-on",
            ),
        )
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("skip", errors[0])
        self.assertIn("required check", errors[0])

    def test_a_verifier_without_a_fork_refusal_is_rejected(self):
        self.clean()
        self.write(
            "pstack-verifier.yml",
            VERIFIER.replace(
                "      - name: Refuse what cannot be verified\n"
                "        if: github.event.pull_request.head.repo.full_name != github.repository\n"
                "        run: |\n"
                '          echo "pstack-verifier cannot verify a fork pull request" >&2\n'
                "          exit 1\n",
                "",
            ),
        )
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("fork", errors[0])

    def test_a_verifier_without_the_job_is_rejected(self):
        self.clean()
        self.write("pstack-verifier.yml", "name: Pstack verifier\non:\n  pull_request:\n")
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 2)
        self.assertIn("pstack-verifier", " ".join(errors))

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

    def test_nightly_with_a_journey_selector_is_rejected(self):
        self.clean()
        self.write("nightly-journeys.yml", NIGHTLY.replace("run.sh --live", "run.sh --live --journeys=factory-entry"))
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("--journeys", errors[0])

    def test_nightly_with_a_quoted_journey_selector_is_rejected(self):
        self.clean()
        self.write(
            "nightly-journeys.yml",
            NIGHTLY.replace("run.sh --live", 'run.sh --live --journeys""=factory-entry'),
        )
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("--journeys", errors[0])

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

    def test_maintain_on_pull_requests_is_rejected(self):
        self.clean()
        self.write("verify-skill-maintain.yml", MAINTAIN.replace("  workflow_dispatch:", "  workflow_dispatch:\n  pull_request:"))
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("pull requests", errors[0])

    def test_maintain_without_a_schedule_is_rejected(self):
        self.clean()
        self.write("verify-skill-maintain.yml", MAINTAIN.replace("  schedule:\n    - cron: \"23 4 * * 1\"\n", ""))
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("schedule", errors[0])

    def test_maintain_without_a_branch_guard_is_rejected(self):
        self.clean()
        self.write("verify-skill-maintain.yml", MAINTAIN.replace("    if: github.event_name == 'workflow_dispatch' || github.ref == 'refs/heads/main'\n", ""))
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("refs/heads/main", errors[0])

    def test_maintain_without_cancellation_is_rejected(self):
        self.clean()
        self.write("verify-skill-maintain.yml", MAINTAIN.replace("  cancel-in-progress: true\n", ""))
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("cancel-in-progress", errors[0])

    def test_maintain_with_a_floating_pstack_source_is_rejected(self):
        self.clean()
        self.write("verify-skill-maintain.yml", MAINTAIN.replace("ref: 0123456789abcdef0123456789abcdef01234567", "ref: main"))
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("cursor/plugins", errors[0])

    def test_maintain_without_the_journeys_is_rejected(self):
        self.clean()
        self.write("verify-skill-maintain.yml", MAINTAIN.replace("      - run: .claude/skills/verify-sf-companion/run.sh --live\n", ""))
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("run.sh", errors[0])

    def test_maintain_without_a_drift_issue_is_rejected(self):
        self.clean()
        self.write("verify-skill-maintain.yml", MAINTAIN.replace("  issues: write\n", "").replace('echo "verify map drift"', 'echo "clean"'))
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("verify map drift", errors[0])

    def test_missing_maintain_is_rejected(self):
        self.clean()
        (self.folder / "verify-skill-maintain.yml").unlink()
        errors = scope.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("verify-skill-maintain.yml", errors[0])

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
