import json
from pathlib import Path
import random
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import factory_burn as burn

NOW = 1795708800


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def claude(at, identity, usage, text="", kind="assistant"):
    return {"type": kind, "timestamp": burn.iso(at), "uuid": identity,
            "message": {"id": identity, "model": "fixture-model", "usage": usage,
                        "content": [{"type": "text", "text": text}]}}


class BurnReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.path = self.home / ".claude/projects/project/session.jsonl"
        config = self.home / "projects/token-ladder/config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"list_prices": {"fixture-model": {"in": 2, "out": 10, "cached": 0.2, "cache_write": 2.5}}}))

    def report(self):
        result = burn.local_report(self.home, NOW)
        self.assertEqual(burn.validate(result), [])
        return result

    def test_claude_deduplicates_stream_updates_and_infers_only_assistant_text_per_hour(self):
        usage = {"input_tokens": 10, "output_tokens": 4, "cache_read_input_tokens": 20, "cache_creation_input_tokens": 5}
        write_rows(self.path, [
            claude(NOW - 7200, "a", dict(usage, output_tokens=1), "VSTA-7"),
            claude(NOW - 7200, "a", usage, "VSTA-7"),
            claude(NOW - 3600, "b", usage, "VSTA-8 VSTA-8"),
            claude(NOW - 3600, "user", {}, "VSTA-99 " * 10, "user"),
        ])
        rows = self.report()["rows"]
        self.assertEqual([row["ticket"] for row in rows], ["VSTA-7", "VSTA-8"])
        self.assertEqual(sum(row["output"] for row in rows), 8)
        self.assertTrue(all(row["attribution"] == "inferred" for row in rows))
        self.assertAlmostEqual(rows[0]["listCostUsd"], (20 + 40 + 4 + 12.5) / 1_000_000)

    def test_assistant_tool_calls_count_ticket_mentions_but_tool_results_do_not(self):
        record = claude(NOW - 3600, "request", {"input_tokens": 10, "output_tokens": 1})
        record["message"]["content"] = [{"type": "tool_use", "input": {"command": "hypertask task get VSTA-329"}}]
        write_rows(self.path, [record, {"type": "user", "timestamp": burn.iso(NOW - 3600),
            "message": {"content": [{"type": "tool_result", "content": "VSTA-999 " * 20}]}}])
        self.assertEqual(self.report()["rows"][0]["ticket"], "VSTA-329")

    def test_duplicate_transcript_copies_do_not_multiply_usage(self):
        row = claude(NOW - 3600, "same-request", {"input_tokens": 10, "output_tokens": 3})
        write_rows(self.path, [row])
        write_rows(self.path.with_name("copy.jsonl"), [row])
        self.assertEqual(sum(row["input"] for row in self.report()["rows"]), 10)

    def test_codex_counts_cumulative_deltas_not_repeated_totals_or_double_cached_input(self):
        path = self.home / ".codex/sessions/2026/11/session.jsonl"
        rows = [{"type": "session_meta", "payload": {"id": "codex-session", "cwd": "/work/project"}}]
        for at, total, cached, output in [(NOW - 7200, 100, 30, 10), (NOW - 7100, 100, 30, 10), (NOW - 3600, 150, 40, 15)]:
            rows.append({"timestamp": burn.iso(at), "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": total, "cached_input_tokens": cached, "output_tokens": output}}}})
        write_rows(path, rows)
        result = self.report()["rows"]
        self.assertEqual(sum(row["input"] for row in result), 110)
        self.assertEqual(sum(row["cacheRead"] for row in result), 40)
        self.assertEqual(sum(row["output"] for row in result), 15)
        self.assertEqual(sum(row["requests"] for row in result), 2)
        self.assertTrue(all(row["listCostUsd"] is None for row in result))

    def test_worker_finish_joins_start_but_parent_session_is_not_worker_usage(self):
        write_rows(self.path, [claude(NOW - 4000, "parent-request", {"input_tokens": 5, "output_tokens": 2}, "VSTA-1")])
        path = self.home / ".local/state/token-ladder/launches.jsonl"
        write_rows(path, [
            {"event": "start", "at": NOW - 4500, "launch_id": "job", "session": "session", "lane": "claude", "model": "fixture-model", "cwd": "/work/project", "ticket": "VSTA-9"},
            {"event": "finish", "launch_id": "job", "finished_at": NOW - 60, "tokens": {"in": 20, "out": 10, "cached": 3}, "cost_usd": 1.25, "cost_basis": "list-equivalent"},
        ])
        rows = self.report()["rows"]
        self.assertEqual(sum(row["input"] for row in rows), 25)
        self.assertEqual({row["ticket"] for row in rows}, {"VSTA-1", "VSTA-9"})
        worker = next(row for row in rows if row["attribution"] == "recorded")
        self.assertEqual(worker["hour"], burn.iso((NOW - 60) // 3600 * 3600))
        self.assertEqual(worker["listCostUsd"], 1.25)

    def test_worker_receipt_matching_transcript_tokens_is_not_counted_twice(self):
        write_rows(self.path, [claude(NOW - 4000, "child-request", {"input_tokens": 20, "output_tokens": 10, "cache_read_input_tokens": 3})])
        path = self.home / ".local/state/token-ladder/launches.jsonl"
        write_rows(path, [
            {"event": "start", "at": NOW - 4500, "launch_id": "job", "lane": "claude", "model": "fixture-model", "ticket": "VSTA-9"},
            {"event": "finish", "launch_id": "job", "finished_at": NOW - 60, "tokens": {"in": 20, "out": 10, "cached": 3}},
        ])
        rows = self.report()["rows"]
        self.assertEqual(sum(row["input"] for row in rows), 20)
        self.assertEqual(rows[0]["ticket"], "VSTA-9")
        self.assertEqual(rows[0]["attribution"], "recorded")

    def test_request_only_is_not_a_measured_zero_or_priced_free(self):
        path = self.home / ".gemini/antigravity-cli/history.jsonl"
        write_rows(path, [{"timestamp": NOW - 60, "display": "private prompt", "conversationId": "agy-session", "workspace": "/work/project"}])
        row = self.report()["rows"][0]
        self.assertEqual(row["requests"], 1)
        self.assertFalse(row["tokensKnown"])
        self.assertIsNone(row["listCostUsd"])

    def test_reset_anchor_is_plan_specific_and_rolls_forward_without_calendar_week_guess(self):
        path = self.home / ".local/state/token-ladder/status.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"pools": {"claude": {"resets_at": NOW + 3000, "window_minutes": 10080}, "codex": {"resets_at": NOW - 2000, "window_minutes": 10080}, "google": {"resets_at": NOW + 20, "window_minutes": 300}}}))
        plans = {row["plan"]: row for row in self.report()["plans"]}
        self.assertEqual(plans["claude"]["weekStartsAt"], burn.iso(NOW + 3000 - burn.WEEK))
        self.assertEqual(plans["codex"]["weekResetsAt"], burn.iso(NOW - 2000 + burn.WEEK))
        self.assertIsNone(plans["antigravity"]["weekStartsAt"])

    def test_only_usage_labels_and_ticket_ids_cross_the_export_and_cache_boundary(self):
        private = "never-export-this-message-body"
        write_rows(self.path, [claude(NOW - 3600, "request", {"input_tokens": 10, "output_tokens": 1}, f"{private} VSTA-5 key=sk-secretfixturevalue")])
        result = self.report()
        exported = json.dumps(result)
        cached = "".join(path.read_text() for path in (self.home / ".local/state/sf-companion/burn-cache").glob("*.json"))
        self.assertNotIn(private, exported + cached)
        self.assertNotIn("sk-secretfixturevalue", exported + cached)
        self.assertNotIn("message", result["rows"][0])
        self.assertEqual(result["rows"][0]["ticket"], "VSTA-5")
        self.assertEqual(burn.label("chat user@example.test sk-abc"), "chat [redacted] [redacted]")

    def test_unchanged_files_are_not_parsed_again_and_append_rebuilds_only_its_file(self):
        write_rows(self.path, [claude(NOW - 3600, "a", {"input_tokens": 10, "output_tokens": 1})])
        first = self.report()
        with patch.object(burn, "transcript", side_effect=AssertionError("cache miss")):
            self.assertEqual(self.report(), first)
        with self.path.open("a") as handle:
            handle.write(json.dumps(claude(NOW - 60, "b", {"input_tokens": 20, "output_tokens": 2})) + "\n")
        self.assertEqual(sum(row["input"] for row in self.report()["rows"]), 30)

    def fixture_history(self):
        write_rows(self.home / ".claude/projects/project/session.jsonl", [
            claude(NOW - 7200, "claude-1", {"input_tokens": 10, "output_tokens": 4, "cache_read_input_tokens": 20}, "VSTA-7"),
            claude(NOW - 3600, "claude-2", {"input_tokens": 5, "output_tokens": 2})])
        write_rows(self.home / ".codex/sessions/2026/11/session.jsonl", [
            {"type": "session_meta", "payload": {"id": "codex-session", "cwd": "/work/codex-project"}},
            {"timestamp": burn.iso(NOW - 3600), "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {
                "input_tokens": 100, "cached_input_tokens": 30, "output_tokens": 10}}}}])
        write_rows(self.home / ".pi/agent/sessions/project/session.jsonl", [
            {"type": "session", "id": "pi-session", "cwd": "/work/pi-project"},
            {"type": "message", "id": "reply", "timestamp": burn.iso(NOW - 3600), "message": {
                "role": "assistant", "provider": "opencode-go", "model": "fixture-model",
                "content": [{"type": "text", "text": "VSTA-329"}],
                "usage": {"input": 10, "output": 2, "cacheRead": 100, "cacheWrite": 3}}}])
        write_rows(self.home / ".gemini/antigravity-cli/history.jsonl", [
            {"timestamp": burn.iso(NOW - 120), "display": "prompt", "conversationId": "agy", "workspace": "/work/agy-project"}])

    def test_a_warm_run_gives_the_same_report_as_a_cold_run(self):
        self.fixture_history()
        cache = self.home / "cold-and-warm"
        cold = burn.local_report(self.home, NOW, cache_dir=cache)
        with patch.object(burn, "transcript", side_effect=AssertionError("cache miss")), \
                patch.object(burn, "antigravity", side_effect=AssertionError("cache miss")):
            warm = burn.local_report(self.home, NOW, cache_dir=cache)
        self.assertEqual(warm, cold)
        self.assertEqual(len({row["plan"] for row in cold["rows"]}), 4)

    def test_parallel_reads_give_the_same_report_as_a_sequential_run(self):
        self.fixture_history()
        sequential = burn.local_report(self.home, NOW, cache_dir=self.home / "sequential", processes=1)
        with patch.object(burn, "PARALLEL_MINIMUM_FILES", 0):
            parallel = burn.local_report(self.home, NOW, cache_dir=self.home / "parallel", processes=2)
        self.assertEqual(parallel, sequential)

    def test_aggregation_preserves_counts_and_unknown_costs_over_generated_rows(self):
        rng = random.Random(329)
        for _ in range(50):
            rows = [burn.observation(NOW - 100, "claude", "session", "project", "model", {k: rng.randrange(1000) for k in burn.COUNTS[:4]}, str(i)) for i in range(rng.randrange(1, 30))]
            actual = burn.aggregate(rows)
            for field in burn.COUNTS:
                self.assertEqual(sum(row[field] for row in actual), sum(row[field] for row in rows))
            self.assertTrue(all(row["listCostUsd"] is None for row in actual))
            self.assertEqual(burn.aggregate(reversed(rows)), actual)

    def test_failed_remote_keeps_local_report_and_says_this_server_only(self):
        with patch.object(burn.subprocess, "run", side_effect=OSError("unreachable")):
            report = burn.collect(NOW, home=self.home)
        self.assertEqual(burn.validate(report), [])
        self.assertTrue(any("This server only" in note for note in report["notes"]))

    def test_remote_report_keeps_server_namespaces_and_imports_only_aggregated_rows(self):
        row = burn.observation(NOW - 60, "claude", "session", "fixture chat", "fixture-model", {"input": 10, "output": 2, "cacheRead": 3, "cacheWrite": 0}, "request")
        rows = burn.aggregate([row])
        remote = {"generatedAt": burn.iso(NOW), "rows": rows, "plans": [], "notes": ["claude: 1 transcript files"]}
        local = {"generatedAt": burn.iso(NOW), "rows": rows, "plans": [], "notes": []}
        with patch.object(burn, "local_report", return_value=local), patch.object(burn, "paid_usage", return_value=([], [])), patch.object(burn.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(remote))):
            report = burn.collect(NOW, self.home)
        self.assertEqual(burn.validate(report), [])
        self.assertEqual({item["plan"] for item in report["rows"]}, {"claude", "claude (Hetzner)"})
        self.assertEqual(sum(item["input"] for item in report["rows"]), 20)
        self.assertEqual(len({item["chatId"] for item in report["rows"]}), 2)
        self.assertTrue(any("Includes Hetzner" in note for note in report["notes"]))

    def test_pi_provider_usage_preserves_cache_prices_and_assistant_only_ticket_inference(self):
        path = self.home / ".pi/agent/sessions/project/session.jsonl"
        write_rows(path, [
            {"type": "session", "id": "pi-session", "cwd": "/work/pi-project"},
            {"type": "message", "id": "user", "timestamp": burn.iso(NOW - 3600),
             "message": {"role": "user", "content": "private user body VSTA-999 " * 10}},
            {"type": "message", "id": "reply", "timestamp": burn.iso(NOW - 3600), "message": {
                "role": "assistant", "provider": "opencode-go", "model": "fixture-model",
                "content": [{"type": "text", "text": "private reply VSTA-329"}],
                "usage": {"input": 10, "output": 2, "cacheRead": 100, "cacheWrite": 3,
                          "cost": {"total": 0.75, "totalFromProvider": False}}}},
        ])
        row = self.report()["rows"][0]
        self.assertEqual((row["plan"], row["chat"], row["ticket"]), ("opencode", "pi-project [" + burn.digest("pi-session")[:8] + "]", "VSTA-329"))
        self.assertEqual((row["input"], row["cacheRead"], row["cacheWrite"]), (10, 100, 3))
        self.assertEqual(row["listCostUsd"], 0.75)
        self.assertNotIn("private", json.dumps(self.report()))

    def test_agent_host_native_session_maps_to_the_published_chat_name(self):
        root = self.home / ".local/state/multiprompt"
        (root / "agent-host").mkdir(parents=True)
        (root / "chat-names.json").write_text(json.dumps({"live-fixture": {"name": "Named chat"}}))
        (root / "agent-host/chat.config.json").write_text(json.dumps({"tmux": "live-fixture"}))
        (root / "agent-host/chat.state.json").write_text(json.dumps({"sid": "host-session", "native_session": "session"}))
        write_rows(self.path, [claude(NOW - 3600, "a", {"input_tokens": 10, "output_tokens": 1})])
        self.assertEqual(self.report()["rows"][0]["chat"], "Named chat")

    def test_model_catalog_prices_cache_and_long_context_tiers_before_config_overrides(self):
        path = self.home / ".npm-global/lib/node_modules/@earendil-works/pi-coding-agent/node_modules/@earendil-works/pi-ai/dist/providers/data/anthropic.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"anthropic-messages": {"chat:catalog-model": {"id": "catalog-model", "cost": {
            "input": 2, "output": 10, "cacheRead": 0.2, "cacheWrite": 2.5,
            "tiers": [{"inputTokensAbove": 100, "input": 4, "output": 20, "cacheRead": 0.4, "cacheWrite": 5}]}}}}))
        prices = burn.list_prices(self.home)
        small = {"input": 10, "output": 3, "cacheRead": 20, "cacheWrite": 5}
        large = dict(small, cacheRead=200)
        self.assertAlmostEqual(burn.cost_of(small, "catalog-model", prices), (20 + 30 + 4 + 12.5) / 1e6)
        self.assertAlmostEqual(burn.cost_of(large, "catalog-model", prices), (40 + 60 + 80 + 25) / 1e6)
        self.assertEqual(prices["fixture-model"]["in"], 2)

    def test_official_fable_price_prices_catalog_lagging_rows_while_unpriced_models_stay_unknown(self):
        every_token = {"input_tokens": 1_000_000, "output_tokens": 1_000_000,
                       "cache_read_input_tokens": 1_000_000, "cache_creation_input_tokens": 1_000_000}
        write_rows(self.path, [
            {"type": "assistant", "timestamp": burn.iso(NOW - 3600), "uuid": identity,
             "message": {"id": identity, "model": model, "usage": usage, "content": []}}
            for identity, model, usage in (("fable", "claude-fable-5-2", every_token),
                                           ("flash", "deepseek-flash", {"input_tokens": 10, "output_tokens": 2}))])
        costs = {row["model"]: row["listCostUsd"] for row in self.report()["rows"]}
        self.assertAlmostEqual(costs["claude-fable-5-2"], 8 + 40 + 0.2 + 10)
        self.assertIsNone(costs["deepseek-flash"])
        self.assertEqual(burn.list_prices(self.home)["claude-fable-5-2"], burn.OFFICIAL_PRICES["claude-fable-5-2"])

    def test_opencode_provider_export_keeps_only_daily_counters_and_hashed_account_labels(self):
        text = ("day,user_type,user_id,user_name,provider,model,requests,input_tokens,output_tokens,cache_read_tokens,cache_write_5m_tokens,cache_write_1h_tokens,cost_usd\n"
                "2026-11-25,service_account,private-account,private-name,opencode-go,fixture-model,2,10,3,1000,5,0,0.125\n")
        items = burn.opencode_export(text, burn.list_prices(self.home))
        item = items[0]
        self.assertEqual(item["row"]["hour"], "2026-11-25T00:00:00Z")
        self.assertEqual(item["periodEndsAt"], "2026-11-26T00:00:00Z")
        self.assertEqual(item["row"]["cacheRead"], 1000)
        self.assertEqual(item["billedCostUsd"], 0.125)
        self.assertNotIn("private-account", json.dumps(items))
        self.assertNotIn("private-name", json.dumps(items))
        report = dict(self.report(), keyUsage=items)
        self.assertEqual(burn.validate(report), [])
        self.assertEqual(report["rows"], [])
        with self.assertRaises(ValueError):
            burn.opencode_export(text.replace(",10,3,", ",-10,3,"), {})

    def test_provider_refresh_replaces_overlapping_days_and_preserves_stale_history_on_failure(self):
        item = burn.key_usage_row("2026-11-25", "opencode", "fixture key", "fixture-model", 1, None, 0.5, {}, "key")
        with patch.object(burn, "read_paid_source", return_value=([item], "2026-10-27T00:00:00Z")):
            rows, _ = burn.paid_usage(self.home, NOW)
            self.assertEqual(len(rows), 3)
            rows, _ = burn.paid_usage(self.home, NOW)
            self.assertEqual(len(rows), 3)
        with patch.object(burn, "read_paid_source", side_effect=OSError("private credential")):
            stale, notes = burn.paid_usage(self.home, NOW + 3600)
        self.assertEqual(rows, stale)
        self.assertTrue(all("last successful read" in note for note in notes[:3]))
        self.assertNotIn("private credential", json.dumps(notes))

    def test_paid_api_calls_use_the_named_credentials_and_do_not_export_response_text(self):
        with patch.object(burn, "provider_key", return_value="private-key") as key, patch.object(burn, "http_json", return_value={"data": [
            {"date": "2026-11-25", "model": "fixture-model", "requests": 2, "usage": 0.25, "prompt": "private prompt"}]}):
            rows, _ = burn.read_paid_source("openrouter", self.home, NOW, {})
        key.assert_called_once_with(self.home, "openrouter-credit")
        self.assertEqual(rows[0]["billedCostUsd"], 0.25)
        self.assertFalse(rows[0]["row"]["tokensKnown"])
        self.assertNotIn("private", json.dumps(rows))
        with patch.object(burn, "provider_key", return_value="private-key") as key, patch.object(burn, "http_json", return_value={"results": [
            {"model": "fixture-model", "request_count": 3, "total_cost": 0.5}]}):
            rows, _ = burn.read_paid_source("vercel", self.home, NOW, {})
        key.assert_called_once_with(self.home, "vercel-ai-gateway")
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["row"]["account"] == "Vercel AI Gateway Token Pass key" for row in rows))

    def test_bad_rows_are_reported_without_copying_source_content(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"secret":invalid}\n')
        report = self.report()
        self.assertIn("invalid JSONL rows: 1", report["notes"])
        self.assertNotIn("secret", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
