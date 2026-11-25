import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
COLLECTOR = HERE / "collect-chats.py"

spec = importlib.util.spec_from_file_location("collect_chats", COLLECTOR)
assert spec is not None and spec.loader is not None
chats = importlib.util.module_from_spec(spec)
sys.modules["collect_chats"] = chats
spec.loader.exec_module(chats)

FIELDS = ["effort", "harness", "model", "name", "project", "server"]


class RedactionTests(unittest.TestCase):
    def test_an_email_never_reaches_the_output(self):
        self.assertEqual(chats.clean("Ops valentin@example.com"), "Ops [redacted]")

    def test_a_token_like_run_never_reaches_the_output(self):
        self.assertEqual(chats.clean("Deploy sk-live-9f2b7c41d8e5a6b3c0d1e2f3a4b5c6d7"),
                         "Deploy [redacted]")

    def test_a_host_name_never_reaches_the_output(self):
        self.assertEqual(chats.clean("Runner box-42.corp.internal"), "Runner [redacted]")

    def test_an_ip_address_never_reaches_the_output(self):
        self.assertEqual(chats.clean("worker 10.0.4.19"), "worker [redacted]")

    def test_a_session_id_name_becomes_an_unnamed_chat(self):
        self.assertEqual(chats.clean("live-4843c43aa96183ad84f63f30dccd454b"), chats.UNNAMED_CHAT)

    def test_a_model_name_survives(self):
        self.assertEqual(chats.clean("gpt-6.1-sol"), "gpt-6.1-sol")
        self.assertEqual(chats.clean("deepseek-v4.1-flash"), "deepseek-v4.1-flash")

    def test_a_missing_field_reads_unknown(self):
        self.assertEqual(chats.clean(None), "unknown")
        self.assertEqual(chats.project_of(None), "unknown")

    def test_a_long_field_is_cut(self):
        self.assertLessEqual(len(chats.clean("a " * 200)), chats.FIELD_LIMIT)

    def test_control_characters_are_dropped(self):
        self.assertEqual(chats.clean("HT\x00 Bugs\x07"), "HT Bugs")


class ProjectTests(unittest.TestCase):
    def test_a_home_path_never_reaches_the_output(self):
        self.assertEqual(chats.project_of("/home/valentin/projects/vstack"), "vstack")
        self.assertEqual(chats.project_of("~/projects/hypertask"), "hypertask")
        self.assertEqual(chats.project_of(str(Path.home())), "home")

    def test_a_trailing_slash_is_ignored(self):
        self.assertEqual(chats.project_of("/home/valentin/projects/vstack/"), "vstack")


class RecordTests(unittest.TestCase):
    def test_a_record_carries_only_the_six_published_fields(self):
        row = chats.chat("HT Bugs", "Contabo", "~/projects/hypertask", "codex", "gpt-6.1-sol", "medium")
        self.assertEqual(sorted(row), FIELDS)

    def test_an_extra_input_field_is_dropped(self):
        record = {"name": "HT Bugs", "cwd": "/home/valentin/projects/hypertask", "harness": "codex",
                  "model": "gpt-6.1-sol", "effort": "medium", "email": "valentin@example.com",
                  "token": "sk-live-9f2b7c41d8e5a6b3c0d1e2f3a4b5c6d7"}
        row = chats.chat(record["name"], "Contabo", record["cwd"], record["harness"],
                         record["model"], record["effort"])
        self.assertEqual(sorted(row), FIELDS)
        body = json.dumps(row)
        self.assertNotIn("example.com", body)
        self.assertNotIn("sk-live", body)

    def test_an_unknown_harness_is_kept_as_unknown(self):
        self.assertEqual(chats.chat("x", "Contabo", "", "hax", "unknown", "unknown")["harness"], "unknown")

    def test_a_known_harness_keeps_its_friendly_name(self):
        for harness in ("claude", "codex", "pi"):
            self.assertEqual(chats.chat("x", "Contabo", "", harness, "m", "e")["harness"], harness)


class SnapshotTests(unittest.TestCase):
    def test_a_server_that_did_not_answer_is_not_connected(self):
        body = chats.snapshot({"Contabo": [chats.chat("HT Bugs", "Contabo", "~/p/hypertask", "codex", "gpt-6.1-sol", "medium")],
                               "inne Hetzner": None}, {"Contabo": "2026-11-25T18:00:00Z"})
        states = {line["server"]: line for line in body["servers"]}
        self.assertEqual(states["Contabo"]["state"], "live")
        self.assertEqual(states["inne Hetzner"]["state"], "not-connected")
        self.assertIsNone(states["inne Hetzner"]["collectedAt"])
        self.assertEqual(len(body["chats"]), 1)

    def test_rows_are_ordered_by_server_then_name(self):
        body = chats.snapshot({
            "Contabo": [chats.chat("Beta", "Contabo", "", "claude", "m", "e"),
                        chats.chat("Alpha", "Contabo", "", "claude", "m", "e")],
            "inne Hetzner": [chats.chat("Zulu", "inne Hetzner", "", "claude", "m", "e")],
        }, {"Contabo": "2026-11-25T18:00:00Z", "inne Hetzner": "2026-11-25T18:00:00Z"})
        self.assertEqual([row["name"] for row in body["chats"]], ["Alpha", "Beta", "Zulu"])


if __name__ == "__main__":
    unittest.main()
