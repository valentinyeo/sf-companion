import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import check_bug_pr

FEATURE = ".claude/skills/verify-sf-companion/features/items.md"
FEATURE_BODY = "- `items-invalid` answers 400 for a slug outside the allowed character set.\n- `items-invalid-slug` answers 400 for an empty or multi-segment slug.\n"
BODY = "## Why\n\nThe slug is never checked.\n\nRepro journey: items-invalid-slug\n"
TEST = "apps/web/test/slug.test.ts"
APP = "apps/web/src/entry.server.ts"
JOURNEY = ".claude/skills/verify-sf-companion/verify.mjs"


class Repo:
    def __init__(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.git("init", "-q")
        self.git("config", "user.email", "verifier@example.com")
        self.git("config", "user.name", "Verifier")
        self.write(FEATURE, FEATURE_BODY)
        self.base = self.commit("base")

    def git(self, *arguments):
        completed = subprocess.run(
            ["git", *arguments],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
            env={
                key: value
                for key, value in os.environ.items()
                if not key.startswith("GIT_")
            },
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr)
        return completed.stdout.strip()

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")


class BugPrCheckTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.directory.cleanup)

    def check(self, title="fix(items): invalid slugs answer 400", labels="", body=BODY):
        return check_bug_pr.check(
            str(self.repo.root),
            title,
            labels.split(","),
            body,
            self.repo.base,
            self.repo.git("rev-parse", "HEAD"),
        )

    def test_a_feature_pull_request_passes_with_no_journey(self):
        self.repo.write(TEST, "test\n")
        self.repo.commit("test")
        self.assertEqual(self.check(title="feat(items): add a page"), [])

    def test_a_fixture_title_is_not_a_fix(self):
        self.repo.write(TEST, "test\n")
        self.repo.commit("test")
        self.assertEqual(self.check(title="fixture(items): reseed the hub"), [])

    def test_a_bug_label_without_a_repro_journey_fails(self):
        errors = self.check(labels="bug", body="## Why\n\nIt breaks.\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("names no repro journey", errors[0])

    def test_an_unknown_repro_journey_fails(self):
        errors = self.check(body="Repro journey: items-nope\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("is not in the verification map", errors[0])
        self.assertIn("items-invalid-slug", errors[0])

    def test_a_repro_journey_with_an_empty_or_duplicate_id_fails(self):
        self.assertEqual(len(self.check(body="Repro journey:\n")), 1)
        errors = self.check(body="Repro journey: items-invalid-slug, items-nope\n")
        self.assertEqual(len(errors), 1)

    def test_a_test_commit_before_the_fix_passes(self):
        self.repo.write(TEST, "test\n")
        self.repo.commit("test: add the failing slug test")
        self.repo.write(APP, "fix\n")
        self.repo.commit("fix(items): invalid slugs answer 400")
        self.assertEqual(self.check(), [])

    def test_a_journey_commit_before_the_fix_passes(self):
        self.repo.write(FEATURE, FEATURE_BODY + "- `items-invalid-slug` is driven.\n")
        self.repo.write(JOURNEY, "await record('slug', 'items-invalid-slug');\n")
        self.repo.commit("verify: drive items-invalid-slug")
        self.repo.write(APP, "fix\n")
        self.repo.commit("fix(items): invalid slugs answer 400")
        self.assertEqual(self.check(), [])

    def test_a_fix_commit_before_the_test_fails(self):
        self.repo.write(APP, "fix\n")
        self.repo.commit("fix(items): invalid slugs answer 400")
        self.repo.write(TEST, "test\n")
        self.repo.commit("test: add the failing slug test")
        errors = self.check()
        self.assertEqual(len(errors), 1)
        self.assertIn("comes before the first commit that adds the failing test", errors[0])

    def test_a_branch_with_no_test_commit_fails(self):
        self.repo.write(APP, "fix\n")
        self.repo.commit("fix(items): invalid slugs answer 400")
        errors = self.check()
        self.assertEqual(len(errors), 1)
        self.assertIn("adds a failing test", errors[0])

    def test_a_hook_environment_does_not_reach_the_temp_repo(self):
        foreign = Repo()
        self.addCleanup(foreign.directory.cleanup)
        os.environ["GIT_DIR"] = str(foreign.root / ".git")
        self.addCleanup(os.environ.pop, "GIT_DIR", None)
        self.repo.write(TEST, "test\n")
        self.repo.commit("test: add the failing slug test")
        self.assertEqual(foreign.git("rev-parse", "HEAD"), foreign.base)

    def test_a_branch_with_no_commit_fails(self):
        with self.assertRaises(RuntimeError) as raised:
            self.check()
        self.assertIn("branch order cannot be read", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
