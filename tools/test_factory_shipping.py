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


if __name__ == "__main__":
    unittest.main()
