import copy
import unittest
from datetime import datetime, timezone

from factory_shipping import shipping, validate

NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc).timestamp()
MIDNIGHT = NOW - 12 * 3600


def fixture():
    prs = [
        {"repo": "a/one", "number": 1, "mergedAt": "2026-11-15T00:00:00Z"},
        {"repo": "a/two", "number": 1, "mergedAt": "2026-11-15T23:59:59Z"},
        {"repo": "a/two", "number": 2, "mergedAt": "2026-11-16T00:00:00Z"},
        {"repo": "a/two", "number": 3, "mergedAt": "2026-11-17T00:00:00Z"},
        {"repo": "a/two", "number": 4, "mergedAt": None},
    ]
    readings = {"codex": [(MIDNIGHT - 86400 - 60, 10), (MIDNIGHT - 86400 + 60, 14),
                           (MIDNIGHT - 86400 + 120, 14), (MIDNIGHT - 86400 + 180, 1),
                           (MIDNIGHT - 86400 + 240, 3), (MIDNIGHT - 3600, 20)]}
    metric = {"at": NOW - 3600, "cover": MIDNIGHT - 30 * 86400, "days": {"2026-11-15": {"spent": 12}, "2026-11-14": {"spent": 2},
                                          "2026-11-16": {"spent": 3}}}
    return prs, readings, metric


class ShippingTests(unittest.TestCase):
    def test_seeded_chart_dates_burn_and_cost(self):
        prs, readings, metric = fixture()
        result = shipping(NOW, prs + prs[:1], "GitHub fixture", readings, metric)
        self.assertEqual(len(result["days"]), 30)
        self.assertEqual(result["days"][0]["date"], "2026-10-18")
        previous, today = result["days"][-2:]
        self.assertEqual(previous["merges"]["value"], 2)
        self.assertEqual(today["merges"]["value"], 1)
        self.assertEqual(previous["burn"][1]["reading"]["value"], 6)
        self.assertEqual(previous["burn"][1]["reading"]["barPct"], 100)
        self.assertEqual(previous["cost"]["display"], "£12.00")
        self.assertEqual(previous["perPr"]["display"], "£6.00")
        self.assertIn("no denominator", result["days"][-3]["perPr"]["reason"])
        self.assertEqual(today["cost"]["kind"], "missing")
        self.assertEqual(validate(result), [])

    def test_cell_sources_stay_short_and_full_repos_appear_once_in_notes(self):
        prs, readings, metric = fixture()
        source = "GitHub mergedAt · " + ", ".join(f"fleet/repository-{i}" for i in range(18))
        result = shipping(NOW, prs, source, readings, metric)
        for day in result["days"]:
            cells = [day["merges"], day["cost"], day["perPr"]] + [b["reading"] for b in day["burn"]]
            for reading in cells:
                self.assertLessEqual(len(reading["source"]), 80)
                self.assertNotIn("fleet/repository-", reading["source"])
        self.assertEqual(result["notes"].count(source), 1)
        self.assertFalse(any("OpenCode points" in note for note in result["notes"]))

    def test_missing_is_not_zero_and_failure_is_independent(self):
        prs, readings, metric = fixture()
        result = shipping(NOW, None, "GitHub fixture", readings, metric)
        self.assertEqual(result["days"][-2]["merges"]["kind"], "missing")
        self.assertEqual(result["days"][-2]["cost"]["value"], 12)
        self.assertEqual(result["days"][-2]["perPr"]["kind"], "missing")
        result = shipping(NOW, prs, "GitHub fixture", {}, {})
        self.assertEqual(result["days"][-2]["merges"]["value"], 2)
        self.assertEqual(result["days"][-2]["burn"][1]["reading"]["kind"], "missing")
        self.assertEqual(result["days"][-2]["cost"]["kind"], "missing")

    def test_flat_readings_measure_zero_but_isolated_readings_do_not(self):
        for rows, kind in [([(MIDNIGHT + 60, 10)], "missing"),
                           ([(MIDNIGHT + 60, 10), (MIDNIGHT + 120, 10)], "measured")]:
            result = shipping(NOW, [], "GitHub fixture", {"claude": rows}, {})
            reading = result["days"][-1]["burn"][0]["reading"]
            self.assertEqual(reading["kind"], kind)
            if kind == "measured":
                self.assertEqual(reading["value"], 0)

    def test_partial_cost_coverage_and_invalid_prices_stay_missing(self):
        prs, readings, metric = fixture()
        for key, value in [("cover", MIDNIGHT - 1), ("at", MIDNIGHT - 1), ("days", None)]:
            changed = dict(metric, **{key: value})
            result = shipping(NOW, prs, "GitHub fixture", readings, changed)
            self.assertEqual(result["days"][-2]["cost"]["kind"], "missing")
        for value in [None, -1, True, float("inf")]:
            metric["days"]["2026-11-15"]["spent"] = value
            result = shipping(NOW, prs, "GitHub fixture", readings, metric)
            self.assertEqual(result["days"][-2]["cost"]["kind"], "missing")

    def test_contract_rejects_bad_provenance_nonfinite_and_duplicate_dates(self):
        prs, readings, metric = fixture()
        result = shipping(NOW, prs, "GitHub fixture", readings, metric)
        for field, value in [("source", ""), ("window", ""), ("value", float("nan")), ("barPct", 101)]:
            broken = copy.deepcopy(result)
            broken["days"][-1]["merges"][field] = value
            self.assertTrue(validate(broken))
        result["days"][-1]["date"] = result["days"][-2]["date"]
        self.assertTrue(validate(result))

    def test_omitted_plan_keeps_its_own_reason(self):
        prs, readings, metric = fixture()
        result = shipping(NOW, prs, "GitHub fixture", readings, metric)
        reasons = {item["plan"]: item["reason"] for item in result["omissions"]}
        self.assertEqual(set(reasons), {"claude", "grok", "opencode"})
        self.assertEqual(reasons["claude"], "no quota readings on any of the 30 UTC dates.")
        self.assertNotIn("pacing", reasons["claude"])
        self.assertNotIn("Grok", reasons["claude"])
        self.assertNotIn("OpenCode", reasons["claude"])
        self.assertEqual(reasons["grok"], "pacing sampler retired on 2026-11-15.")
        self.assertEqual(reasons["opencode"], "pacing sampler retired on 2026-11-15.")
        self.assertEqual(validate(result), [])
        readings["claude"] = [(MIDNIGHT + 60, 1), (MIDNIGHT + 120, 4)]
        readings["grok"] = [(MIDNIGHT + 60, 1), (MIDNIGHT + 120, 1)]
        present = shipping(NOW, prs, "GitHub fixture", readings, metric)
        self.assertEqual([item["plan"] for item in present["omissions"]], ["opencode"])
        self.assertEqual(present["omissions"][0]["reason"], "pacing sampler retired on 2026-11-15.")
        self.assertNotIn("Claude", present["omissions"][0]["reason"])

    def test_advisor_clock_is_minutes_utc(self):
        prs, readings, metric = fixture()
        metric = dict(metric, at=datetime(2026, 11, 16, 11, 34, 17, 455841, tzinfo=timezone.utc).timestamp())
        result = shipping(NOW, prs, "GitHub fixture", readings, metric)
        source = result["days"][-2]["cost"]["source"]
        self.assertEqual(source, "Advisor attributed £ · 2026-11-16 11:34 UTC")
        for day in result["days"]:
            self.assertNotIn("+00:00", day["cost"]["source"])
            self.assertNotRegex(day["cost"]["source"], r"\d{2}:\d{2}:\d{2}")
            self.assertNotRegex(day["cost"]["source"], r"\.\d{3,}")


if __name__ == "__main__":
    unittest.main()
