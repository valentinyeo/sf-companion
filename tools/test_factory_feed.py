import importlib.util
import json
import os
import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
EXPORTER = HERE / "export-factory-feed.py"
BLANK = ("OPENCODE_HISTORY", "AI_GATEWAY_API_KEY", "GROK_STATE", "DEEPSEEK_API_KEY",
         "OPENROUTER_MANAGEMENT_KEY", "OPENROUTER_MANAGEMENT_KEY_AGENTS")

NOW = 1795525000

AGY_SAMPLE = "\n".join((
    "Gemini Models\tWeekly Limit Remaining\t65%\t2026-11-30T20:03:27Z",
    "Gemini Models\tFive Hour Limit Remaining\t100%\t2026-11-25T14:38:33Z",
    "Claude and GPT models\tWeekly Limit Remaining\t100%\t2026-12-02T09:38:33Z",
    "Claude and GPT models\tFive Hour Limit Remaining\t100%\t2026-11-25T14:38:33Z",
)) + "\n"


class Advisor:
    PRIMARY = {"opencode": "month", "vercel": "month"}

    def runner_groups(self):
        return None

    def runners_text(self, groups):
        if groups is None:
            return "0 runners"
        parts = sorted(groups.items(), key=lambda kv: (-kv[1], kv[0]))
        return " · ".join(f"{c} {m} {eff}".strip() for (m, eff), c in parts) or "0 runners"

    def model_name(self, model):
        return re.sub(r"-(low|medium|high)$", "", (model or "?").split("/")[-1])

    def review_pill(self, plan, label):
        return ""

    def tone(self, delta):
        return "" if delta is None or delta <= 0 else " hot" if delta > 10 else " warm"

    def when(self, at):
        return datetime.fromtimestamp(at, timezone.utc).strftime("%a %H:%M")


def load_exporter(status_path):
    env = {"ADVISOR_BIN": str(HERE), "TOKEN_LADDER_STATUS": str(status_path)}
    env.update({key: "" for key in BLANK})
    env.update({
        "TOKEN_LADDER_LIMITS": "",
        "TOKEN_LADDER_CREDITS": "",
        "TOKEN_LADDER_LAUNCHES": "",
        "OPENCODE_AUTH_FILE": str(status_path.with_name("missing-auth.json")),
        "AGY_BIN": str(status_path.with_name("missing-agy")),
    })
    with patch.dict(os.environ, env, clear=False):
        loader = importlib.machinery.SourceFileLoader("export_factory_feed", str(EXPORTER))
        spec = importlib.util.spec_from_loader("export_factory_feed", loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module


def write_fake_proc(root, pid, cmdline=None, cwd=None, state="S"):
    proc_dir = root / str(pid)
    proc_dir.mkdir(parents=True, exist_ok=True)
    (proc_dir / "stat").write_text(f"{pid} (python3) {state} 1 1 1 0 -1 0 0 0 0 0 0 0 0 0 20 0 1 0 100 0 0\n")
    if cmdline is not None:
        (proc_dir / "cmdline").write_bytes(b"\x00".join(part.encode() for part in cmdline) + b"\x00")
    if cwd is not None:
        os.symlink(str(cwd), proc_dir / "cwd")


def write_fake_agy(directory, body):
    path = directory / "agy"
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(0o755)
    return path


class FeedPlanCards(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.state = Path(directory.name)
        self.status = self.state / "status.json"
        self.status.write_text('{"pools": {}}')
        self.feed = load_exporter(self.status)
        self.feed.OPENCODE_AUTH_FILES = ()

    def limits(self, payload):
        (self.state / "lane-limits.json").write_text(payload)

    def card(self, plan, metric=None):
        cards = self.feed.usage_part(Advisor(), metric or {}, NOW)["cards"]
        return next(card for card in cards if card["plan"] == plan)

    def test_every_lane_plan_gets_a_card_and_retired_plans_come_last(self):
        self.limits("{}")
        cards = self.feed.usage_part(Advisor(), {}, NOW)["cards"]
        plans = [card["plan"] for card in cards]
        self.assertEqual(plans, sorted(self.feed.PLAN_ENUM, key=lambda plan: plan in self.feed.INACTIVE_PLANS))
        self.assertEqual([card["name"] for card in cards][-3:], ["Grok", "DeepSeek", "Cursor"])
        self.assertEqual({card["plan"] for card in cards if card["inactive"]}, set(self.feed.INACTIVE_PLANS))
        for card in cards:
            self.assertIn("skip", card)
            self.assertIn("note", card)

    def test_an_inactive_plan_shows_no_reading_and_ignores_lane_limits(self):
        self.limits('{"cursor": 2110825352.5}')
        cursor = self.card("cursor")
        self.assertTrue(cursor["inactive"])
        self.assertIsNone(cursor["skip"])
        self.assertEqual(cursor["mode"], "none")
        self.assertIsNone(cursor["usedPct"])
        self.assertIsNone(cursor["resetsText"])
        self.assertIsNone(cursor["paceDelta"])
        self.assertEqual(cursor["windows"], [])

    def test_inactive_plans_make_no_api_calls(self):
        self.limits("{}")
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}, clear=False), \
                patch.object(self.feed, "fetch_json", side_effect=AssertionError("unexpected API call")):
            for plan in self.feed.INACTIVE_PLANS:
                self.assertTrue(self.card(plan)["inactive"])

    def test_a_recorded_reason_wins_over_the_default_wording(self):
        self.limits('{"opencode": {"until": 2110825352.5, "reason": "retired"}}')
        self.assertEqual(self.card("opencode")["skip"]["reason"], "retired")

    def test_an_expired_skip_is_dropped(self):
        self.limits('{"opencode": 1795524000.0}')
        self.assertIsNone(self.card("opencode")["skip"])

    def test_a_pool_alias_carries_the_skip_too(self):
        self.limits('{"google": 2110825352.5}')
        self.assertEqual(self.card("antigravity")["skip"]["untilText"], "2036-11-20 20:22 UTC")

    def test_antigravity_carries_its_quota_state(self):
        self.limits("{}")
        self.status.write_text(
            '{"pools": {"google": {"used_up": true, "used_up_at": "2026-11-24T00:46:05Z",'
            ' "used_pct": null, "source": "agy local history timestamps"}}}'
        )
        antigravity = self.card("antigravity")
        self.assertEqual(antigravity["mode"], "none")
        self.assertEqual(antigravity["note"], "Quota used up at 2026-11-24T00:46:05Z · limit unknown")

    def test_commandcode_reads_its_monthly_credits(self):
        self.limits("{}")
        (self.state / "lane-credits.json").write_text(
            '{"commandcode": {"credits": 66.4094930002, "period_start": 1795384346.0,'
            ' "period_end": 1797976346.0, "at": 1795523477.8}}'
        )
        commandcode = self.card("commandcode")
        self.assertEqual(commandcode["mode"], "percent")
        self.assertAlmostEqual(commandcode["usedPct"], 5.13, places=2)
        self.assertEqual(commandcode["primaryWindow"], "month")
        self.assertEqual(commandcode["note"], "66.4095/70 monthly credits left (~$94.87 Flash usage)")
        self.assertIsNotNone(commandcode["resetsText"])
        self.assertIsNone(commandcode["skip"])

    def test_a_finished_commandcode_period_leaves_the_card_without_a_reading(self):
        self.limits("{}")
        (self.state / "lane-credits.json").write_text(
            '{"commandcode": {"credits": 66.4094930002, "period_start": 1795384346.0,'
            ' "period_end": 1795524999.0}}'
        )
        commandcode = self.card("commandcode")
        self.assertEqual(commandcode["mode"], "none")
        self.assertIsNone(commandcode["usedPct"])

    def test_antigravity_reads_its_limits_from_the_agy_cli(self):
        self.limits("{}")
        agy = write_fake_agy(self.state, "cat <<'ROWS'\n" + AGY_SAMPLE + "ROWS")
        with patch.object(self.feed, "AGY_BIN", agy):
            antigravity = self.card("antigravity")
        self.assertEqual(antigravity["mode"], "percent")
        self.assertEqual(antigravity["usedPct"], 35.0)
        self.assertEqual(antigravity["primaryWindow"], "week")
        self.assertEqual(antigravity["resetsText"], "Mon 20:03")
        self.assertEqual(antigravity["windows"], [
            {"label": "gemini 5h", "usedPct": 0.0},
            {"label": "claude/gpt week", "usedPct": 0.0},
            {"label": "claude/gpt 5h", "usedPct": 0.0},
        ])
        self.assertIsNone(antigravity["note"])

    def test_antigravity_runs_agy_in_an_empty_directory(self):
        self.limits("{}")
        log = self.state / "agy.log"
        agy = write_fake_agy(self.state, "\n".join((
            f"printf '%s\\n' \"$@\" > {log}",
            f"ls -A | wc -l >> {log}",
            "cat <<'ROWS'",
            AGY_SAMPLE + "ROWS",
        )))
        with patch.object(self.feed, "AGY_BIN", agy):
            self.card("antigravity")
        self.assertEqual(log.read_text().split(), ["-p", "/usage", "--print-timeout", "45s", "0"])

    def test_antigravity_skips_rows_that_are_not_four_fields(self):
        self.limits("{}")
        junk = "\n".join((
            "Gemini Models\tWeekly Limit Remaining\t65%",
            "Gemini Models\tWeekly Limit Remaining\t65\t2026-11-30T20:03:27Z",
            "Gemini Models\tWeekly Limit Remaining\t65%\tsoon",
            "Gemini Models\tMonthly Limit Remaining\t40%\t2026-11-30T20:03:27Z",
            "no tabs here at all",
        ))
        agy = write_fake_agy(self.state, "cat <<'ROWS'\n" + junk + "\n" + AGY_SAMPLE + "ROWS")
        with patch.object(self.feed, "AGY_BIN", agy):
            antigravity = self.card("antigravity")
        self.assertEqual(antigravity["usedPct"], 35.0)
        self.assertEqual([window["label"] for window in antigravity["windows"]],
                         ["gemini 5h", "claude/gpt week", "claude/gpt 5h"])

    def test_a_failing_agy_keeps_the_card_and_marks_the_source_unavailable(self):
        self.limits("{}")
        self.status.write_text(
            '{"pools": {"google": {"used_up": true, "used_up_at": "2026-11-24T00:46:05Z",'
            ' "used_pct": null, "source": "agy local history timestamps"}}}'
        )
        agy = write_fake_agy(self.state, "printf 'no limits\\n' >&2\nexit 1")
        with patch.object(self.feed, "AGY_BIN", agy):
            antigravity = self.card("antigravity")
        self.assertEqual(antigravity["mode"], "none")
        self.assertIsNone(antigravity["usedPct"])
        self.assertEqual(antigravity["windows"], [])
        self.assertEqual(antigravity["note"], "Quota used up at 2026-11-24T00:46:05Z · limit unknown")

    def test_opencode_reads_go_usage_endpoint_with_auth_file_key(self):
        self.limits("{}")
        auth_file = self.state / "auth.json"
        auth_file.write_text(json.dumps({"opencode-go": {"type": "api", "key": "test-token"}}))
        (self.state / "lane-credits.json").write_text(
            json.dumps({"opencode": {"usd": 6.2, "at": NOW - 600, "source": "OpenCode live console"}})
        )
        payload = {
            "usage": {
                "rolling": {"status": "ok", "percent": 12.5, "resetsAt": "2026-11-25T03:00:00.000Z"},
                "weekly": {"status": "ok", "percent": 40.0, "resetsAt": "2026-11-30T00:00:00.000Z"},
                "monthly": {"status": "rate-limited", "percent": 100.0, "resetsAt": "2026-11-30T23:01:10.000Z"},
            }
        }
        seen = []

        def fake_fetch(url, key):
            seen.append((url, key))
            return payload

        with patch.dict(os.environ, {"OPENCODE_AUTH_FILE": str(auth_file)}, clear=False), \
                patch.object(self.feed, "fetch_json", side_effect=fake_fetch):
            opencode = self.card("opencode")
        self.assertEqual(len(seen), 1)
        self.assertTrue(seen[0][0].endswith("/v1/usage"))
        self.assertEqual(seen[0][1], "test-token")
        self.assertEqual(opencode["mode"], "percent")
        self.assertEqual(opencode["usedPct"], 100.0)
        self.assertEqual(opencode["primaryWindow"], "month")
        self.assertIsNotNone(opencode["resetsText"])
        self.assertEqual(opencode["windows"], [
            {"label": "month", "usedPct": 100.0},
            {"label": "week", "usedPct": 40.0},
            {"label": "5h", "usedPct": 12.5},
        ])
        self.assertEqual(opencode["note"], "Prepaid credit estimate: $6.20 left")

    def test_opencode_falls_back_to_anchored_credit_estimate_when_api_fails(self):
        self.limits("{}")
        (self.state / "lane-credits.json").write_text(
            json.dumps({"opencode": {"usd": 6.2, "at": NOW - 3600, "source": "OpenCode live console"}})
        )
        with patch.object(self.feed, "opencode_usage_api", return_value=None):
            opencode = self.card("opencode")
        self.assertEqual(opencode["mode"], "credit")
        self.assertEqual(opencode["creditUsd"], 6.2)
        self.assertEqual(opencode["creditSubLabel"], "estimate")
        self.assertEqual(opencode["creditAsOf"], " · as of 1h ago")
        self.assertIn("estimate", opencode["note"].lower())

    def test_live_plan_pick_runners_count_unfinished_alive_workers_per_lane(self):
        self.limits("{}")
        proc = self.state / "proc"
        work_a = self.state / "work-a"
        work_b = self.state / "work-b"
        work_c = self.state / "work-c"
        work_a.mkdir()
        work_b.mkdir()
        work_c.mkdir()
        write_fake_proc(proc, 1001, ["python3", "/home/valentin/.local/bin/plan-pick", "--run"], cwd=work_a)
        write_fake_proc(proc, 1002, ["python3", "/home/valentin/.local/bin/plan-pick", "--run"], cwd=work_b)
        write_fake_proc(proc, 1003, ["python3", "/home/valentin/.local/bin/lease", "X", "run", "--", "plan-pick", "--run"], cwd=work_c)
        write_fake_proc(proc, 2001, ["python3", "/home/valentin/.local/bin/plan-pick", "--run"], cwd=work_c, state="S")
        write_fake_proc(proc, 2002, ["python3", "/home/valentin/.local/bin/plan-pick", "--run"], cwd=work_c, state="Z")
        launches = self.state / "launches.jsonl"
        rows = [
            {"event": "start", "launch_id": "done-1", "lane": "codex", "cwd": str(work_a), "model": "gpt-6.1-sol", "effort": "high", "at": NOW - 200},
            {"event": "finish", "launch_id": "done-1", "finished_at": NOW - 100, "exit_code": 0},
            {"event": "start", "launch_id": "live-cwd-1", "lane": "antigravity", "cwd": str(work_a), "model": "gemini-4-neon-high", "effort": "high", "at": NOW - 50},
            {"event": "start", "launch_id": "live-cwd-2", "lane": "vercel-zai", "cwd": str(work_b), "model": "zai/glm-5.3-flash", "effort": "medium", "at": NOW - 40},
            {"event": "start", "launch_id": "live-pid-1", "lane": "opencode", "pid": 2001, "cwd": str(work_c), "model": "deepseek-v4.1-flash", "effort": "medium", "at": NOW - 30},
            {"event": "start", "launch_id": "zombie-pid", "lane": "opencode", "pid": 2002, "cwd": str(work_c), "model": "deepseek-v4.1-flash", "effort": "medium", "at": NOW - 20},
            {"event": "start", "launch_id": "dead-pid", "lane": "codex", "pid": 99999, "cwd": str(work_c), "model": "gpt-6.1-sol", "effort": "high", "at": NOW - 10},
        ]
        launches.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        with patch.object(self.feed, "PROC_ROOT", proc):
            usage = self.feed.usage_part(Advisor(), {}, NOW)
        by_plan = {card["plan"]: card for card in usage["cards"]}
        self.assertTrue(by_plan["antigravity"]["runnersLive"])
        self.assertEqual(by_plan["antigravity"]["runnersText"], "1 gemini-4-neon high")
        self.assertEqual(by_plan["vercel"]["runnersText"], "1 glm-5.3-flash medium")
        self.assertEqual(by_plan["opencode"]["runnersText"], "1 deepseek-v4.1-flash medium")
        self.assertEqual(by_plan["codex"]["runnersText"], "0 runners")

    def test_burn_keeps_only_fixed_1h_window(self):
        self.limits("{}")
        metric = {
            "windows": {
                "1h": {"plans": {"claude": {"pts": 2, "gbp": 0.5, "priced_pts": 2}}},
                "7d": {"plans": {"claude": {"pts": 14, "gbp": 7.0, "priced_pts": 14}}},
                "30d": {"plans": {"claude": {"pts": 40, "gbp": 20.0, "priced_pts": 40}}},
            }
        }
        usage = self.feed.usage_part(Advisor(), metric, NOW)
        self.assertEqual(list(usage["burn"].keys()), ["1h"])
        self.assertEqual(usage["burn"]["1h"]["claude"]["pts"], 2)


if __name__ == "__main__":
    unittest.main()
