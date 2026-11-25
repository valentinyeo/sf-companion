#!/usr/bin/env python3
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import check_fixture_scale as scale

README = ".claude/skills/verify-sf-companion/features/README.md"
FIXTURE = ".claude/skills/verify-sf-companion/fixture.json"
HUB = ".claude/skills/verify-sf-companion/fixture-hub/index.json"
CHATS = ".claude/skills/verify-sf-companion/fixture-chats.json"

HEADER = "| Measure | Production | Fixture |\n| --- | --- | --- |\n"
DATE = "Production counts were measured on 2026-11-19.\n"
TITLE = "# Companion verification map\n\n"


def feed(cards=7, burn=7, tiles=7, notes=2, days=30, omissions=2, ship_notes=1):
    return {
        "usage": {"cards": [{}] * cards, "burn": {str(index): {} for index in range(burn)}},
        "kpis": {
            "tiles": [{}] * tiles,
            "notes": ["note"] * notes,
            "shipping": {
                "days": [{}] * days,
                "omissions": [{}] * omissions,
                "notes": ["note"] * ship_notes,
            },
        },
    }


def hub(reports=10, explorations=10):
    return [{"key": f"r/{index}.html"} for index in range(reports)] + [
        {"key": f"x/{index}.html"} for index in range(explorations)
    ]


def chats(count=73):
    return {"chats": [{"name": f"Chat {index}"} for index in range(count)]}


def rows(**overrides):
    counts = {
        "Hub reports": (9, 10),
        "Hub explorations": (1, 10),
        "Usage cards": (7, 7),
        "Usage burn windows": (7, 7),
        "KPI tiles": (4, 7),
        "KPI notes": (8, 8),
        "Shipping days": (30, 30),
        "Shipping omissions": (2, 2),
        "Shipping notes": (5, 5),
        "Chats": (73, 73),
    }
    counts.update(overrides)
    return "".join(
        f"| {name} | {production} | {fixture} |\n"
        for name, (production, fixture) in counts.items()
    )


class Repo:
    def __init__(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.write(FIXTURE, json.dumps(feed(notes=8, ship_notes=5)))
        self.write(HUB, json.dumps(hub()))
        self.write(CHATS, json.dumps(chats()))

    def scale(self, table=None, date=DATE):
        return f"## Scale\n\n{date}\n{table or HEADER + rows()}"

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


class FixtureScaleTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.directory.cleanup)

    def check(self, section):
        self.repo.write(README, TITLE + section)
        return scale.check(self.repo.root)

    def test_a_fixture_at_production_scale_passes(self):
        self.assertEqual(self.check(self.repo.scale()), [])

    def test_a_fixture_below_production_fails(self):
        self.repo.write(FIXTURE, json.dumps(feed(notes=2, ship_notes=5)))
        errors = self.check(self.repo.scale(HEADER + rows(**{"KPI notes": (8, 2)})))
        self.assertTrue(any("so every journey starts below the size users meet" in error for error in errors), errors)
        self.assertTrue(any("grow the fixture to at least 8" in error for error in errors), errors)

    def test_a_table_that_drifts_from_the_fixture_fails(self):
        errors = self.check(self.repo.scale(HEADER + rows(**{"KPI notes": (8, 7)})))
        self.assertTrue(any("records a fixture count of 7" in error for error in errors), errors)

    def test_a_missing_scale_section_fails(self):
        errors = self.check("Nothing here.\n")
        self.assertTrue(any('no "## Scale" section' in error for error in errors), errors)

    def test_an_undated_measurement_fails(self):
        errors = self.check(self.repo.scale(date=""))
        self.assertTrue(any("never says when" in error for error in errors), errors)

    def test_a_missing_row_fails(self):
        table = HEADER + "".join(
            line for line in rows().splitlines(keepends=True) if "KPI tiles" not in line
        )
        errors = self.check(self.repo.scale(table=table))
        self.assertTrue(any("no KPI tiles row" in error for error in errors), errors)

    def test_an_unknown_measure_fails(self):
        errors = self.check(self.repo.scale(HEADER + rows() + "| Latency | 3 | 3 |\n"))
        self.assertTrue(any('names "Latency"' in error for error in errors), errors)

    def test_a_word_instead_of_a_count_fails(self):
        errors = self.check(self.repo.scale(HEADER + rows(**{"KPI tiles": ("four", 7)})))
        self.assertTrue(any("whole number" in error for error in errors), errors)

    def test_measure_prints_the_counts_it_can_read(self):
        elsewhere = self.repo.root / "elsewhere"
        elsewhere.mkdir(parents=True, exist_ok=True)
        feed_path = elsewhere / "factory.json"
        feed_path.write_text(json.dumps(feed(notes=3)), encoding="utf-8")
        hub_path = elsewhere / "index.json"
        hub_path.write_text(json.dumps(hub(reports=4)), encoding="utf-8")
        chats_path = elsewhere / "chats.json"
        chats_path.write_text(json.dumps(chats(count=4)), encoding="utf-8")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            scale.measure(feed_path, hub_path, chats_path)
        printed = buffer.getvalue().splitlines()
        self.assertIn("KPI notes: 3", printed)
        self.assertIn("Hub reports: 4", printed)
        self.assertIn("Hub explorations: 10", printed)
        self.assertIn("Chats: 4", printed)

    def test_measure_says_what_it_could_not_read(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            scale.measure(None, None, None)
        self.assertIn("Hub reports: not measured, no hub index given", buffer.getvalue())
        self.assertIn("Chats: not measured, no chats snapshot given", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
