import importlib.util
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(name, path):
    loader = SourceFileLoader(name, str(path))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    return module


rule_table = load("check_rule_table", ROOT / "scripts/check-rule-table")

EMERGENCY = """## Emergency: revert first

A bad change is reverted before anyone diagnoses it.

1. Run `git revert <sha>` and open a normal pull request.
2. Merge through the same required check as everything else, so the fix follows the normal verified path.
3. No skip lane: no direct push to `main`.

"""

OXLINT = """export default {
  jsPlugins: [{ name: "demo", specifier: "./scripts/demo-plugin.ts" }],
  rules: { "demo/no-thing": "error" },
};
"""

PLUGIN = """export default {
  rules: { "no-thing": demoRule },
};
"""

PACKAGE = """{
  "scripts": {
    "check": "pnpm typecheck",
    "test": "node --test scripts/demo.test.mjs"
  }
}
"""

CI = """jobs:
  checks:
    steps:
      - name: Demo step
        run: scripts/demo-check
"""

TABLE_HEADER = """## Rule table

| Rule | Enforced by | Where it runs |
| --- | --- | --- |
"""

TABLE_ROWS = """| Lint rules fail a run | `lint:demo/no-thing` | CI |
| Scripts are gates | `script:scripts/demo-check` | CI |
| The gate is a script | `pnpm:check`, `pnpm:test` | Our CI |
| Tests have a runner | `test:scripts/demo.test.mjs` | pnpm test |
| Steps exist | `ci:Demo step` | CI |
"""

TABLE = TABLE_HEADER + TABLE_ROWS + "\n"


def write(root, name, text, executable=False):
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755 if executable else 0o644)
    return path


def fixture(root, table=TABLE, emergency=EMERGENCY):
    write(root, "AGENTS.md", table + emergency)
    write(root, "oxlint.config.ts", OXLINT)
    write(root, "scripts/demo-plugin.ts", PLUGIN)
    write(root, "scripts/demo-check", "#!/usr/bin/env python3\nprint('ok')\n", True)
    write(root, "scripts/demo.test.mjs", "export const demo = true;\n")
    write(root, "package.json", PACKAGE)
    write(root, ".github/workflows/ci.yml", CI)


class RuleTableTest(unittest.TestCase):
    def test_real_table_resolves_every_check(self):
        self.assertEqual(rule_table.check(ROOT), [])

    def test_fixture_table_passes(self):
        with tempfile.TemporaryDirectory() as root:
            fixture(root)
            self.assertEqual(rule_table.check(root), [])

    def test_missing_lint_rule_fails(self):
        table = TABLE_HEADER + TABLE_ROWS + "| A rule with no lint rule | `lint:demo/no-such-rule` | CI |\n\n"
        with tempfile.TemporaryDirectory() as root:
            fixture(root, table=table)
            errors = rule_table.check(root)

        self.assertTrue(any("no-such-rule" in error for error in errors), errors)

    def test_off_lint_rule_fails(self):
        with tempfile.TemporaryDirectory() as root:
            fixture(root)
            write(root, "oxlint.config.ts", OXLINT.replace('"error"', '"off"'))
            errors = rule_table.check(root)

        self.assertTrue(any("cannot fail" in error for error in errors), errors)

    def test_missing_script_fails(self):
        table = TABLE_HEADER + TABLE_ROWS + "| A rule with no script | `script:scripts/absent` | CI |\n\n"
        with tempfile.TemporaryDirectory() as root:
            fixture(root, table=table)
            errors = rule_table.check(root)

        self.assertTrue(any("scripts/absent" in error for error in errors), errors)

    def test_missing_ci_step_fails(self):
        table = TABLE_HEADER + TABLE_ROWS + "| A rule with no step | `ci:Absent step` | CI |\n\n"
        with tempfile.TemporaryDirectory() as root:
            fixture(root, table=table)
            errors = rule_table.check(root)

        self.assertTrue(any("Absent step" in error for error in errors), errors)

    def test_missing_pnpm_script_fails(self):
        table = TABLE_HEADER + TABLE_ROWS + "| A rule with no script | `pnpm:absent` | CI |\n\n"
        with tempfile.TemporaryDirectory() as root:
            fixture(root, table=table)
            errors = rule_table.check(root)

        self.assertTrue(any("pnpm absent" in error for error in errors), errors)

    def test_unknown_check_kind_fails(self):
        table = TABLE_HEADER + TABLE_ROWS + "| A rule with a made-up kind | `wish:something` | CI |\n\n"
        with tempfile.TemporaryDirectory() as root:
            fixture(root, table=table)
            errors = rule_table.check(root)

        self.assertTrue(any("wish" in error for error in errors), errors)

    def test_row_without_a_check_fails(self):
        table = TABLE_HEADER + TABLE_ROWS + "| A rule with no check at all | nothing | CI |\n\n"
        with tempfile.TemporaryDirectory() as root:
            fixture(root, table=table)
            errors = rule_table.check(root)

        self.assertTrue(any("names no check" in error for error in errors), errors)

    def test_missing_rule_table_fails(self):
        with tempfile.TemporaryDirectory() as root:
            fixture(root, table="")
            errors = rule_table.check(root)

        self.assertTrue(any("Rule table" in error for error in errors), errors)

    def test_missing_emergency_section_fails(self):
        with tempfile.TemporaryDirectory() as root:
            fixture(root, emergency="")
            errors = rule_table.check(root)

        self.assertTrue(
            any("Emergency: revert first" in error for error in errors), errors
        )

    def test_emergency_section_without_the_ban_fails(self):
        emergency = EMERGENCY.replace(
            "No skip lane: no direct push to `main`.",
            "Use your judgement.",
        )
        with tempfile.TemporaryDirectory() as root:
            fixture(root, emergency=emergency)
            errors = rule_table.check(root)

        self.assertTrue(any("skip lane" in error for error in errors), errors)

    def test_wrong_header_fails(self):
        table = """## Rule table

| Rule | Check | Runs |
| --- | --- | --- |
| Lint rules fail a run | `lint:demo/no-thing` | CI |

"""
        with tempfile.TemporaryDirectory() as root:
            fixture(root, table=table)
            errors = rule_table.check(root)

        self.assertTrue(any("header" in error for error in errors), errors)

    def test_unextended_script_fails(self):
        with tempfile.TemporaryDirectory() as root:
            fixture(root)
            write(root, "scripts/demo-check", "#!/usr/bin/env python3\nprint('ok')\n")
            errors = rule_table.check(root)

        self.assertTrue(any("executable" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
