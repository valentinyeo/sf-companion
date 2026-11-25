import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "sf-companion-feed"


class FeedScriptTests(unittest.TestCase):
    def setUp(self):
        self.text = SCRIPT.read_text()

    def at(self, needle):
        found = self.text.find(needle)
        self.assertNotEqual(found, -1, f"{SCRIPT.name} never mentions {needle!r}")
        return found

    def test_fast_forwards_before_the_export(self):
        branch = self.at('git -C "$REPO" rev-parse --abbrev-ref HEAD')
        fetch = self.at('git -C "$REPO" fetch -q origin main')
        merge = self.at("merge --ff-only -q origin/main")
        export = self.at("export-factory-feed.py")
        self.assertLess(branch, fetch)
        self.assertLess(fetch, merge)
        self.assertLess(merge, export)

    def test_refuses_a_checkout_that_cannot_fast_forward(self):
        guard = self.at('[ "$branch" = "main" ]')
        refusal = self.at('cannot fast-forward to origin/main"; exit 1; }')
        self.assertLess(guard, refusal)


if __name__ == "__main__":
    unittest.main()
