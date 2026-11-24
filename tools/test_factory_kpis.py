import contextlib
import copy
import importlib.util
import io
import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import factory_kpis as kpi


NOW = 1794830400


def iso(at):
    return kpi.datetime.fromtimestamp(at, kpi.timezone.utc).isoformat()


def seed():
    return {
        "tickets": [
            {"id": 1, "boardId": 15, "sectionIsDone": True, "sectionChangedAt": iso(NOW - 60),
             "updatedAt": iso(NOW), "assignees": [{"displayName": "Product Lead"}]},
            {"id": 2, "boardId": 2060, "sectionIsDone": True, "sectionChangedAt": iso(NOW - 2 * kpi.DAY),
             "updatedAt": iso(NOW), "assignees": []},
            {"id": 3, "boardId": 11514, "sectionIsDone": False, "sectionChangedAt": iso(NOW), "assignees": []},
        ],
        "prs": [
            {"createdAt": iso(NOW - 3 * kpi.DAY), "updatedAt": iso(NOW), "mergedAt": iso(NOW - 10),
             "number": 1, "comments": [{"createdAt": iso(NOW - 60), "body": "**PASS+NOTES**\nChecked like a user."}]},
            {"createdAt": iso(NOW - 4 * kpi.DAY), "updatedAt": iso(NOW), "mergedAt": iso(NOW - 10),
             "number": 2, "comments": [{"createdAt": iso(NOW - 120), "body": "FAIL"},
                                       {"createdAt": iso(NOW - 60), "body": "PASS"}]},
            {"createdAt": iso(NOW - 3 * kpi.DAY), "updatedAt": iso(NOW), "mergedAt": iso(NOW - 10),
             "number": 3, "comments": []},
        ],
        "chats": [{"name": "Product Lead", "matched": True}, {"name": "Unnamed", "matched": False}],
        "runs": [{"id": 10, "status": "completed", "conclusion": "success", "created_at": iso(NOW - 600), "updated_at": iso(NOW - 500)},
                 {"id": 11, "check_suite_node_id": "suite-11", "status": "completed", "conclusion": "failure", "created_at": iso(NOW - 600), "updated_at": iso(NOW - 500)}],
        "annotations": [{"message": "The job was not started because recent account payments have failed", "title": "Error"}],
        "deployments": [{"id": 20, "sha": "merge-1", "environment": "Production", "created_at": iso(NOW - 9)}],
        "statuses": [{"state": "success", "created_at": iso(NOW - 1)}],
        "pools": {"claude": {"used_pct": 50, "pace_ratio": 2, "resets_at": NOW + kpi.DAY},
                  "codex": {"used_pct": 0, "pace_ratio": 0, "resets_at": NOW + kpi.DAY},
                  "grok": {"used_pct": 10, "pace_ratio": None}},
        "roster": {"rows": [{"name": "Product Lead", "kind": "lead"},
                              {"name": "Factory Lead", "kind": "chief"},
                              {"name": "Runner", "kind": "runner-pool"}]},
        "log": f"{iso(NOW - 60)} solo-wake: Product Lead loop: ok, loop fired 2 min ago\n"
               f"{iso(NOW - 60)} solo-wake: Factory Lead loop: would arm, no scheduled turn in 45 min\n",
    }


def runner(fixture):
    def run(args):
        if args[0] == "hypertask":
            board = int(args[args.index("--project") + 1])
            tasks = [t for t in fixture["tickets"] if t["boardId"] == board]
            return {"success": True, "tasks": tasks, "total": len(tasks)}
        if args[0] == "token-ladder":
            return fixture["pools"]
        if args[0] == "python3":
            return fixture["chats"]
        endpoint = args[-1]
        if "nodes(ids:" in endpoint and "WorkflowRun" in endpoint:
            ids = json.loads(endpoint.split("nodes(ids: ")[1].split(") {")[0])
            runs = {r["node_id"]: r for r in fixture["runs"] if r.get("node_id")}
            return {"data": {"nodes": [{"id": i, "databaseId": runs[i]["id"],
                                        "createdAt": runs[i]["created_at"],
                                        "updatedAt": runs[i]["updated_at"],
                                        "checkSuite": {"id": runs[i].get("check_suite_node_id"),
                                                       "status": (runs[i].get("status") or "").upper(),
                                                       "conclusion": (runs[i].get("conclusion") or "").upper() or None}}
                                       for i in ids]}}
        if "nodes(ids:" in endpoint:
            return {"data": {"nodes": [{"id": "suite-11", "checkRuns": {
                "pageInfo": {"hasNextPage": fixture.get("annotation_overflow", False)},
                "nodes": [{"conclusion": "FAILURE", "annotations": {"pageInfo": {"hasNextPage": False},
                           "nodes": [dict(a, annotationLevel=a.get("annotationLevel", "FAILURE")) for a in fixture["annotations"]]
                           if fixture["annotations"] is not None else None}}],
            }}]}}
        if "/actions/runs/" in endpoint and endpoint.rsplit("/", 1)[-1].isdigit():
            wanted = int(endpoint.rsplit("/", 1)[-1])
            return next(r for r in fixture["runs"] if r["id"] == wanted)
        if "/actions/runs?" in endpoint:
            return {"total_count": len(fixture["runs"]), "workflow_runs": fixture["runs"]}
        if "/jobs?" in endpoint:
            return {"jobs": [{"conclusion": "failure", "check_run_url": "https://api.github.com/repos/fixture/repo/check-runs/30"}]}
        if "/annotations?" in endpoint:
            return [dict(a, annotation_level=a.get("annotation_level", "failure")) for a in fixture["annotations"]]
        if "/statuses?" in endpoint:
            return fixture["statuses"]
        if "/deployments?" in endpoint:
            return fixture["deployments"]
        return {"data": {"repository": {"pullRequests": {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "nodes": [dict(p, mergeCommit={"oid": f"merge-{p['number']}"}, comments={"pageInfo": {"hasNextPage": False}, "nodes": p["comments"]})
                      for p in fixture["prs"]],
        }}}}

    return run


def exported_in(fixture, directory, calls=None):
    root = Path(directory)
    (root / "roster.json").write_text(json.dumps(fixture["roster"]))
    (root / "loop.log").write_text(fixture["log"])
    inner = runner(fixture)

    def run(args):
        if calls is not None:
            calls.append(list(args))
        return inner(args)

    with patch.dict(os.environ, {"FACTORY_REPOS": "fixture/repo", "FACTORY_ROSTER": str(root / "roster.json"),
                                 "FACTORY_LOOP_LOG": str(root / "loop.log"),
                                 "FACTORY_CACHE": str(root / "cache")}):
        return kpi.collect(NOW, run)


def exported(fixture):
    with tempfile.TemporaryDirectory() as directory:
        return exported_in(fixture, directory)


def exporter_module():
    with patch.dict(os.environ, {"ADVISOR_BIN": "/fixture", "TOKEN_LADDER_STATUS": "/fixture/status.json"}):
        spec = importlib.util.spec_from_file_location("exporter", Path(__file__).with_name("export-factory-feed.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class FactoryKpiTests(unittest.TestCase):
    def test_daily_shipping_reuses_collector_beyond_seven_days(self):
        fixture = seed()
        fixture["prs"].append({"number": 99, "createdAt": iso(NOW - 20 * kpi.DAY),
                               "updatedAt": iso(NOW - 15 * kpi.DAY), "mergedAt": iso(NOW - 15 * kpi.DAY),
                               "comments": []})
        result = exported(fixture)
        date = kpi.datetime.fromtimestamp(NOW - 15 * kpi.DAY, kpi.timezone.utc).date().isoformat()
        day = next(d for d in result["shipping"]["days"] if d["date"] == date)
        self.assertEqual(day["merges"]["value"], 1)
        self.assertEqual(next(t for t in result["tiles"] if t["id"] == "merges")["display"],
                         "3 merged in 24h · 0.4 per day over 7d · 4319.8 min median")

    def test_seeded_sources_change_only_their_tile(self):
        baseline = exported(seed())
        self.assertEqual(len(baseline["notes"]), 5)
        self.assertEqual([t["display"] for t in baseline["tiles"]],
                         ["1 / day · 2 / week", "50%", "1/2 over pace", "50%",
                          "3 merged in 24h · 0.4 per day over 7d · 4319.8 min median", "50%",
                          "50% runs failed · infra 1 · code/policy 0 · unclassified 0 · 0.1 min median to live (1/3 receipted)"])
        for index in range(7):
            fixture = seed()
            if index == 0:
                fixture["tickets"][1]["sectionChangedAt"] = iso(NOW - 60)
            elif index == 1:
                fixture["prs"][1]["comments"][0]["body"] = "PASS"
            elif index == 2:
                fixture["pools"]["claude"]["pace_ratio"] = 0.5
            elif index == 3:
                fixture["log"] += f"{iso(NOW)} solo-wake: Factory Lead loop: ok, loop fired 1 min ago\n"
            elif index == 4:
                fixture["prs"][0]["createdAt"] = iso(NOW - 5 * kpi.DAY)
            elif index == 5:
                fixture["chats"][1]["matched"] = True
            else:
                fixture["annotations"][0]["message"] = "error TS2322: Type mismatch"
            actual = exported(fixture)
            self.assertNotEqual(actual["tiles"][index]["display"], baseline["tiles"][index]["display"])
            self.assertEqual(actual["notes"], baseline["notes"])
            for other in range(7):
                if other != index:
                    self.assertEqual(actual["tiles"][other], baseline["tiles"][other])

    def test_delivery_uses_move_date_not_recent_edit(self):
        fixture = seed()
        fixture["tickets"][0]["sectionChangedAt"] = iso(NOW - 10 * kpi.DAY)
        result = exported(fixture)["tiles"][0]
        self.assertEqual(result["display"], "0 / day · 1 / week")
        self.assertIn("Board 2060 / Unassigned, 7d: 1", result["details"])
        self.assertIn("Board 11514, 1d: 0", result["details"])

    def test_missing_sources_are_dropped_not_zeroed(self):
        fixture = seed()
        del fixture["tickets"][0]["sectionChangedAt"]
        fixture["log"] = f"{iso(NOW)} solo-wake: Product Lead: woke chat\n"
        result = exported(fixture)
        self.assertEqual([t["id"] for t in result["tiles"]], ["verifier", "pace", "merges", "identity", "ci"])
        self.assertIn("Done-move dates unavailable", result["notes"][0])
        self.assertIn("ordinary wakes are not loop fires", result["notes"][1])
        self.assertNotIn(str(Path.home()), json.dumps(result))

    def test_zero_is_measured_and_missing_denominator_is_explained(self):
        result = kpi.verifier([], NOW)
        self.assertEqual(result["display"], "–")
        self.assertIn("No PRs", result["details"][0])
        fixture = seed()
        fixture["tickets"] = []
        self.assertEqual(exported(fixture)["tiles"][0]["display"], "0 / day · 0 / week")

    def test_first_verdict_and_merge_coverage_have_separate_windows(self):
        fixture = seed()
        fixture["prs"][0]["comments"][0]["createdAt"] = iso(NOW - 8 * kpi.DAY)
        fixture["prs"][2]["comments"] = [{"createdAt": iso(NOW), "body": "PASS"}]
        result = kpi.verifier(fixture["prs"], NOW)
        self.assertEqual(result["display"], "50%")
        self.assertIn("(1/3)", result["details"][1])
        fixture["prs"][0]["comments"][0]["body"] = "FAIL"
        self.assertEqual(kpi.verifier(fixture["prs"], NOW)["display"], "50%")

    def test_verdict_requires_a_verdict_line(self):
        for body in ("The instructions say PASS / PASS+NOTES / FAIL", "> PASS", "```\nPASS\n```", "PASSING"):
            self.assertIsNone(kpi.verdict(body))
        for body in ("PASS", "## PASS+NOTES", "**Verdict: PASS**", "Verifier: FAIL"):
            self.assertIsNotNone(kpi.verdict(body))

    def test_loop_observation_age_is_not_loop_fire_age(self):
        fixture = seed()
        fixture["log"] = f"{iso(NOW - 40 * 60)} solo-wake: Product Lead loop: ok, loop fired 10 min ago\n"
        result = next(t for t in exported(fixture)["tiles"] if t["id"] == "loops")
        self.assertEqual(result["display"], "0%")
        fixture["log"] = f"{iso(NOW + 60)} solo-wake: Product Lead loop: ok, loop fired 1 min ago\n"
        self.assertNotIn("loops", [t["id"] for t in exported(fixture)["tiles"]])

    def test_failed_cli_never_becomes_empty_success(self):
        with self.assertRaises(ValueError):
            kpi.read_tickets(NOW, lambda args: {"success": False})
        with self.assertRaises(ValueError):
            kpi.read_prs(NOW, lambda args: {"errors": [{"message": "failed"}]})

    def test_pr_and_comment_pagination_preserve_the_first_verdict(self):
        pr = seed()["prs"][0]
        calls = []

        def run(args):
            calls.append(args)
            if "/comments?" in args[-1]:
                if "page=2" in args[-1]:
                    return [{"body": "PASS", "created_at": iso(NOW - 60)}]
                return [{"body": "FAIL", "created_at": iso(NOW - 120)}] * 100
            paged = "after=cursor" in args
            node = dict(pr, comments={"pageInfo": {"hasNextPage": True}, "nodes": []})
            if paged:
                node = dict(node, updatedAt=iso(NOW - 8 * kpi.DAY))
            return {"data": {"repository": {"pullRequests": {
                "pageInfo": {"hasNextPage": True, "endCursor": "cursor"}, "nodes": [node],
            }}}}

        with patch.dict(os.environ, {"FACTORY_REPOS": "fixture/repo"}):
            prs = kpi.read_prs(NOW, run)
        self.assertEqual(len(prs), 1)
        self.assertEqual(kpi.verifier(prs, NOW)["display"], "0%")
        self.assertEqual(len(calls), 4)

    def test_ticket_pagination_counts_each_ticket_once(self):
        task = seed()["tickets"][0]

        def run(args):
            offset = int(args[args.index("--offset") + 1])
            return {"success": True, "tasks": [task] if offset < 2 else [], "total": 2}

        rows = kpi.read_tickets(NOW, run)
        self.assertEqual(len(rows), 1)

    def test_latest_loop_observation_overrides_earlier_health(self):
        fixture = seed()
        fixture["log"] += f"{iso(NOW)} solo-wake: Product Lead loop: escalate, no loop after 2 arm messages\n"
        self.assertEqual(next(t for t in exported(fixture)["tiles"] if t["id"] == "loops")["display"], "0%")

    def test_merge_window_and_median_use_merges_not_updates(self):
        prs = seed()["prs"]
        prs[0]["mergedAt"] = iso(NOW - 8 * kpi.DAY)
        prs[1]["mergedAt"] = iso(NOW + 1)
        prs[2]["createdAt"] = iso(NOW - 1210)
        self.assertIn("1 merged in 24h · 0.1 per day over 7d · 20.0 min median", kpi.merges(prs, NOW)["display"])
        self.assertIn("0 merged in 24h · 0.0 per day over 7d · – median", kpi.merges([], NOW)["display"])
        prs[2]["createdAt"] = None
        with self.assertRaises(kpi.SourceUnavailable):
            kpi.merges(prs, NOW)

    def test_identity_has_a_live_denominator_and_explains_gaps(self):
        fixture = seed()
        fixture["chats"] = []
        result = exported(fixture)
        self.assertNotIn("identity", [t["id"] for t in result["tiles"]])
        self.assertTrue(any("no live Multibot chat inventory" in n for n in result["notes"]))
        tile = kpi.identity_sync([{"name": None, "matched": False}], NOW)
        self.assertEqual(tile["display"], "0%")
        self.assertIn("Gaps: Unnamed chat", tile["details"])
        self.assertNotIn("credentials", json.dumps(tile))

    def test_ci_unknown_failures_never_become_code_or_infra(self):
        fixture = seed()
        fixture["annotations"] = [{"message": "Process completed with exit code 1", "title": "Error"}]
        tile = next(t for t in exported(fixture)["tiles"] if t["id"] == "ci")
        self.assertIn("infra 0 · code/policy 0 · unclassified 1", tile["display"])
        fixture["runs"] = []
        fixture["deployments"] = []
        tile = next(t for t in exported(fixture)["tiles"] if t["id"] == "ci")
        self.assertEqual(tile["display"], "– runs failed · – to live (0/3 receipted)")
        self.assertIn("No completed Actions runs", " ".join(tile["details"]))

    def test_ci_latency_requires_successful_production_merge_sha(self):
        for field, value in (("sha", "unrelated"), ("environment", "Preview")):
            fixture = seed()
            fixture["deployments"][0][field] = value
            tile = next(t for t in exported(fixture)["tiles"] if t["id"] == "ci")
            self.assertIn("– to live (0/3 receipted)", tile["display"])
        for status in ({"state": "pending", "created_at": iso(NOW - 1)},
                       {"state": "success", "created_at": iso(NOW + 1)},
                       {"state": "success", "created_at": iso(NOW - 100)}):
            fixture = seed()
            fixture["statuses"] = [status]
            tile = next(t for t in exported(fixture)["tiles"] if t["id"] == "ci")
            self.assertIn("– to live (0/3 receipted)", tile["display"])
        fixture = seed()
        fixture["prs"][0]["mergedAt"] = iso(NOW - 1800)
        fixture["statuses"] += [{"state": "success", "created_at": iso(NOW - 600)}]
        fixture["deployments"] *= 2
        tile = next(t for t in exported(fixture)["tiles"] if t["id"] == "ci")
        self.assertIn("20.0 min median to live (1/3 receipted)", tile["display"])
        self.assertEqual(tile["state"], "bad")
        self.assertIn("1/3 merged PRs", tile["details"][0])

    def test_ci_excludes_future_old_and_incomplete_runs(self):
        fixture = seed()
        for changes in ({"created_at": iso(NOW - 8 * kpi.DAY)}, {"updated_at": iso(NOW + 1)},
                        {"status": "in_progress"}, {"created_at": iso(NOW + 1)}):
            fixture["runs"].append(dict(fixture["runs"][1], id=len(fixture["runs"]) + 20, **changes))
        tile = next(t for t in exported(fixture)["tiles"] if t["id"] == "ci")
        self.assertIn("2 completed Actions runs", " ".join(tile["details"]))

    def test_actions_search_splits_at_the_api_limit_without_gaps(self):
        calls = []

        def run(args):
            window = args[-1].split("created=")[1]
            start, end = map(kpi.timestamp, window.split(".."))
            calls.append((start, end))
            if start != end:
                return {"total_count": 1001, "workflow_runs": []}
            return {"total_count": 1, "workflow_runs": [{"id": int(start)}]}

        rows = kpi.read_actions("fixture/repo", NOW - 1, NOW, run)
        self.assertEqual([r["id"] for r in rows], [NOW - 1, NOW])
        self.assertEqual(calls, [(NOW - 1, NOW), (NOW - 1, NOW - 1), (NOW, NOW)])
        with self.assertRaises(kpi.SourceUnavailable):
            kpi.read_actions("fixture/repo", NOW, NOW, lambda args: {"total_count": 1001})

    def test_failure_annotations_batch_and_preserve_unknown(self):
        calls = []
        rows = [{"id": i, "check_suite_node_id": f"suite-{i}", "conclusion": "failure"} for i in range(25)]

        def run(args):
            ids = json.loads(args[-1].split("nodes(ids: ")[1].split(") {")[0])
            calls.append(ids)
            return {"data": {"nodes": [{"id": sid, "checkRuns": {"pageInfo": {"hasNextPage": False}, "nodes": []}} for sid in ids]}}

        kinds = kpi.read_failure_kinds("fixture/repo", rows, run)
        self.assertEqual([len(c) for c in calls], [20, 5])
        self.assertEqual(kinds, {i: "unknown" for i in range(25)})
        with self.assertRaises(kpi.SourceUnavailable):
            kpi.read_failure_kinds("fixture/repo", rows, lambda args: {"errors": [{"message": "failed"}]})

    def test_annotation_overflow_is_paged_and_warnings_are_not_failures(self):
        fixture = seed()
        fixture["annotation_overflow"] = True
        self.assertIn("infra 1 · code/policy 0 · unclassified 0", next(t for t in exported(fixture)["tiles"] if t["id"] == "ci")["display"])
        fixture["annotation_overflow"] = False
        fixture["annotations"][0]["annotationLevel"] = "WARNING"
        self.assertIn("infra 0 · code/policy 0 · unclassified 1", next(t for t in exported(fixture)["tiles"] if t["id"] == "ci")["display"])

    def test_identity_reader_uses_file_existence_without_reading_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fleet = root / "fleet"
            fleet.mkdir()
            (fleet / "roster.py").write_text("def hosted_chats():\n    return {'a': {'name': 'HT Product Lead'}, 'b': {'name': 'Other'}, 'c': {'name': None}}\n")
            sessions = root / ".config/hypertask-agents/credentials/sessions"
            sessions.mkdir(parents=True)
            (sessions / "ht-product-lead-agent-token").write_text("private token contents")

            def run(args):
                return json.loads(kpi.subprocess.run([*args[:-1], str(fleet)], capture_output=True, text=True,
                                  check=True, env={**os.environ, "HOME": str(root)}).stdout)

            rows = kpi.read_identities(run)
            self.assertEqual([r["matched"] for r in rows], [True, False, False])
            self.assertNotIn("private token contents", json.dumps(rows))
            self.assertNotIn(str(root), json.dumps(rows))

    def test_actions_pagination_cannot_silently_truncate(self):
        with self.assertRaises(kpi.SourceUnavailable):
            kpi.read_actions("fixture/repo", NOW - kpi.DAY, NOW,
                             lambda args: {"total_count": 101, "workflow_runs": [{"id": 1}]})

    def test_new_source_failure_does_not_hide_other_tiles(self):
        fixture = seed()
        fixture["annotations"] = None
        result = exported(fixture)
        self.assertEqual([t["id"] for t in result["tiles"]], ["delivered", "verifier", "pace", "loops", "merges", "identity"])
        self.assertTrue(any("CI health unavailable" in n for n in result["notes"]))

    def test_exporter_contract_accepts_seeded_kpis_and_rejects_missing_provenance(self):
        exporter = exporter_module()
        feed = {"generatedAt": "2026-11-16T12:00:00Z", "usage": {"cards": [], "burn": {}}, "kpis": exported(seed())}
        self.assertEqual(exporter.validate(feed), [])
        broken = copy.deepcopy(feed)
        broken["kpis"]["tiles"][0]["source"] = ""
        self.assertTrue(exporter.validate(broken))

    def test_repeat_export_rereads_no_finished_run_and_no_classified_failure(self):
        fixture = seed()
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            first = exported_in(fixture, directory, calls)
            first_gh = len([a for a in calls if a[0] == "gh"])
            calls.clear()
            second = exported_in(fixture, directory, calls)
            second_gh = [a for a in calls if a[0] == "gh"]
            self.assertEqual(second["tiles"], first["tiles"])
            self.assertEqual(second["shipping"], first["shipping"])
            self.assertLessEqual(len(second_gh), 6)
            self.assertLess(len(second_gh), first_gh)
            self.assertEqual([a for a in second_gh if any("nodes(ids:" in w for w in a)], [])
            self.assertEqual([a for a in second_gh if any("/jobs?" in w for w in a)], [])
            self.assertEqual([a for a in second_gh if any("/annotations?" in w for w in a)], [])

    def test_saved_prs_never_widen_the_requested_window(self):
        fixture = seed()
        fixture["prs"].append({"number": 42, "createdAt": iso(NOW - 20 * kpi.DAY),
                               "updatedAt": iso(NOW - 20 * kpi.DAY), "mergedAt": None, "comments": []})
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory)
            (store / "fixture__repo.json").write_text(json.dumps({"prs": {
                "42": dict(fixture["prs"][-1], repo="fixture/repo"),
                "1": dict(fixture["prs"][0], repo="fixture/repo", mergeCommit={"oid": "merge-1"})},
                "prs_through": NOW - 60}))
            quiet = runner(fixture)
            with patch.dict(os.environ, {"FACTORY_REPOS": "fixture/repo"}):
                self.assertEqual([p["number"] for p in kpi.read_prs(NOW, quiet, days=7, cache=kpi.Cache(store))], [1, 2, 3])
                self.assertEqual(sorted(p["number"] for p in kpi.read_prs(NOW, quiet, days=30, cache=kpi.Cache(store))),
                                 [1, 2, 3, 42])
                saved = json.loads((store / "fixture__repo.json").read_text())
            self.assertEqual(sorted(saved["prs"]), ["1", "2", "3", "42"])

    def test_in_flight_runs_are_refreshed_in_one_batch_and_leave_the_store(self):
        fixture = seed()
        for offset in (1, 2):
            fixture["runs"].append({"id": 12 + offset, "node_id": f"node-{12 + offset}", "status": "in_progress",
                                    "conclusion": None, "created_at": iso(NOW - 600), "updated_at": iso(NOW - 300)})
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            first = exported_in(fixture, directory, calls)
            batch = [a for a in calls if a[0] == "gh" and any("WorkflowRun" in w for w in a)]
            self.assertEqual(len(batch), 1)
            self.assertEqual([a for a in calls if a[0] == "gh" and a[-1].rsplit("/", 1)[-1].isdigit()], [])
            self.assertIn("2 completed Actions runs", " ".join(next(t for t in first["tiles"] if t["id"] == "ci")["details"]))
            for run in fixture["runs"][-2:]:
                run.update(status="completed", conclusion="success", updated_at=iso(NOW - 60))
            calls.clear()
            second = exported_in(fixture, directory, calls)
            self.assertEqual([a for a in calls if a[0] == "gh" and any("WorkflowRun" in w for w in a)], [])
            self.assertIn("4 completed Actions runs", " ".join(next(t for t in second["tiles"] if t["id"] == "ci")["details"]))
            saved = json.loads((Path(directory) / "cache" / "fixture__repo.json").read_text())
            self.assertEqual({r["status"] for r in saved["runs"].values()}, {"completed"})

    def test_completed_run_keeps_the_failure_kind_from_its_first_read(self):
        fixture = seed()
        with tempfile.TemporaryDirectory() as directory:
            exported_in(fixture, directory)
            cache_file = next((Path(directory) / "cache").glob("*.json"))
            saved = json.loads(cache_file.read_text())
            self.assertEqual([(r["id"], r["failure_kind"], r["classified"]) for r in saved["runs"].values()],
                             [(10, None, True), (11, "infra", True)])
            before = cache_file.read_text()
            exported_in(fixture, directory)
            self.assertEqual(cache_file.read_text(), before)

    def test_budget_refusal_stops_the_export_and_keeps_the_previous_feed(self):
        refused = types.SimpleNamespace(returncode=75, stdout="", stderr="refused")
        with patch.object(kpi.subprocess, "run", return_value=refused):
            with self.assertRaises(kpi.BudgetRefused):
                kpi.command_json(["gh", "api", "rate_limit"])
        with tempfile.TemporaryDirectory() as directory:
            def refused_run(args):
                raise kpi.BudgetRefused("refused")

            with self.assertRaises(kpi.BudgetRefused):
                kpi.collect(NOW, refused_run, store=kpi.Cache(directory))
            exporter = exporter_module()
            out = Path(directory) / "factory.json"
            out.write_text('{"generatedAt": "kept"}')
            stderr = io.StringIO()
            with patch.object(exporter, "advisor",
                              return_value=(None, types.SimpleNamespace(load=lambda: {}), None)), \
                 patch.object(exporter, "build", side_effect=kpi.BudgetRefused("refused")), \
                 contextlib.redirect_stderr(stderr):
                code = exporter.main(["--out", str(out)])
            self.assertEqual(code, 3)
            self.assertEqual(out.read_text(), '{"generatedAt": "kept"}')
            self.assertEqual(len([line for line in stderr.getvalue().splitlines() if line.strip()]), 1)

    def test_ci_headline_names_receipts_and_a_high_failed_share(self):
        unknown = {"failure_kind": "unknown"}
        ok = {"failure_kind": None}
        merged = [{"mergedAt": iso(NOW - 30)} for _ in range(31)]
        loud = kpi.ci_health({"runs": [unknown] * 89 + [ok] * 911, "live_minutes": [4.9, 4.9]}, merged, NOW)
        self.assertIn("8.9% runs failed", loud["display"])
        self.assertIn("unclassified 89", loud["display"])
        self.assertIn("4.9 min median to live (2/31 receipted)", loud["display"])
        self.assertEqual(loud["state"], "bad")
        self.assertIn("above 5% failed runs", " ".join(loud["details"]))
        quiet = kpi.ci_health({"runs": [unknown] + [ok] * 19, "live_minutes": [4.9]}, merged[:1], NOW)
        self.assertIn("5% runs failed", quiet["display"])
        self.assertIn("(1/1 receipted)", quiet["display"])
        self.assertIsNone(quiet["state"])
        slow = kpi.ci_health({"runs": [ok] * 20, "live_minutes": [20.0]}, merged[:1], NOW)
        self.assertEqual(slow["state"], "bad")
        self.assertIn("20.0 min median to live (1/1 receipted)", slow["display"])

    def test_merge_headline_uses_one_daily_basis(self):
        prs = [{"createdAt": iso(NOW - i * kpi.DAY - 120), "mergedAt": iso(NOW - i * kpi.DAY - 60)} for i in range(7)]
        tile = kpi.merges(prs, NOW)
        self.assertEqual(tile["display"], "1 merged in 24h · 1.0 per day over 7d · 1.0 min median")
        self.assertNotIn("/ week", tile["display"])
        self.assertIn("1.00 per day", " ".join(tile["details"]))

    def test_startup_and_policy_failures_keep_a_counted_unclassified_rest(self):
        rows = [
            {"id": 1, "check_suite_node_id": "s1", "conclusion": "startup_failure"},
            {"id": 2, "check_suite_node_id": "s2", "conclusion": "failure"},
            {"id": 3, "check_suite_node_id": "s3", "conclusion": "failure"},
            {"id": 4, "check_suite_node_id": "s4", "conclusion": "failure"},
            {"id": 5, "check_suite_node_id": "s5", "conclusion": "failure"},
            {"id": 6, "check_suite_node_id": "s6", "conclusion": "failure"},
        ]
        messages = {
            "s1": "",
            "s2": "The PR body must contain the line Fixes SOFT-1",
            "s3": "Live required checks do not match docs/ci-policy.yml",
            "s4": "failed to acquire a runner to run this job",
            "s5": "Process completed with exit code 1",
            "s6": "",
        }
        conclusions = {"s6": "STARTUP_FAILURE"}

        def run(args):
            ids = json.loads(args[-1].split("nodes(ids: ")[1].split(") {")[0])
            return {"data": {"nodes": [{"id": sid, "checkRuns": {"pageInfo": {"hasNextPage": False}, "nodes": [
                {"conclusion": conclusions.get(sid, "FAILURE"), "annotations": {"pageInfo": {"hasNextPage": False}, "nodes": [] if not messages[sid] else [
                    {"annotationLevel": "FAILURE", "message": messages[sid], "title": "Error"}]}}
            ]}} for sid in ids]}}

        self.assertEqual(kpi.read_failure_kinds("fixture/repo", rows, run),
                         {1: "infra", 2: "code", 3: "code", 4: "infra", 5: "unknown", 6: "infra"})


if __name__ == "__main__":
    unittest.main()
