import json
import tempfile
import unittest
from pathlib import Path

from scripts.tests.fixtures import make_upstream, make_patch, run_sync


class SyncUpstream(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.upstream, self.sha = make_upstream(self.tmp / "up")
        self.patches = self.tmp / "patches"
        make_patch(self.upstream, self.patches)

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_apply_writes_lock(self):
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"UPSTREAM {self.sha}", r.stdout)
        lock = json.loads((self.tmp / "upstream.lock.json").read_text())
        self.assertEqual(lock["schema"], 1)
        self.assertEqual(lock["upstream"], {"url": str(self.upstream), "ref": "refs/heads/develop", "sha": self.sha})
        self.assertEqual([p["file"] for p in lock["patches"]], ["0001-demo.patch"])
        self.assertRegex(lock["patches"][0]["sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(lock["patched_commit"], r"^[0-9a-f]{40}$")
        self.assertTrue(lock["image"]["tag"].startswith(f"localhost/ota-teable:{self.sha[:12]}-"))
        self.assertIn("BUILD podman build -f dockers/teable/Dockerfile", r.stdout)
        wt = self.tmp / ".work" / f"teable-{self.sha[:12]}"
        self.assertTrue((wt / "app" / "new.ts").exists())


if __name__ == "__main__":
    unittest.main()
