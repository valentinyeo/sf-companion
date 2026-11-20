#!/usr/bin/env python3
import io
import tempfile
import unittest
import urllib.request
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


class DownloadTest(unittest.TestCase):
    def request(self):
        return urllib.request.Request(
            f"{cache.API}/repos/valentinyeo/sf-companion/actions/artifacts/7/zip",
            headers=cache.headers("secret"),
        )

    def test_the_storage_redirect_drops_the_bearer_token(self):
        following = cache.StorageRedirect().redirect_request(
            self.request(),
            None,
            302,
            "Found",
            {},
            "https://blob.example/archive?sig=1",
        )
        self.assertIsNotNone(following)
        self.assertNotIn("Authorization", following.headers)

    def test_a_redirect_inside_the_api_keeps_the_bearer_token(self):
        following = cache.StorageRedirect().redirect_request(
            self.request(),
            None,
            302,
            "Found",
            {},
            f"{cache.API}/repositories/1/actions/artifacts/7/zip",
        )
        self.assertEqual(following.headers.get("Authorization"), "Bearer secret")


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

    def test_the_output_names_the_artifact_to_upload_on_a_miss(self):
        self.restore([])
        self.assertIn(f"name={NAME}", self.output.read_text(encoding="utf-8"))

    def test_an_expired_entry_and_a_stray_entry_still_end_the_search(self):
        result = self.restore(
            [
                artifact(5, NAME, "2026-11-19T20:00:00Z", expired=True),
                artifact(6, f"base-proof-v1-{BASE}-ffffffffffffffff", "2026-11-19T20:00:00Z"),
            ]
        )
        self.assertFalse(result["hit"])
        self.assertEqual(self.served, [])
        self.assertIn("hit=false", self.output.read_text(encoding="utf-8"))

    def test_a_full_first_page_asks_for_the_next_one(self):
        pages = {
            1: [artifact(1, NAME, "2026-11-18T20:00:00Z") for _ in range(2)],
            2: [artifact(2, NAME, "2026-11-19T20:00:00Z")],
        }
        asked = []

        def fetch(url, token):
            page = int(url.rsplit("page=", 1)[1])
            asked.append(page)
            return {"total_count": 3, "artifacts": pages.get(page, [])}

        found = cache.saved_artifacts(
            "valentinyeo/sf-companion", NAME, "token", fetch, per_page=2
        )
        self.assertEqual(asked, [1, 2])
        self.assertEqual([artifact["id"] for artifact in found], [1, 1, 2])

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
