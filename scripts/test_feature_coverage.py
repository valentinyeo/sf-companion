#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

import feature_coverage as coverage

ROUTE = """export const SiteRoute = Route.defineRouteUnion({
  Entry: { section: Section, slug: Schema.String },
  Factory: {},
  Home: {},
  List: { section: Section },
  NotFound: { path: Schema.String },
});
"""

ITEM = 'export const Section = Schema.Literals(["explorations", "reports"]);\n'

FACTORY = """  h.h2([], ["Usage"]),
  h.h2([], ["Output and waste"]),
  h.h2([], ["PRs shipped vs plan burn"]),
  h.p([], ["No factory numbers yet."]),
"""

SHARE = """export const serveItem = (
export const uploadItem = (
export const deleteItem = (
"""

WEBSITE = 'export class Website extends Cloudflare.Website.Foldkit<Website>()("Website", {}\n'
VERIFIER = 'run: python3 scripts/pick_verifier.py --body-file "$RECORDS/pr-body.txt"\n'

FEATURES = {
    "home.md": "route:Home",
    "lists.md": "route:List, section:explorations",
    "reports.md": "section:reports",
    "items.md": "route:Entry, share:serve",
    "factory.md": "route:Factory",
    "usage.md": "factory:usage",
    "kpis.md": "factory:output-and-waste",
    "shipping.md": "factory:prs-shipped-vs-plan-burn",
    "empty.md": "factory:no-feed, route:NotFound",
    "access.md": "deploy:website",
    "share.md": "share:upload, share:delete",
    "verifier.md": "ci:verifier-selection",
}

TOTAL = 16


class CoverageTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.features = self.root / coverage.FEATURES_DIR
        self.features.mkdir(parents=True)
        self.write_source(coverage.ROUTE_FILE, ROUTE)
        self.write_source(coverage.ITEM_FILE, ITEM)
        self.write_source(coverage.FACTORY_FILE, FACTORY)
        self.write_source(coverage.SHARE_FILE, SHARE)
        self.write_source(coverage.WEBSITE_FILE, WEBSITE)
        self.write_source(coverage.VERIFIER_FILE, VERIFIER)
        for name, covers in FEATURES.items():
            self.write_feature(name, covers)
        self.write_readme(coverage.coverage_line(TOTAL, TOTAL, len(FEATURES)))

    def write_source(self, relative, source):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    def write_feature(self, name, covers):
        body = f"# {name}\n\nCovers: {covers}\n\n## Sub-features\n\n- `{name.removesuffix('.md')}` does the thing.\n"
        (self.features / name).write_text(body, encoding="utf-8")

    def write_readme(self, line):
        (self.features / coverage.README).write_text(
            f"{line}\n\n# Map\n", encoding="utf-8"
        )

    def test_clean_map_passes(self):
        self.assertEqual(coverage.check(self.root), [])

    def test_readme_line_is_generated_from_source(self):
        self.assertEqual(
            coverage.coverage_line(TOTAL, TOTAL, len(FEATURES)),
            "Coverage: 16 of 16 features across 12 files.",
        )

    def test_feature_without_a_file_is_rejected(self):
        self.write_feature("reports.md", "section:explorations")
        self.write_feature("lists.md", "route:List")
        errors = coverage.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("section:reports", errors[0])
        self.assertIn("no feature file covers it", errors[0])

    def test_stale_coverage_count_is_rejected(self):
        self.write_readme(coverage.coverage_line(14, 14, 11))
        errors = coverage.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("Coverage: 16 of 16 features across 12 files.", errors[0])
        self.assertIn("--write", errors[0])

    def test_write_refreshes_the_coverage_count(self):
        self.write_readme(coverage.coverage_line(1, 1, 1))
        errors, covered, total, files = coverage.evaluate(self.root)
        self.assertEqual(errors, [])
        coverage.write_coverage_line(self.root, covered, total, files)
        self.assertEqual(coverage.check(self.root), [])

    def test_feature_the_source_lost_is_rejected(self):
        self.write_feature("usage.md", "factory:usage, factory:tickets")
        errors = coverage.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("factory:tickets", errors[0])
        self.assertIn("source no longer has", errors[0])

    def test_feature_claimed_twice_is_rejected(self):
        self.write_feature("items.md", "route:Entry, share:serve, section:reports")
        errors = coverage.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("section:reports", errors[0])
        self.assertIn("covered by", errors[0])

    def test_new_factory_section_needs_a_feature_file(self):
        self.write_source(
            coverage.FACTORY_FILE, FACTORY + '  h.h2([], ["Tickets"]),\n'
        )
        errors = coverage.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("factory:tickets", errors[0])

    def test_verifier_without_a_feature_file_is_rejected(self):
        (self.features / "verifier.md").unlink()
        errors = coverage.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("ci:verifier-selection", errors[0])
        self.assertIn("no feature file covers it", errors[0])

    def test_removed_verifier_makes_its_feature_stale(self):
        self.write_source(coverage.VERIFIER_FILE, "jobs: {}\n")
        errors = coverage.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("ci:verifier-selection", errors[0])
        self.assertIn("source no longer has", errors[0])

    def test_feature_file_without_a_covers_line_is_rejected(self):
        (self.features / "stray.md").write_text("# Stray\n", encoding="utf-8")
        errors = coverage.check(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("stray.md", errors[0])
        self.assertIn("Covers:", errors[0])

    def test_missing_source_file_is_rejected(self):
        (self.root / coverage.SHARE_FILE).unlink()
        errors = coverage.check(self.root)
        self.assertIn("apps/web/src/content/share.ts", errors[0])
        self.assertEqual(len(errors), 4)
        self.assertIn("share:serve", " ".join(errors))


class RealRepoTest(unittest.TestCase):
    def test_this_repository_passes(self):
        root = Path(__file__).resolve().parent.parent
        self.assertEqual(coverage.check(root), [])


if __name__ == "__main__":
    unittest.main()
