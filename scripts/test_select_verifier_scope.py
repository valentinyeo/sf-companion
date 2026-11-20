import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import select_verifier_scope as selector


FACTORY = {
    "codePaths": ["apps/web/src/features/factory.ts"],
    "id": "factory",
    "journeys": ["factory-entry", "factory-readings", "factory-empty"],
}
USAGE = {
    "codePaths": ["apps/web/src/client/app/update.ts"],
    "id": "usage",
    "journeys": ["usage-window", "usage-details"],
}
ACCESS = {
    "codePaths": ["apps/web/src/website.ts"],
    "id": "access",
    "journeys": ["access-anonymous"],
}
FEATURES = [FACTORY, USAGE, ACCESS]


class FeatureFileTest(unittest.TestCase):
    def test_reads_code_paths_and_journeys_from_a_feature_file(self):
        feature = selector.parse_feature(
            "# Factory\n\n## Sub-features\n\n- `factory-entry` supports direct loading.\n"
            "- `factory-empty` shows missing numbers.\n\n## Driving it\n\n"
            "- Direct entry. `page.goto('/factory')` returns 200.\n\n"
            "Code paths: `apps/web/src/features/factory.ts`, apps/web/src/content/feed.ts\n"
        )
        self.assertEqual(
            feature["journeys"], ["factory-entry", "factory-empty"]
        )
        self.assertEqual(
            feature["codePaths"],
            ["apps/web/src/features/factory.ts", "apps/web/src/content/feed.ts"],
        )

    def test_reads_feature_files_from_a_directory_and_ignores_the_index(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "factory.md").write_text(
                "- `factory-entry` loads.\n\nCode paths: apps/web/src/features/factory.ts\n"
            )
            Path(directory, "README.md").write_text("- `index-only` is not a feature.\n")
            features = selector.read_features(directory)
        self.assertEqual(
            features,
            [
                {
                    "codePaths": ["apps/web/src/features/factory.ts"],
                    "id": "factory",
                    "journeys": ["factory-entry"],
                }
            ],
        )


class MatchTest(unittest.TestCase):
    def test_maps_a_changed_source_file_to_its_feature_journeys(self):
        scope = selector.select_scope(
            ["apps/web/src/features/factory.ts"], FEATURES, []
        )
        self.assertEqual(scope["status"], "ok")
        self.assertEqual(scope["features"], ["factory"])
        self.assertEqual(
            scope["journeys"],
            ["factory-empty", "factory-entry", "factory-readings"],
        )
        self.assertFalse(scope["fallback"])

    def test_maps_a_directory_code_path_to_everything_under_it(self):
        scope = selector.select_scope(
            ["apps/web/src/client/app/update.ts"], FEATURES, []
        )
        self.assertEqual(scope["features"], ["usage"])
        self.assertEqual(scope["journeys"], ["usage-details", "usage-window"])

    def test_matches_a_prefix_only_on_a_path_boundary(self):
        self.assertTrue(
            selector.matches_code_path("apps/web/src/website.ts", "apps/web/src/website.ts")
        )
        self.assertFalse(
            selector.matches_code_path("apps/web/src/website.tsx", "apps/web/src/website.ts")
        )
        self.assertTrue(
            selector.matches_code_path(
                "apps/web/src/client/app/update.ts", "apps/web/src/client/app"
            )
        )
        self.assertTrue(
            selector.matches_code_path(
                "apps/web/src/client/app/update.ts", "apps/web/src/client/app/**"
            )
        )


class ReproTest(unittest.TestCase):
    def test_adds_journeys_named_in_the_pr_body(self):
        scope = selector.select_scope(
            ["apps/web/src/website.ts"], FEATURES, ["usage-window"]
        )
        self.assertEqual(scope["features"], ["access"])
        self.assertEqual(scope["journeys"], ["access-anonymous", "usage-window"])
        self.assertEqual(scope["repro"], ["usage-window"])

    def test_parses_repro_journey_lines(self):
        self.assertEqual(
            selector.parse_repro_journeys(
                "## Why\n\nRepro journey: factory-empty\n"
                "Repro journey: `usage-details`, access-anonymous\n"
            ),
            ["factory-empty", "usage-details", "access-anonymous"],
        )
        self.assertEqual(selector.parse_repro_journeys("no repro here"), [])

    def test_fails_an_unknown_repro_journey(self):
        scope = selector.select_scope(
            ["apps/web/src/website.ts"], FEATURES, ["factory-typo"]
        )
        self.assertEqual(scope["status"], "fail")
        self.assertIn("Unknown repro journey: factory-typo", scope["reason"])
        self.assertIn("factory-entry", scope["reason"])


def all_journeys():
    return [
        "access-anonymous",
        "factory-empty",
        "factory-entry",
        "factory-readings",
        "usage-details",
        "usage-window",
    ]


class HarnessTest(unittest.TestCase):
    def test_runs_every_journey_when_the_helper_changed(self):
        scope = selector.select_scope(
            [".claude/skills/verify-sf-companion/verify.mjs"], FEATURES, []
        )
        self.assertEqual(scope["status"], "ok")
        self.assertTrue(scope["harness"])
        self.assertEqual(scope["features"], ["factory", "usage", "access"])
        self.assertEqual(scope["journeys"], all_journeys())
        self.assertFalse(scope["fallback"])
        self.assertIn("verify.mjs", scope["reason"])

    def test_runs_every_journey_when_the_launcher_or_fixture_changed(self):
        for helper in ("run.sh", "fixture.json"):
            scope = selector.select_scope(
                [f".claude/skills/verify-sf-companion/{helper}"], FEATURES, []
            )
            self.assertTrue(scope["harness"], helper)
            self.assertEqual(scope["journeys"], all_journeys(), helper)

    def test_runs_every_journey_when_the_map_index_changed(self):
        scope = selector.select_scope(
            [".claude/skills/verify-sf-companion/features/README.md"], FEATURES, []
        )
        self.assertTrue(scope["harness"])
        self.assertEqual(scope["journeys"], all_journeys())

    def test_a_helper_change_wins_over_a_feature_file_change(self):
        scope = selector.select_scope(
            [
                ".claude/skills/verify-sf-companion/features/factory.md",
                ".claude/skills/verify-sf-companion/verify.mjs",
            ],
            FEATURES,
            [],
        )
        self.assertTrue(scope["harness"])
        self.assertEqual(scope["journeys"], all_journeys())


class FeatureFileChangeTest(unittest.TestCase):
    def test_one_feature_file_selects_only_its_own_journeys(self):
        scope = selector.select_scope(
            [".claude/skills/verify-sf-companion/features/usage.md"], FEATURES, []
        )
        self.assertEqual(scope["status"], "ok")
        self.assertFalse(scope["harness"])
        self.assertFalse(scope["fallback"])
        self.assertEqual(scope["features"], ["usage"])
        self.assertEqual(scope["journeys"], ["usage-details", "usage-window"])
        self.assertIn("usage.md", scope["reason"])

    def test_two_feature_files_select_both_features(self):
        scope = selector.select_scope(
            [
                ".claude/skills/verify-sf-companion/features/usage.md",
                ".claude/skills/verify-sf-companion/features/access.md",
            ],
            FEATURES,
            [],
        )
        self.assertEqual(scope["features"], ["usage", "access"])
        self.assertEqual(
            scope["journeys"], ["access-anonymous", "usage-details", "usage-window"]
        )

    def test_a_feature_file_plus_app_code_keeps_both(self):
        scope = selector.select_scope(
            [
                ".claude/skills/verify-sf-companion/features/factory.md",
                "apps/web/src/client/app/update.ts",
            ],
            FEATURES,
            [],
        )
        self.assertFalse(scope["harness"])
        self.assertEqual(scope["features"], ["factory", "usage"])
        self.assertEqual(
            scope["journeys"],
            [
                "factory-empty",
                "factory-entry",
                "factory-readings",
                "usage-details",
                "usage-window",
            ],
        )

    def test_a_feature_file_for_an_unknown_feature_is_a_helper(self):
        scope = selector.select_scope(
            [".claude/skills/verify-sf-companion/features/deleted.md"], FEATURES, []
        )
        self.assertTrue(scope["harness"])
        self.assertEqual(scope["journeys"], all_journeys())

    def test_a_feature_file_without_journeys_falls_back_to_the_smoke_journey(self):
        scope = selector.select_scope(
            [".claude/skills/verify-sf-companion/features/silent.md"],
            [
                {
                    "codePaths": [],
                    "id": "silent",
                    "journeys": [],
                }
            ],
            [],
        )
        self.assertEqual(scope["features"], ["silent"])
        self.assertEqual(scope["journeys"], ["factory-entry"])
        self.assertTrue(scope["fallback"])


class DigestTest(unittest.TestCase):
    def test_same_journeys_share_a_digest_across_different_diffs(self):
        first = selector.select_scope(["apps/web/src/website.ts"], FEATURES, [])
        second = selector.select_scope(
            ["apps/web/src/website.ts", ".claude/skills/verify-sf-companion/features/access.md"],
            FEATURES,
            [],
        )
        self.assertEqual(first["journeys"], second["journeys"])
        self.assertEqual(first["digest"], second["digest"])

    def test_a_different_journey_set_gets_a_different_digest(self):
        first = selector.select_scope(["apps/web/src/website.ts"], FEATURES, [])
        second = selector.select_scope(["apps/web/src/features/factory.ts"], FEATURES, [])
        self.assertNotEqual(first["digest"], second["digest"])

    def test_the_digest_is_short_hex(self):
        digest = selector.select_scope(["apps/web/src/website.ts"], FEATURES, [])[
            "digest"
        ]
        self.assertRegex(digest, r"^[0-9a-f]{16}$")


class FallbackTest(unittest.TestCase):
    def test_falls_back_to_the_entry_smoke_journey(self):
        scope = selector.select_scope(
            [".github/workflows/pstack-verifier.yml", "README.md"], FEATURES, []
        )
        self.assertEqual(scope["status"], "ok")
        self.assertEqual(scope["features"], [])
        self.assertEqual(scope["journeys"], ["factory-entry"])
        self.assertTrue(scope["fallback"])


class CommandLineTest(unittest.TestCase):
    def test_prints_a_scope_from_a_diff_list_and_pr_body_file(self):
        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as directory:
            features = Path(directory, "features")
            features.mkdir()
            Path(features, "factory.md").write_text(
                "- `factory-entry` loads.\n\nCode paths: apps/web/src/features/factory.ts\n"
            )
            Path(directory, "diff.txt").write_text("apps/web/src/features/factory.ts\n")
            Path(directory, "body.txt").write_text("Repro journey: factory-entry\n")
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/select_verifier_scope.py",
                    "--features-dir",
                    str(features),
                    "--diff-list",
                    str(Path(directory, "diff.txt")),
                    "--pr-body-file",
                    str(Path(directory, "body.txt")),
                ],
                capture_output=True,
                check=False,
                cwd=root,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        scope = json.loads(result.stdout)
        self.assertEqual(scope["status"], "ok")
        self.assertEqual(scope["features"], ["factory"])
        self.assertEqual(scope["journeys"], ["factory-entry"])
        self.assertRegex(scope["digest"], r"^[0-9a-f]{16}$")


if __name__ == "__main__":
    unittest.main()
