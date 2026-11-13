"""E4: real upstream develop (network: github.com). Not part of `make test`."""
import re, shutil, subprocess, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def sync(*args):
    # absolute --work-dir: scripts/sync-upstream.py mishandles the relative default (worktree lands inside the cache repo)
    return subprocess.run(["python3", str(ROOT / "scripts/sync-upstream.py"), "--work-dir", str(ROOT / ".work"), *args], cwd=ROOT, capture_output=True, text=True)

class RealSync(unittest.TestCase):
    def test_real_develop_applies(self):
        r = sync("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"(?m)^UPSTREAM [0-9a-f]{40}$")

    def test_real_develop_broken_copy_conflicts(self):
        with tempfile.TemporaryDirectory() as d:
            for p in (ROOT / "patches").glob("*.patch"): shutil.copy(p, d)
            p = Path(d) / "0001-sql-query-route.patch"
            text = p.read_text()
            i = text.index("base.module.ts\n")
            j = text.index("\n ", text.index("@@", i))  # first context line of that file's hunk
            p.write_text(text[:j + 1] + " BROKEN" + text[j + 1:])
            r = sync("--dry-run", "--patches", d)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertRegex(r.stdout, r"CONFLICT patch=0001-sql-query-route\.patch path=apps/nestjs-backend/src/features/base/base\.module\.ts")
