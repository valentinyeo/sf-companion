import copy
import importlib.util
import json
import os
import tempfile
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
        "pools": {"claude": {"used_pct": 50, "pace_ratio": 2, "resets_at": NOW + kpi.DAY},
                  "codex": {"used_pct": 0, "pace_ratio": 0, "resets_at": NOW + kpi.DAY},
                  "grok": {"used_pct": 10, "pace_ratio": None}},
        "roster": {"rows": [{"name": "Product Lead", "kind": "lead"},
                              {"name": "Factory Lead", "kind": "chief"},
                              {"name": "Runner", "kind": "runner-pool"}]},
        "log": f"{iso(NOW - 60)} solo-wake: Product Lead loop: ok, loop fired 2 min ago\n"
               f"{iso(NOW - 60)} solo-wake: Factory Lead loop: would arm, no scheduled turn in 45 min\n",
    }


def exported(fixture):
    def run(args):
        if args[0] == "hypertask":
            board = int(args[args.index("--project") + 1])
            tasks = [t for t in fixture["tickets"] if t["boardId"] == board]
            return {"success": True, "tasks": tasks, "total": len(tasks)}
        if args[0] == "token-ladder":
            return fixture["pools"]
        return {"data": {"repository": {"pullRequests": {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "nodes": [dict(p, comments={"pageInfo": {"hasNextPage": False}, "nodes": p["comments"]})
                      for p in fixture["prs"]],
        }}}}

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "roster.json").write_text(json.dumps(fixture["roster"]))
        (root / "loop.log").write_text(fixture["log"])
        with patch.dict(os.environ, {"FACTORY_REPOS": "fixture/repo", "FACTORY_ROSTER": str(root / "roster.json"),
                                     "FACTORY_LOOP_LOG": str(root / "loop.log")}):
            return kpi.collect(NOW, run)


class FactoryKpiTests(unittest.TestCase):
    def test_seeded_sources_change_only_their_tile(self):
        baseline = exported(seed())
        self.assertEqual(baseline["notes"], [])
        self.assertEqual([t["display"] for t in baseline["tiles"]],
                         ["1 / day · 2 / week", "50%", "1/2 over pace", "50%"])
        for index in range(4):
            fixture = seed()
            if index == 0:
                fixture["tickets"][1]["sectionChangedAt"] = iso(NOW - 60)
            elif index == 1:
                fixture["prs"][1]["comments"][0]["body"] = "PASS"
            elif index == 2:
                fixture["pools"]["claude"]["pace_ratio"] = 0.5
            else:
                fixture["log"] += f"{iso(NOW)} solo-wake: Factory Lead loop: ok, loop fired 1 min ago\n"
            actual = exported(fixture)
            self.assertNotEqual(actual["tiles"][index]["display"], baseline["tiles"][index]["display"])
            for other in range(4):
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
        self.assertEqual([t["id"] for t in result["tiles"]], ["verifier", "pace"])
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
        result = exported(fixture)["tiles"][-1]
        self.assertEqual(result["display"], "0%")
        fixture["log"] = f"{iso(NOW + 60)} solo-wake: Product Lead loop: ok, loop fired 1 min ago\n"
        self.assertEqual(exported(fixture)["tiles"][-1]["id"], "pace")

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
            if "--slurp" in args:
                return [[{"body": "FAIL", "created_at": iso(NOW - 120)}],
                        [{"body": "PASS", "created_at": iso(NOW - 60)}]]
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
        self.assertEqual(len(calls), 3)

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
        self.assertEqual(exported(fixture)["tiles"][-1]["display"], "0%")

    def test_exporter_contract_accepts_seeded_kpis_and_rejects_missing_provenance(self):
        with patch.dict(os.environ, {"ADVISOR_BIN": "/fixture", "TOKEN_LADDER_STATUS": "/fixture/status.json"}):
            spec = importlib.util.spec_from_file_location("exporter", Path(__file__).with_name("export-factory-feed.py"))
            exporter = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(exporter)
        feed = {"generatedAt": "2026-11-16T12:00:00Z", "usage": {"cards": [], "burn": {}}, "kpis": exported(seed())}
        self.assertEqual(exporter.validate(feed), [])
        broken = copy.deepcopy(feed)
        broken["kpis"]["tiles"][0]["source"] = ""
        self.assertTrue(exporter.validate(broken))


if __name__ == "__main__":
    unittest.main()
