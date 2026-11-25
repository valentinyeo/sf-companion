import importlib.util
import io
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

    def __init__(self, groups=None):
        self.groups = groups

    def runner_groups(self):
        return self.groups

    def runners_text(self, groups):
        if groups is None:
            return "–"
        parts = sorted(groups.items(), key=lambda kv: (-kv[1], kv[0]))
        return " · ".join(f"{c} {m} {eff}".strip() for (m, eff), c in parts) or "0 runners"

    def model_name(self, model):
        return re.sub(r"-(low|medium|high)$", "", (model or "?").split("/")[-1])

    def review_pill(self, plan, label):
        return ""

    def tone(self, delta):
        return "" if delta is None or delta <= 0 else " hot" if delta > 10 else " warm"

    def when(self, at, kind="week"):
        stamp = datetime.fromtimestamp(at, timezone.utc)
        return stamp.strftime("%a %H:%M") if kind != "month" else f"{stamp.day} {stamp:%b}"


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


def write_fake_roster(directory, body):
    path = directory / "roster-live"
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(0o755)
    return path


ROSTER_ROWS = "\n".join((
    "Board Drain Loop (live-2abf0cb7, claude, ~/projects/vstack)",
    "HT Features (live-7afb95d9, claude, ~/projects/hypertask)",
    "Board Drain Loop (live-2abf0cb7, claude, ~/projects/vstack)",
    "Claude CRO (pid 720312, claude, ~/projects/claude-cro)",
    "Pi Runner (live-9dbc7da5, codex, ~/projects/multiprompt)",
    "Pi Runner (live-9dbc7da5, codex, ~/projects/multiprompt)",
)) + "\n"


class FeedPlanCards(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.state = Path(directory.name)
        self.status = self.state / "status.json"
        self.status.write_text('{"pools": {}}')
        self.feed = load_exporter(self.status)
        self.feed.OPENCODE_AUTH_FILES = ()
        self.feed.ROSTER_BIN = self.state / "missing-roster"

    def limits(self, payload):
        (self.state / "lane-limits.json").write_text(payload)

    def card(self, plan, metric=None):
        cards = self.feed.usage_part(Advisor(), metric or {}, NOW)["cards"]
        return next(card for card in cards if card["plan"] == plan)

    def test_every_lane_plan_gets_a_card_in_plan_order(self):
        self.limits("{}")
        cards = self.feed.usage_part(Advisor(), {}, NOW)["cards"]
        self.assertEqual([card["plan"] for card in cards], list(self.feed.PLAN_ENUM))
        self.assertEqual([card["name"] for card in cards],
                         ["Claude", "Codex", "OpenCode", "Vercel Token Pass", "OpenRouter", "Antigravity", "CommandCode"])
        for card in cards:
            self.assertIn("skip", card)
            self.assertIn("note", card)
            self.assertNotIn("inactive", card)

    def test_retired_plans_are_gone_from_the_cards_and_the_burn(self):
        self.limits("{}")
        metric = {"windows": {"1h": {"plans": {"grok": {"pts": 3, "gbp": 1.0, "priced_pts": 3}}}}}
        usage = self.feed.usage_part(Advisor(), metric, NOW)
        plans = {card["plan"] for card in usage["cards"]}
        self.assertFalse(plans & {"grok", "deepseek", "cursor"})
        self.assertEqual(set(usage["burn"]["1h"]), set(self.feed.PLAN_ENUM))

    def test_live_chats_count_once_per_session_and_follow_their_harness(self):
        self.limits("{}")
        roster = write_fake_roster(self.state, "cat <<'ROWS'\n" + ROSTER_ROWS + "ROWS")
        with patch.object(self.feed, "ROSTER_BIN", roster):
            cards = {card["plan"]: card for card in self.feed.usage_part(Advisor(), {}, NOW)["cards"]}
        self.assertEqual(cards["claude"]["loadText"], "3 chats")
        self.assertEqual(cards["codex"]["loadText"], "1 chat")
        self.assertEqual(cards["opencode"]["loadText"], "–")

    def test_an_unreadable_roster_shows_no_chat_count(self):
        self.limits("{}")
        roster = write_fake_roster(self.state, "printf 'boom\\n' >&2\nexit 1")
        with patch.object(self.feed, "ROSTER_BIN", roster):
            cards = {card["plan"]: card for card in self.feed.usage_part(Advisor(groups={"vercel": {("glm-5.3-flash", "medium"): 2}}), {}, NOW)["cards"]}
        self.assertEqual(cards["claude"]["loadText"], "–")
        self.assertEqual(cards["vercel"]["loadText"], "2 runners")

    def test_cards_sort_by_chats_plus_runners_and_idle_cards_come_last(self):
        self.limits("{}")
        roster = write_fake_roster(self.state, "cat <<'ROWS'\n" + ROSTER_ROWS + "ROWS")
        groups = {
            "claude": {("Sonnet", "high"): 1},
            "codex": {("GPT 6.1 Sol", "high"): 1},
            "opencode": {("DeepSeek 4.1 Flash", "medium"): 2},
        }
        with patch.object(self.feed, "ROSTER_BIN", roster):
            cards = self.feed.usage_part(Advisor(groups=groups), {}, NOW)["cards"]
        self.assertEqual([card["plan"] for card in cards],
                         ["claude", "codex", "opencode", "vercel", "openrouter", "antigravity", "commandcode"])
        by_plan = {card["plan"]: card for card in cards}
        self.assertEqual(by_plan["claude"]["loadText"], "3 chats · 1 runner")
        self.assertEqual(by_plan["codex"]["loadText"], "1 chat · 1 runner")
        self.assertEqual(by_plan["opencode"]["loadText"], "2 runners")
        self.assertEqual(by_plan["vercel"]["loadText"], "idle")

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

    def test_vercel_shows_the_token_pass_percent_not_the_gateway_balance(self):
        self.limits("{}")
        (self.state / "lane-credits.json").write_text(
            json.dumps({"vercel": {"usd": 30, "at": NOW, "limit_usd": 110}})
        )
        payload = json.dumps({
            "balance": "19.9740337796",
            "token_pass": {"remaining": "30", "resets_at": "2026-12-05T08:00:00.000Z"},
            "total_used": "661.1272349684",
        })
        seen = []

        class Response:
            def __enter__(self):
                return io.StringIO(payload)

            def __exit__(self, *args):
                return False

        def fake_urlopen(request, timeout=None):
            seen.append(request.full_url)
            return Response()

        with patch.dict(os.environ, {"AI_GATEWAY_API_KEY": "test-key"}, clear=False), \
                patch.object(self.feed.urllib.request, "urlopen", side_effect=fake_urlopen):
            vercel = self.card("vercel")
        self.assertEqual(seen, ["https://ai-gateway.vercel.sh/v1/credits"])
        self.assertEqual(vercel["name"], "Vercel Token Pass")
        self.assertEqual(vercel["mode"], "percent")
        self.assertAlmostEqual(vercel["usedPct"], 72.73, places=2)
        self.assertGreater(vercel["paceDelta"], 0)
        self.assertEqual(vercel["primaryWindow"], "month")
        self.assertEqual(vercel["resetsText"], "5 Dec")
        self.assertEqual(vercel["note"], "$30.00 of $110 pass credit left")
        self.assertIsNone(vercel["creditUsd"])
        self.assertIsNone(vercel["skip"])

    def test_vercel_without_a_published_total_quotes_no_number_of_its_own(self):
        self.limits("{}")
        (self.state / "lane-credits.json").write_text(json.dumps({"vercel": {"usd": 30, "at": NOW}}))
        payload = json.dumps({
            "balance": "19.9740337796",
            "token_pass": {"remaining": "30", "resets_at": "2026-12-05T08:00:00.000Z"},
            "total_used": "661.1272349684",
        })

        class Response:
            def __enter__(self):
                return io.StringIO(payload)

            def __exit__(self, *args):
                return False

        with patch.dict(os.environ, {"AI_GATEWAY_API_KEY": "test-key"}, clear=False), \
                patch.object(self.feed.urllib.request, "urlopen", side_effect=lambda *a, **k: Response()):
            vercel = self.card("vercel")
        self.assertEqual(vercel["mode"], "none")
        self.assertIsNone(vercel["usedPct"])
        self.assertIsNone(vercel["resetsText"])
        self.assertEqual(vercel["note"], "$30.00 of unknown total pass credit left")

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
            if url == self.feed.OPENCODE_BALANCE_API:
                raise OSError("403 Forbidden")
            return payload

        with patch.dict(os.environ, {"OPENCODE_AUTH_FILE": str(auth_file)}, clear=False), \
                patch.object(self.feed, "fetch_json", side_effect=fake_fetch):
            opencode = self.card("opencode")
        self.assertEqual([url for url, _ in seen],
                         [self.feed.OPENCODE_USAGE_API, self.feed.OPENCODE_BALANCE_API])
        self.assertEqual({key for _, key in seen}, {"test-token"})
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

    def test_opencode_reads_prepaid_credit_from_the_console_balance_endpoint(self):
        self.limits("{}")
        auth_file = self.state / "auth.json"
        auth_file.write_text(json.dumps({"opencode-go": {"type": "api", "key": "test-token"}}))
        (self.state / "lane-credits.json").write_text(
            json.dumps({"opencode": {"usd": 8.01, "at": NOW - 600, "source": "plan-pick"}})
        )
        payload = {
            "usage": {
                "rolling": {"status": "ok", "percent": 12.5, "resetsAt": "2026-11-25T03:00:00.000Z"},
                "weekly": {"status": "ok", "percent": 40.0, "resetsAt": "2026-11-30T00:00:00.000Z"},
                "monthly": {"status": "rate-limited", "percent": 100.0, "resetsAt": "2026-11-30T23:01:10.000Z"},
            }
        }

        def fake_fetch(url, key):
            if url == self.feed.OPENCODE_BALANCE_API:
                return {"balanceMicroCents": 577000000, "availableMicroCents": 577000000}
            return payload

        with patch.dict(os.environ, {"OPENCODE_AUTH_FILE": str(auth_file)}, clear=False), \
                patch.object(self.feed, "fetch_json", side_effect=fake_fetch):
            opencode = self.card("opencode")
        self.assertEqual(opencode["mode"], "percent")
        self.assertEqual(opencode["usedPct"], 100.0)
        self.assertEqual(opencode["note"], "Prepaid credit: $5.77 left")

    def test_opencode_carries_the_console_balance_when_go_usage_is_unreadable(self):
        self.limits("{}")
        auth_file = self.state / "auth.json"
        auth_file.write_text(json.dumps({"opencode-go": {"type": "api", "key": "test-token"}}))
        (self.state / "lane-credits.json").write_text(
            json.dumps({"opencode": {"usd": 8.01, "at": NOW - 600, "source": "plan-pick"}})
        )

        def fake_fetch(url, key):
            return {"balanceMicroCents": 577000000}

        with patch.dict(os.environ, {"OPENCODE_AUTH_FILE": str(auth_file)}, clear=False), \
                patch.object(self.feed, "opencode_usage_api", return_value=None), \
                patch.object(self.feed, "fetch_json", side_effect=fake_fetch):
            opencode = self.card("opencode")
        self.assertEqual(opencode["mode"], "credit")
        self.assertEqual(opencode["creditUsd"], 5.77)
        self.assertEqual(opencode["creditSubLabel"], "credit")
        self.assertEqual(opencode["creditAsOf"], " · as of 0m ago")
        self.assertIsNone(opencode["note"])

    def test_opencode_falls_back_to_anchored_credit_estimate_when_api_fails(self):
        self.limits("{}")
        (self.state / "lane-credits.json").write_text(
            json.dumps({"opencode": {"usd": 6.2, "at": NOW - 3600, "source": "OpenCode live console"}})
        )
        with patch.object(self.feed, "opencode_usage_api", return_value=None), \
                patch.object(self.feed, "opencode_console_credit", return_value=None):
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
