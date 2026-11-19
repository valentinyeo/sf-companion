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


exact_pins = load("check_exact_pins", ROOT / "scripts/check-exact-pins")


def write(root, name, text):
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def manifest(root, version, app_version=None):
    write(
        root,
        "package.json",
        '{"dependencies": {"effect": "%s"}}\n' % version,
    )
    if app_version is not None:
        write(
            root,
            "apps/web/package.json",
            '{"devDependencies": {"vitest": "%s"}}\n' % app_version,
        )


class ExactPinsTest(unittest.TestCase):
    def test_real_manifests_are_exact(self):
        self.assertEqual(exact_pins.check(ROOT), 0)

    def test_exact_versions_pass(self):
        with tempfile.TemporaryDirectory() as root:
            manifest(root, "4.1.4", "5.1.0")
            self.assertEqual(exact_pins.check(root), 0)

    def test_prerelease_pin_passes(self):
        with tempfile.TemporaryDirectory() as root:
            manifest(root, "6.0.0-beta.1", "0.25.0-ts7.1.0-beta")
            self.assertEqual(exact_pins.check(root), 0)

    def test_caret_range_fails(self):
        with tempfile.TemporaryDirectory() as root:
            manifest(root, "^4.1.4")
            self.assertEqual(exact_pins.check(root), 1)

    def test_latest_tag_fails(self):
        with tempfile.TemporaryDirectory() as root:
            manifest(root, "latest", "5.1.0")
            self.assertEqual(exact_pins.check(root), 1)

    def test_workspace_protocol_passes(self):
        with tempfile.TemporaryDirectory() as root:
            manifest(root, "workspace:^")
            self.assertEqual(exact_pins.check(root), 0)


if __name__ == "__main__":
    unittest.main()
