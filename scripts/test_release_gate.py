import inspect
import io
import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

import release_gate as gate
import select_verifier_scope as selector

REPO = Path(inspect.getfile(gate)).resolve().parent.parent
FIXTURES = REPO / "scripts" / "fixtures" / "release-gate"
WORKFLOW = REPO / ".github" / "workflows" / "pstack-verifier.yml"
FEATURE_DIR = REPO / ".claude" / "skills" / "verify-sf-companion" / "features"

WORKBENCH = """# Factory

## Sub-features

- `factory-entry` loads /factory.
- `factory-readings` shows seeded readings.
- `factory-empty` shows a missing feed.
- `factory-shipping` shows shipped PRs.
- `factory-layout` fits both viewports.

Code paths: apps/web/src/features/factory.ts
"""

USAGE = """# Usage

## Sub-features

- `usage-window` picks a window.
- `usage-burn` changes the burn reading.
- `usage-kpi-fixed` keeps the KPI fixed.
- `usage-details` opens both disclosures.

Code paths: apps/web/src/features/factory.ts, apps/web/src/client/app/update.ts
"""


LIVE_ONLY = {"access-anonymous": "A live HTTPS request, so no browser page."}


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


def trace_members(traces):
    return {
        name
        for names in (traces.get("journeys") or {}).values()
        for name in names
    }


def artifact(*, traces=None, members=()):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("proof-base/result.json", "{}")
        if traces is not None:
            archive.writestr(
                "proof-head/traces.json", json.dumps(traces, indent=2)
            )
        for name in members:
            archive.writestr(f"proof-head/{name}", "PK" + "0" * 64)
    return buffer.getvalue()


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.features = [
            {"id": "factory", **selector.parse_feature(WORKBENCH)},
            {"id": "usage", **selector.parse_feature(USAGE)},
        ]

    def evaluate(
        self, *, traces, members, files=None, artifacts=None, runs=None, live_only=None
    ):
        return gate.evaluate_pull_request(
            fixture("pull-request.json"),
            files if files is not None else fixture("files.json"),
            runs if runs is not None else fixture("runs.json"),
            artifacts if artifacts is not None else fixture("artifacts.json"),
            artifact(traces=traces, members=members),
            self.features,
            LIVE_ONLY if live_only is None else live_only,
        )


class AppCodeTest(unittest.TestCase):
    def test_app_code_is_apps_and_packages_without_content(self):
        paths = [
            "apps/web/src/features/factory.ts",
            "packages/core/src/contracts.ts",
            "apps/web/content/feed/factory.json",
            "apps/web/content/reports/2026-11-19.html",
            "README.md",
            "AGENTS.md",
        ]
        self.assertEqual(
            gate.app_code_paths(paths),
            ["apps/web/src/features/factory.ts", "packages/core/src/contracts.ts"],
        )

    def test_content_only_pull_request_passes(self):
        report = gate.evaluate_pull_request(
            fixture("pull-request.json"),
            fixture("content-files.json"),
            fixture("runs.json"),
            fixture("artifacts.json"),
            None,
            [],
            LIVE_ONLY,
        )
        self.assertEqual(report["outcome"], "no app code")
        self.assertEqual(report["problems"], [])

    def test_merged_in_range_keeps_only_merged_pull_requests_in_the_range(self):
        pull_requests = [
            {"number": 1, "merged_at": None, "merge_commit_sha": "merge1"},
            {"number": 2, "merged_at": "2026-11-19", "merge_commit_sha": "merge2"},
            {"number": 3, "merged_at": "2026-11-19", "merge_commit_sha": "merge3"},
            {
                "number": 4,
                "merged_at": "2026-11-19",
                "merge_commit_sha": "rebased",
                "head": {"sha": "head4"},
            },
        ]
        kept = gate.merged_in_range(pull_requests, {"merge2", "head4"})
        self.assertEqual([entry["number"] for entry in kept], [2, 4])


class PassTest(FixtureCase):
    def test_fixture_passes_with_a_trace_for_every_journey(self):
        traces = fixture("traces-pass.json")
        report = self.evaluate(traces=traces, members=trace_members(traces))
        self.assertEqual(report["problems"], [])
        self.assertEqual(report["outcome"], "passed")
        self.assertEqual(report["features"], ["factory", "usage"])
        self.assertEqual(
            sorted(report["journeys"]),
            ["factory-empty", "factory-entry", "factory-layout", "factory-readings",
             "factory-shipping", "usage-burn", "usage-details", "usage-kpi-fixed",
             "usage-window"],
        )

    def test_live_only_journey_needs_no_trace(self):
        traces = fixture("traces-live-only.json")
        problems = gate.check_traces(
            ["access-anonymous"], traces, {"proof-head/traces.json": 128}, LIVE_ONLY
        )
        self.assertEqual(problems, [])

    def test_untraced_journey_outside_the_live_only_list_fails(self):
        traces = {
            "journeys": {},
            "untraced": [{"journey": "factory-readings", "reason": ""}],
        }
        self.assertEqual(
            gate.check_traces(["factory-readings"], traces, {}, LIVE_ONLY),
            ["no trace or video for journey factory-readings"],
        )

    def test_untraced_live_only_journey_without_a_reason_fails(self):
        traces = {
            "journeys": {},
            "untraced": [{"journey": "access-anonymous", "reason": ""}],
        }
        self.assertEqual(
            gate.check_traces(["access-anonymous"], traces, {}, LIVE_ONLY),
            ["no trace or video for journey access-anonymous"],
        )

    def test_pass_fixture_covers_the_repository_feature_map(self):
        features = selector.read_features(FEATURE_DIR)
        journeys, touched = gate.required_journeys(
            features, ["apps/web/src/features/factory.ts"]
        )
        self.assertEqual(touched, ["factory", "usage"])
        self.assertEqual(
            sorted(journeys),
            sorted(fixture("traces-pass.json")["journeys"]),
        )


class FailTest(FixtureCase):
    def test_journey_without_a_trace_fails(self):
        traces = fixture("traces-missing-journey.json")
        report = self.evaluate(
            traces=traces, members=traces["journeys"]["factory-entry"]
        )
        self.assertEqual(report["outcome"], "failed")
        self.assertIn("no trace or video for journey factory-empty", report["problems"])

    def test_trace_named_but_absent_from_the_artifact_fails(self):
        traces = fixture("traces-missing-member.json")
        report = self.evaluate(traces=traces, members=[])
        self.assertEqual(report["outcome"], "failed")
        self.assertIn(
            "the proof artifact holds no seeded-1280-light.trace.zip for journey factory-entry",
            report["problems"],
        )

    def test_artifact_without_a_trace_index_fails(self):
        report = self.evaluate(traces=None, members=())
        self.assertEqual(report["outcome"], "failed")
        self.assertIn("uploaded no proof-head/traces.json", report["problems"][0])

    def test_pull_request_without_a_successful_run_fails(self):
        traces = fixture("traces-pass.json")
        report = self.evaluate(
            traces=traces,
            members=trace_members(traces),
            runs=fixture("runs-failed.json"),
        )
        self.assertEqual(report["outcome"], "failed")
        self.assertEqual(
            report["problems"], ["no successful pstack-verifier.yml run for head head12"]
        )

    def test_pull_request_without_a_proof_artifact_fails(self):
        report = self.evaluate(
            traces=None, members=(), artifacts=fixture("artifacts-empty.json")
        )
        self.assertEqual(report["outcome"], "failed")
        self.assertIn("uploaded no verifier-proofs artifact", report["problems"][0])

    def test_proof_from_another_revision_fails(self):
        traces = fixture("traces-pass.json")
        traces["revision"] = "anothersha"
        report = self.evaluate(traces=traces, members=trace_members(traces))
        self.assertEqual(report["outcome"], "failed")
        self.assertEqual(
            report["problems"][0],
            "the proof records revision anothersha, not head head12",
        )

    def test_base_traces_cannot_stand_in_for_head_traces(self):
        traces = {
            "journeys": {"factory-readings": ["seeded-1280-light.trace.zip"]},
            "untraced": [],
        }
        problems = gate.check_traces(
            ["factory-readings"],
            traces,
            {"proof-base/seeded-1280-light.trace.zip": 900},
            LIVE_ONLY,
        )
        self.assertEqual(
            problems,
            [
                "the proof artifact holds no seeded-1280-light.trace.zip "
                "for journey factory-readings"
            ],
        )

    def test_entry_that_is_not_a_trace_or_video_fails(self):
        traces = {
            "journeys": {"factory-entry": ["seeded-1280-light.png"]},
            "untraced": [],
        }
        problems = gate.check_traces(
            ["factory-entry"],
            traces,
            {"proof-head/seeded-1280-light.png": 900},
            LIVE_ONLY,
        )
        self.assertEqual(
            problems,
            ["seeded-1280-light.png for journey factory-entry is not a trace or video"],
        )


class ArtifactTest(unittest.TestCase):
    def test_reads_the_trace_index_and_member_sizes_from_a_proof_artifact(self):
        traces = fixture("traces-pass.json")
        archive = artifact(
            traces=traces, members=["seeded-1280-light.trace.zip"]
        )
        self.assertEqual(
            gate.read_traces(archive)["journeys"]["factory-entry"][0],
            "seeded-1280-light.trace.zip",
        )
        sizes = gate.member_sizes(archive)
        self.assertGreater(sizes["proof-head/seeded-1280-light.trace.zip"], 0)
        self.assertGreater(sizes["proof-base/result.json"], 0)


def PROOF_ARGS(directory):
    return SimpleNamespace(
        proof_dir=directory,
        journeys="factory-entry",
        repo_path=str(REPO),
        features_dir=str(Path(FEATURE_DIR).relative_to(REPO)),
    )


class ProofDirectoryTest(unittest.TestCase):
    def test_proof_directory_without_a_trace_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "result.json").write_text("{}")
            self.assertEqual(gate.proof(PROOF_ARGS(directory)), 1)

    def test_proof_directory_with_a_trace_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            traces = fixture("traces-missing-member.json")
            Path(directory, "traces.json").write_text(json.dumps(traces))
            Path(directory, "seeded-1280-light.trace.zip").write_bytes(b"PK00")
            self.assertEqual(gate.proof(PROOF_ARGS(directory)), 0)


class LiveOnlyTest(unittest.TestCase):
    def test_live_only_list_comes_from_the_skill_not_the_artifact(self):
        self.assertEqual(
            gate.live_only_journeys(FEATURE_DIR),
            {
                "access-anonymous": "A live HTTPS request to yeoux.net with no cookies, "
                "so there is no browser page to record."
            },
        )

    def test_missing_live_only_list_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(gate.GateError):
                gate.live_only_journeys(Path(directory, "features"))


class StateTest(unittest.TestCase):
    def test_missing_state_file_reads_as_none(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(gate.read_state(Path(directory, "deployed-sha")))

    def test_empty_state_file_reads_as_none(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "deployed-sha")
            path.write_text("\n")
            self.assertIsNone(gate.read_state(path))

    def test_state_file_reads_its_sha(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "deployed-sha")
            path.write_text("969807fe9008f2999475cb61d52490bc22ef3748\n")
            self.assertEqual(
                gate.read_state(path), "969807fe9008f2999475cb61d52490bc22ef3748"
            )


class WorkflowTest(unittest.TestCase):
    def test_the_verifier_runs_the_gate_and_uploads_the_proof(self):
        source = WORKFLOW.read_text()
        self.assertRegex(
            source,
            re.compile(
                r"release_gate\.py --proof-dir \"\$GITHUB_WORKSPACE/proof-head\""
            ),
        )
        self.assertIn("--journeys=$JOURNEYS", source)
        self.assertRegex(
            source,
            re.compile(r"name: verifier-proofs\n(?:\s+.*\n)*?\s+proof-head"),
        )
