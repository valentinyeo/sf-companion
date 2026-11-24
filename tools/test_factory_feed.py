import importlib.util
import os
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


class Advisor:
    PRIMARY = {}

    def runner_groups(self):
        return None

    def runners_text(self, groups):
        return "0 runners"

    def review_pill(self, plan, label):
        return ""

    def tone(self, delta):
        return "plain"

    def when(self, at):
        return datetime.fromtimestamp(at, timezone.utc).strftime("%a %H:%M")


def load_exporter(status_path):
    env = {"ADVISOR_BIN": str(HERE), "TOKEN_LADDER_STATUS": str(status_path)}
    env.update({key: "" for key in BLANK})
    env.update({"TOKEN_LADDER_LIMITS": "", "TOKEN_LADDER_CREDITS": ""})
    with patch.dict(os.environ, env, clear=False):
        loader = importlib.machinery.SourceFileLoader("export_factory_feed", str(EXPORTER))
        spec = importlib.util.spec_from_loader("export_factory_feed", loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module


class FeedPlanCards(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.state = Path(directory.name)
        self.status = self.state / "status.json"
        self.status.write_text('{"pools": {}}')
        self.feed = load_exporter(self.status)

    def limits(self, payload):
        (self.state / "lane-limits.json").write_text(payload)

    def card(self, plan):
        cards = self.feed.usage_part(Advisor(), {}, NOW)["cards"]
        return next(card for card in cards if card["plan"] == plan)

    def test_every_lane_plan_gets_a_card(self):
        self.limits("{}")
        cards = self.feed.usage_part(Advisor(), {}, NOW)["cards"]
        self.assertEqual([card["plan"] for card in cards], list(self.feed.PLAN_ENUM))
        self.assertEqual([card["name"] for card in cards][-3:], ["Antigravity", "CommandCode", "Cursor"])
        for card in cards:
            self.assertIn("skip", card)
            self.assertIn("note", card)

    def test_a_retired_lane_shows_its_skip_and_end_date(self):
        self.limits('{"cursor": 2110825352.5}')
        cursor = self.card("cursor")
        self.assertEqual(cursor["skip"], {"reason": "manual skip (lane-limits)",
                                          "untilText": "2036-11-20 20:22 UTC"})
        self.assertEqual(cursor["mode"], "none")
        self.assertIsNone(cursor["usedPct"])
        self.assertIsNone(cursor["resetsText"])

    def test_a_recorded_reason_wins_over_the_default_wording(self):
        self.limits('{"cursor": {"until": 2110825352.5, "reason": "retired"}}')
        self.assertEqual(self.card("cursor")["skip"]["reason"], "retired")

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


if __name__ == "__main__":
    unittest.main()
