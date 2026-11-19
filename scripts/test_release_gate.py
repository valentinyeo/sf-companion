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
UNTRACED = {"access-anonymous": "A live HTTPS request, so no browser page."}
EBML_HEADER = (
    b"\x1aE\xdf\xa3"
    b"\x9f"
    b"\x42\x86\x81\x01"
    b"\x42\xf7\x81\x01"
    b"\x42\xf2\x81\x04"
    b"\x42\xf3\x81\x08"
    b"\x42\x82\x84webm"
    b"\x42\x87\x81\x04"
    b"\x42\x85\x81\x02"
)
WEBM = EBML_HEADER + b"0" * 2048
FRAME = json.dumps({"type": "screencast-frame", "sha1": "ab", "width": 1}) + "\n"
NOT_AN_EVENT = json.dumps({"type": "not-an-event"}) + "\n"

def fixture(name):
    return json.loads((FIXTURES / name).read_text())


ACTION = json.dumps({"type": "before", "apiName": "page.goto", "time": 1}) + "\n"


def trace_zip(events=ACTION):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("trace.trace", events)
        archive.writestr("trace.network", "")
    return buffer.getvalue()


def trace_members(traces):
    names = {
        name
        for names in (traces.get("journeys") or {}).values()
        for name in names
    }
    return {name: trace_zip() for name in names}


def case_log(journeys):
    actions = [{"action": "drive", "journey": journey} for journey in journeys]
    return json.dumps({"id": "case", "actions": actions})


def journeys_by_member(traces):
    recorded = {}
    for journey, names in ((traces or {}).get("journeys") or {}).items():
        for name in names:
            recorded.setdefault(name, []).append(journey)
    return recorded


def artifact(
    *,
    traces=None,
    members=(),
    invalid_trace=False,
    extra_manifest=False,
    records=None,
    member_data=None,
):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("proof-base/result.json", "{}")
        if traces is not None:
            archive.writestr("proof-head/traces.json", json.dumps(traces, indent=2))
        if extra_manifest:
            archive.writestr("proof-head/nested/proof-head/traces.json", "{}")
        for name in members:
            if member_data and name in member_data:
                data = member_data[name]
            elif invalid_trace and name.endswith(".trace.zip"):
                data = b"x"
            else:
                data = trace_zip() if name.endswith(".trace.zip") else b"PK00"
            archive.writestr(f"proof-head/{name}", data)
        for name, journeys in (
            journeys_by_member(traces) if records is None else records
        ).items():
            archive.writestr(
                f"proof-head/{gate.case_log_name(name)}", case_log(journeys)
            )
    return buffer.getvalue()


def proof_args(directory, journeys):
    return SimpleNamespace(
        proof_dir=directory,
        journeys=journeys,
        repo_path=str(REPO),
        features_dir=str(FEATURE_DIR.relative_to(REPO)),
    )


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.features = selector.read_features(FEATURE_DIR)

    def evaluate(
        self,
        *,
        traces,
        members=(),
        files=None,
        artifacts=None,
        runs=None,
        invalid_trace=False,
        extra_manifest=False,
        records=None,
        member_data=None,
    ):
        return gate.evaluate_pull_request(
            fixture("pull-request.json"),
            files if files is not None else fixture("files.json"),
            runs if runs is not None else fixture("runs.json"),
            artifacts if artifacts is not None else fixture("artifacts.json"),
            artifact(
                traces=traces,
                members=members,
                invalid_trace=invalid_trace,
                extra_manifest=extra_manifest,
                records=records,
                member_data=member_data,
            ),
            self.features,
            UNTRACED,
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
            UNTRACED,
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
        self.assertEqual(
            report["features"], ["empty", "factory", "kpis", "shipping", "usage"]
        )
        self.assertEqual(
            sorted(report["journeys"]),
            sorted(fixture("traces-pass.json")["journeys"]),
        )

    def test_untraced_journey_needs_no_trace(self):
        traces = fixture("traces-untraced.json")
        problems = gate.check_traces(
            ["access-anonymous"], traces, {}, UNTRACED, {}
        )
        self.assertEqual(problems, [])

    def test_video_counts_as_evidence(self):
        traces = {"journeys": {"factory-entry": ["case.webm"]}, "untraced": []}
        self.assertEqual(
            gate.check_traces(
                ["factory-entry"],
                traces,
                {"case.webm": WEBM},
                UNTRACED,
                {"case.webm": {"factory-entry"}},
            ),
            [],
        )

    def test_a_trace_with_only_a_screencast_frame_is_evidence(self):
        traces = {"journeys": {"factory-entry": ["case.trace.zip"]}, "untraced": []}
        self.assertEqual(
            gate.check_traces(
                ["factory-entry"],
                traces,
                {"case.trace.zip": trace_zip(FRAME)},
                UNTRACED,
                {"case.trace.zip": {"factory-entry"}},
            ),
            [],
        )

    def test_pass_fixture_covers_the_repository_feature_map(self):
        features = selector.read_features(FEATURE_DIR)
        journeys, touched = gate.required_journeys(
            features, ["apps/web/src/features/factory.ts"]
        )
        self.assertEqual(touched, ["empty", "factory", "kpis", "shipping", "usage"])
        self.assertEqual(
            sorted(journeys),
            sorted(fixture("traces-pass.json")["journeys"]),
        )


class FailTest(FixtureCase):
    def test_journey_without_a_trace_fails(self):
        traces = fixture("traces-missing-journey.json")
        report = self.evaluate(traces=traces, members=trace_members(traces))
        self.assertEqual(report["outcome"], "failed")
        self.assertIn(
            "no trace or video for journey factory-empty", report["problems"]
        )

    def test_trace_named_but_absent_from_the_artifact_fails(self):
        traces = fixture("traces-missing-member.json")
        report = self.evaluate(traces=traces, members=())
        self.assertEqual(report["outcome"], "failed")
        self.assertIn(
            "the proof artifact holds no seeded-1280-light.trace.zip "
            "for journey factory-entry",
            report["problems"],
        )

    def test_a_file_named_like_a_trace_is_not_a_trace(self):
        traces = {
            "journeys": {"factory-layout": ["fake.trace.zip"]},
            "untraced": [],
        }
        report = self.evaluate(
            traces=traces, members=["fake.trace.zip"], invalid_trace=True
        )
        self.assertEqual(report["outcome"], "failed")
        self.assertIn(
            "fake.trace.zip for journey factory-layout holds no recorded browser "
            "action, so it is not trace evidence",
            report["problems"],
        )

    def test_a_zip_with_a_zero_byte_trace_member_is_not_evidence(self):
        traces = {"journeys": {"factory-entry": ["empty.trace.zip"]}, "untraced": []}
        report = self.evaluate(
            traces=traces,
            members=["empty.trace.zip"],
            member_data={"empty.trace.zip": trace_zip("")},
        )
        self.assertEqual(report["outcome"], "failed")
        self.assertIn(
            "empty.trace.zip for journey factory-entry holds no recorded browser "
            "action, so it is not trace evidence",
            report["problems"],
        )

    def test_a_trace_of_json_that_holds_no_event_is_not_evidence(self):
        traces = {"journeys": {"factory-entry": ["case.trace.zip"]}, "untraced": []}
        report = self.evaluate(
            traces=traces,
            members=["case.trace.zip"],
            member_data={"case.trace.zip": trace_zip(NOT_AN_EVENT)},
        )
        self.assertEqual(report["outcome"], "failed")
        self.assertIn(
            "case.trace.zip for journey factory-entry holds no recorded browser "
            "action, so it is not trace evidence",
            report["problems"],
        )

    def test_a_trace_that_recorded_another_journey_fails(self):
        traces = fixture("traces-pass.json")
        members = trace_members(traces)
        records = journeys_by_member(traces)
        records["empty-1280-light.trace.zip"] = ["home-empty"]
        report = self.evaluate(traces=traces, members=members, records=records)
        self.assertEqual(report["outcome"], "failed")
        self.assertIn(
            "empty-1280-light.trace.zip for journey factory-empty recorded no "
            "action for that journey",
            report["problems"],
        )

    def test_a_trace_without_its_case_log_fails(self):
        traces = fixture("traces-pass.json")
        report = self.evaluate(
            traces=traces, members=trace_members(traces), records={}
        )
        self.assertEqual(report["outcome"], "failed")
        self.assertIn(
            "seeded-1280-light.trace.zip for journey factory-entry has no case log "
            "of its own, so it cannot be tied to that journey",
            report["problems"],
        )

    def test_a_video_without_a_readable_header_fails(self):
        traces = {"journeys": {"factory-entry": ["case.webm"]}, "untraced": []}
        report = self.evaluate(
            traces=traces,
            members=["case.webm"],
            member_data={"case.webm": b"\x1aE\xdf\xa3" + b"0" * 2048},
        )
        self.assertEqual(report["outcome"], "failed")
        self.assertIn(
            "case.webm for journey factory-entry is not a readable video",
            report["problems"],
        )

    def test_a_case_log_that_is_not_a_case_log_is_no_tie(self):
        traces = {"journeys": {"factory-entry": ["case.trace.zip"]}, "untraced": []}
        records = {"case.trace.zip": None}
        self.assertEqual(
            gate.check_traces(
                ["factory-entry"],
                traces,
                {"case.trace.zip": trace_zip()},
                UNTRACED,
                records,
            ),
            [
                "case.trace.zip for journey factory-entry has no case log of its "
                "own, so it cannot be tied to that journey"
            ],
        )

    def test_artifact_without_a_trace_index_fails(self):
        report = self.evaluate(traces=None)
        self.assertEqual(report["outcome"], "failed")
        self.assertIn(
            "uploaded no single proof-head/traces.json", report["problems"][0]
        )

    def test_two_trace_indexes_fail(self):
        traces = fixture("traces-pass.json")
        report = self.evaluate(
            traces=traces, members=trace_members(traces), extra_manifest=True
        )
        self.assertEqual(report["outcome"], "failed")
        self.assertIn(
            "uploaded no single proof-head/traces.json", report["problems"][0]
        )

    def test_pull_request_without_a_successful_run_fails(self):
        traces = fixture("traces-pass.json")
        report = self.evaluate(
            traces=traces,
            members=trace_members(traces),
            runs=fixture("runs-failed.json"),
        )
        self.assertEqual(report["outcome"], "failed")
        self.assertEqual(
            report["problems"],
            ["no successful pstack-verifier.yml run for head head12"],
        )

    def test_pull_request_without_a_proof_artifact_fails(self):
        report = self.evaluate(
            traces=None, artifacts=fixture("artifacts-empty.json")
        )
        self.assertEqual(report["outcome"], "failed")
        self.assertIn("uploaded no verifier-proofs artifact", report["problems"][0])

    def test_untraced_journey_outside_the_list_fails(self):
        traces = {
            "journeys": {},
            "untraced": [{"journey": "factory-timestamp", "reason": ""}],
        }
        self.assertEqual(
            gate.check_traces(["factory-timestamp"], traces, {}, UNTRACED, {}),
            ["no trace or video for journey factory-timestamp"],
        )

    def test_untraced_journey_without_a_reason_fails(self):
        traces = {
            "journeys": {},
            "untraced": [{"journey": "access-anonymous", "reason": ""}],
        }
        self.assertEqual(
            gate.check_traces(["access-anonymous"], traces, {}, UNTRACED, {}),
            ["no trace or video for journey access-anonymous"],
        )

    def test_proof_from_another_revision_fails(self):
        traces = fixture("traces-pass.json")
        traces["revision"] = "anothersha"
        report = self.evaluate(traces=traces, members=trace_members(traces))
        self.assertEqual(report["outcome"], "failed")
        self.assertEqual(
            report["problems"][0],
            "the proof records revision anothersha, not head head12",
        )

    def test_entry_that_is_not_a_trace_or_video_fails(self):
        traces = {
            "journeys": {"factory-entry": ["seeded-1280-light.png"]},
            "untraced": [],
        }
        self.assertEqual(
            gate.check_traces(
                ["factory-entry"],
                traces,
                {"seeded-1280-light.png": b"png"},
                UNTRACED,
                {},
            ),
            ["seeded-1280-light.png for journey factory-entry is not a trace or video"],
        )

    def test_base_traces_cannot_stand_in_for_head_traces(self):
        traces = {
            "journeys": {"factory-timestamp": ["seeded-1280-light.trace.zip"]},
            "untraced": [],
        }
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr(
                "proof-base/seeded-1280-light.trace.zip", trace_zip()
            )
        archive = archive.getvalue()
        self.assertEqual(gate.head_traces(archive, gate.trace_names(traces)), {})
        problems = gate.check_traces(
            ["factory-timestamp"],
            traces,
            gate.head_traces(archive, gate.trace_names(traces)),
            UNTRACED,
            {},
        )
        self.assertEqual(
            problems,
            [
                "the proof artifact holds no seeded-1280-light.trace.zip "
                "for journey factory-timestamp"
            ],
        )


class ArtifactTest(unittest.TestCase):
    def test_reads_the_trace_index_and_the_head_traces_it_names(self):
        traces = fixture("traces-pass.json")
        archive = artifact(traces=traces, members=["seeded-1280-light.trace.zip"])
        self.assertEqual(
            gate.read_traces(archive)["journeys"]["factory-entry"][0],
            "seeded-1280-light.trace.zip",
        )
        found = gate.head_traces(archive, gate.trace_names(traces))
        self.assertIn("seeded-1280-light.trace.zip", found)
        self.assertEqual(
            gate.read_traces(archive)["status"],
            "passed",
        )


class ProofDirectoryTest(unittest.TestCase):
    def test_proof_directory_without_a_trace_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "result.json").write_text("{}")
            self.assertEqual(gate.proof(proof_args(directory, "factory-entry")), 1)

    def test_proof_directory_with_a_trace_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            traces = fixture("traces-missing-member.json")
            Path(directory, "traces.json").write_text(json.dumps(traces))
            Path(directory, "seeded-1280-light.trace.zip").write_bytes(trace_zip())
            Path(directory, "seeded-1280-light.json").write_text(
                case_log(["factory-entry"])
            )
            self.assertEqual(gate.proof(proof_args(directory, "factory-entry")), 0)

    def test_proof_directory_with_a_trace_of_another_journey_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            traces = fixture("traces-missing-member.json")
            Path(directory, "traces.json").write_text(json.dumps(traces))
            Path(directory, "seeded-1280-light.trace.zip").write_bytes(trace_zip())
            Path(directory, "seeded-1280-light.json").write_text(
                case_log(["home-links"])
            )
            self.assertEqual(gate.proof(proof_args(directory, "factory-entry")), 1)
    

    def test_proof_directory_with_an_empty_recording_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            traces = {
                "journeys": {"factory-entry": ["empty.trace.zip"]},
                "untraced": [],
            }
            Path(directory, "traces.json").write_text(json.dumps(traces))
            Path(directory, "empty.trace.zip").write_bytes(trace_zip(events=""))
            Path(directory, "empty.json").write_text(case_log(["factory-entry"]))
            self.assertEqual(gate.proof(proof_args(directory, "factory-entry")), 1)

    def test_proof_directory_with_a_one_byte_trace_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            traces = {
                "journeys": {"factory-layout": ["fake.trace.zip"]},
                "untraced": [],
            }
            Path(directory, "traces.json").write_text(json.dumps(traces))
            Path(directory, "fake.trace.zip").write_bytes(b"x")
            Path(directory, "fake.json").write_text(case_log(["factory-layout"]))
            self.assertEqual(gate.proof(proof_args(directory, "factory-layout")), 1)


class UntracedListTest(unittest.TestCase):
    def test_untraced_list_comes_from_the_skill_not_the_artifact(self):
        untraced = gate.untraced_journeys(FEATURE_DIR)
        self.assertEqual(
            sorted(untraced),
            [
                "access-anonymous",
                "share-auth",
                "share-delete",
                "share-publish",
                "share-validate",
            ],
        )
        self.assertIn("no browser page", untraced["access-anonymous"])
        self.assertIn("no browser page", untraced["share-publish"])

    def test_missing_untraced_list_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(gate.GateError):
                gate.untraced_journeys(Path(directory, "features"))


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
