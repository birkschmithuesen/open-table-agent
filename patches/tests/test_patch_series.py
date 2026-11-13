"""Static checks of the AGPL patch series (spec §5, MUSTs P1-P4). No network, no checkout."""
import os, re, subprocess, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATCH_DIR = ROOT / "patches"
UPSTREAM = os.environ.get("OTA_UPSTREAM_GIT_DIR", "/mnt/HC_Volume_106183673/projekte/teable-fork/.git")
ALLOWED = {
    "apps/nestjs-backend/src/features/base-sql-executor/base-sql-query.controller.ts",
    "apps/nestjs-backend/src/features/base-sql-executor/base-sql-executor.module.ts",
    "apps/nestjs-backend/src/features/base/base.module.ts",
    "apps/nestjs-backend/test/admin/table-route-ledger.ts",
}

def series():
    files = sorted(PATCH_DIR.glob("[0-9][0-9][0-9][0-9]-*.patch"))
    if not files:
        raise AssertionError("no patches/NNNN-*.patch found")
    return files

class PatchSeries(unittest.TestCase):
    def test_base_is_a_full_sha(self):
        self.assertRegex((PATCH_DIR / "BASE").read_text().strip(), r"^[0-9a-f]{40}$")

    def test_touches_only_allowlisted_paths(self):
        touched = set()
        for p in series():
            touched |= set(re.findall(r"^diff --git a/(\S+) b/", p.read_text(), re.M))
        self.assertEqual(touched - ALLOWED, set())

    def test_route_permission(self):
        text = (PATCH_DIR / "0001-sql-query-route.patch").read_text()
        self.assertIn("+  @Post(':baseId/sql-query')", text)
        self.assertIn("+  @Permissions('base|query_data')", text)
        self.assertRegex(text, r"(?m)^-\s*'POST /api/base/:baseId/sql-query': 'EE',$")

    def test_readme_states_agpl(self):
        self.assertIn("AGPL-3.0", (PATCH_DIR / "README.md").read_text())

    def test_applies_to_base(self):
        base = (PATCH_DIR / "BASE").read_text().strip()
        if not Path(UPSTREAM).exists():
            self.fail(f"upstream git dir {UPSTREAM} missing; set OTA_UPSTREAM_GIT_DIR")
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "GIT_DIR": UPSTREAM, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
            r = subprocess.run(["git", "read-tree", base], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"BASE {base} not in {UPSTREAM}: {r.stderr}")
            for p in series():
                r = subprocess.run(["git", "apply", "--cached", "--check", "-v", str(p)], env=env, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, f"{p.name} does not apply to {base}:\n{r.stderr}")
                subprocess.run(["git", "apply", "--cached", str(p)], env=env, check=True, capture_output=True)

if __name__ == "__main__":
    unittest.main()
