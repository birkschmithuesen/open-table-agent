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

    def test_broken_context_reports_conflict(self):
        from scripts.tests.fixtures import break_context
        break_context(self.patches / "0001-demo.patch")
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"CONFLICT patch=0001-demo\.patch path=app/module\.ts hunk=@@ -\d+,\d+ \+\d+,\d+ @@")
        self.assertIn(f"UPSTREAM {self.sha}", r.stdout)
        self.assertFalse((self.tmp / "upstream.lock.json").exists())

    def test_ignores_local_branch_with_extra_commit(self):
        import subprocess
        cache = self.tmp / ".work" / "upstream.git"
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches), "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        # plant a local 'develop' in the cache that carries an extra commit (the teable-fork trap)
        wt = self.tmp / "plant"
        subprocess.run(["git", "clone", "-q", str(self.upstream), str(wt)], check=True)
        (wt / "extra.txt").write_text("x")
        subprocess.run(["git", "-C", str(wt), "add", "."], check=True)
        subprocess.run(["git", "-C", str(wt), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "local"], check=True)
        subprocess.run(["git", "-C", str(wt), "push", "-q", str(cache), "HEAD:refs/heads/develop"], check=True)
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches))
        self.assertIn(f"UPSTREAM {self.sha}", r.stdout)

    def test_second_run_is_up_to_date(self):
        a = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches))
        lock1 = (self.tmp / "upstream.lock.json").read_text()
        b = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches))
        self.assertEqual((a.returncode, b.returncode), (0, 0))
        self.assertIn(f"UP-TO-DATE {self.sha}", b.stdout)
        self.assertEqual((self.tmp / "upstream.lock.json").read_text(), lock1)

    def test_up_to_date_false_when_worktree_missing(self):
        import shutil
        a = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches))
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
        wt = self.tmp / ".work" / f"teable-{self.sha[:12]}"
        shutil.rmtree(wt)
        b = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches))
        self.assertEqual(b.returncode, 0, b.stdout + b.stderr)
        self.assertNotIn("UP-TO-DATE", b.stdout)
        self.assertIn("PATCHED", b.stdout)
        self.assertTrue(wt.exists())

    def test_dry_run_leaves_no_trace(self):
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches), "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("DRY-RUN ok", r.stdout)
        self.assertFalse((self.tmp / "upstream.lock.json").exists())
        self.assertEqual([p.name for p in (self.tmp / ".work").iterdir()], ["upstream.git"])

    def test_tag_and_usage_errors(self):
        import subprocess
        subprocess.run(["git", "-C", str(self.upstream), "-c", "tag.gpgsign=false", "tag", "release.test.1"], check=True)
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches), "--tag", "release.test.1", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        (self.tmp / "empty").mkdir()
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.tmp / "empty"), "--dry-run")
        self.assertEqual(r.returncode, 2)
        self.assertIn("sync-upstream: no NNNN-*.patch", r.stderr)
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches), "--ref", "develop", "--tag", "x")
        self.assertEqual(r.returncode, 2)

    def test_build_failure_exit_3(self):
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches), "--build",
                     env_extra={"OTA_PODMAN": "false"})
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertFalse(json.loads((self.tmp / "upstream.lock.json").read_text())["image"]["built"])

    def test_podman_args_pass_through(self):
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches),
                     "--podman-arg=--volume=/x:/ota-prisma:ro", "--podman-arg=--env=A=b")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"(?m)^BUILD podman build -f dockers/teable/Dockerfile -t \S+ --volume=/x:/ota-prisma:ro --env=A=b \S+$")


if __name__ == "__main__":
    unittest.main()
