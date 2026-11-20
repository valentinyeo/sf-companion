#!/usr/bin/env python3
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

import base_proof_cache as cache

BASE = "ae510e099a658d37ccc968a334a219a9618b1711"
DIGEST = "e8d6a54e61146eb2"
NAME = f"base-proof-v1-{BASE}-{DIGEST}"


def archive(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, text in entries.items():
            bundle.writestr(name, text)
    return buffer.getvalue()


PROOF = archive({"proof-base/result.json": '{"status":"passed"}\n'})


def artifact(identifier, name, created_at, expired=False):
    return {
        "id": identifier,
        "name": name,
        "expired": expired,
        "created_at": created_at,
        "workflow_run": {"id": identifier * 10, "html_url": f"https://run/{identifier}"},
    }


class NameTest(unittest.TestCase):
    def test_the_name_carries_the_base_and_the_journey_digest(self):
        self.assertEqual(cache.artifact_name(BASE, DIGEST), NAME)


class RestoreTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.proof = self.root / "proof-base"
        self.output = self.root / "output.txt"
        self.served = []

    def fetch_json(self, listings):
        def fetch(url, token):
            return {"total_count": len(listings), "artifacts": listings}

        return fetch

    def fetch_zip(self, url, token):
        self.served.append(url)
        return PROOF

    def restore(self, listings, fetch_zip=None, fetch_json=None):
        return cache.restore(
            repo="valentinyeo/sf-companion",
            base_sha=BASE,
            digest=DIGEST,
            proof_dir=self.proof,
            token="token",
            output=self.output,
            fetch_json=fetch_json or self.fetch_json(listings),
            fetch_zip=fetch_zip or self.fetch_zip,
        )

    def test_a_saved_proof_is_restored_and_reported_as_a_hit(self):
        result = self.restore([artifact(7, NAME, "2026-11-19T20:00:00Z")])
        self.assertTrue(result["hit"])
        self.assertEqual(result["run"], "70")
        self.assertEqual(
            (self.proof / "result.json").read_text(encoding="utf-8"),
            '{"status":"passed"}\n',
        )
        self.assertIn("hit=true", self.output.read_text(encoding="utf-8"))

    def test_the_newest_unexpired_proof_wins(self):
        result = self.restore(
            [
                artifact(1, NAME, "2026-11-18T20:00:00Z"),
                artifact(2, NAME, "2026-11-19T20:00:00Z"),
                artifact(3, NAME, "2026-11-20T20:00:00Z", expired=True),
            ]
        )
        self.assertEqual(result["run"], "20")
        self.assertEqual(self.served, [f"https://api.github.com/repos/valentinyeo/sf-companion/actions/artifacts/2/zip"])

    def test_another_artifact_never_matches(self):
        result = self.restore(
            [artifact(4, f"base-proof-v1-{BASE}-ffffffffffffffff", "2026-11-19T20:00:00Z")]
        )
        self.assertFalse(result["hit"])
        self.assertEqual(self.served, [])
        self.assertIn("hit=false", self.output.read_text(encoding="utf-8"))
        self.assertIn("miss", result["message"])

    def test_an_archive_without_a_result_file_is_a_miss(self):
        result = self.restore(
            [artifact(7, NAME, "2026-11-19T20:00:00Z")],
            fetch_zip=lambda url, token: archive({"proof-base/install.log": "log\n"}),
        )
        self.assertFalse(result["hit"])
        self.assertIn("result.json", result["message"])

    def test_a_proof_that_sits_at_the_root_of_the_archive_is_restored(self):
        result = self.restore(
            [artifact(7, NAME, "2026-11-19T20:00:00Z")],
            fetch_zip=lambda url, token: archive({"result.json": "{}\n"}),
        )
        self.assertTrue(result["hit"])
        self.assertTrue((self.proof / "result.json").is_file())

    def test_a_failing_api_call_is_a_miss_with_a_reason(self):
        def broken(url, token):
            raise OSError("network down")

        result = self.restore([], fetch_json=broken)
        self.assertFalse(result["hit"])
        self.assertIn("network down", result["message"])


if __name__ == "__main__":
    unittest.main()
