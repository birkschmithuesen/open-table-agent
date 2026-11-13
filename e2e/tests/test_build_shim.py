"""Hermetic tests for the COPY --link build shim (no containers, no network)."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from e2e import build_shim

FIXTURE = """FROM node:24 AS base
COPY --link package.json ./
COPY --link --chown=node:node src/ /app/src/
COPY --chown=node:node --link conf /etc/conf
COPY --from=builder --link /out /out
ADD --link=true http://x/y /y
COPY plain.txt ./
RUN echo "COPY --link inside a RUN stays"
"""


class BuildShimTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src = self.tmp / "Dockerfile"
        self.src.write_text(FIXTURE)
        self.before = hashlib.sha256(self.src.read_bytes()).hexdigest()

    def test_no_link_flag_in_output(self):
        out = build_shim.render(self.src, self.tmp / "out" / "Containerfile").read_text()
        for line in out.splitlines():
            if line.startswith(("COPY", "ADD")):
                self.assertNotIn("--link", line)

    def test_other_flags_preserved(self):
        out = build_shim.render(self.src, self.tmp / "o").read_text().splitlines()
        self.assertIn("COPY package.json ./", out)
        self.assertIn("COPY --chown=node:node src/ /app/src/", out)
        self.assertIn("COPY --chown=node:node conf /etc/conf", out)
        self.assertIn("COPY --from=builder /out /out", out)
        self.assertIn("ADD http://x/y /y", out)
        self.assertIn("COPY plain.txt ./", out)
        self.assertIn('RUN echo "COPY --link inside a RUN stays"', out)

    def test_source_unchanged(self):
        build_shim.render(self.src, self.tmp / "o")
        self.assertEqual(hashlib.sha256(self.src.read_bytes()).hexdigest(), self.before)
        self.assertEqual(self.src.read_text(), FIXTURE)

    def test_idempotent(self):
        a = build_shim.render(self.src, self.tmp / "a")
        b = build_shim.render(a, self.tmp / "b")
        self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_pnpm_fetch_seeds_store_first(self):
        self.src.write_text(FIXTURE + "WORKDIR /w\nRUN pnpm fetch\nRUN pnpm install --frozen-lockfile\n")
        out = build_shim.render(self.src, self.tmp / "o").read_text().splitlines()
        line = next(l for l in out if "pnpm fetch" in l)
        self.assertTrue(line.startswith(f"RUN pnpm store add {build_shim.XLSX_MOUNT} && "))
        self.assertTrue(line.endswith(" && pnpm fetch"))
        self.assertIn(build_shim.XLSX_URL, line)
        self.assertIn(build_shim.XLSX_INTEGRITY, line)
        self.assertNotIn("RUN pnpm fetch", out)
        self.assertIn("RUN pnpm install --frozen-lockfile", out)

    def test_pnpm_fetch_seed_idempotent_and_source_unchanged(self):
        self.src.write_text(FIXTURE + "RUN pnpm fetch\n")
        before = self.src.read_bytes()
        a = build_shim.render(self.src, self.tmp / "a")
        b = build_shim.render(a, self.tmp / "b")
        self.assertEqual(a.read_bytes(), b.read_bytes())
        self.assertEqual(a.read_text().count("pnpm store add"), 1)
        self.assertEqual(self.src.read_bytes(), before)

    def test_constants_match_vendor_script(self):
        from e2e import vendor_xlsx
        self.assertEqual(build_shim.XLSX_URL, vendor_xlsx.URL)
        self.assertEqual(build_shim.XLSX_INTEGRITY, vendor_xlsx.INTEGRITY)
        self.assertEqual(build_shim.XLSX_MOUNT, "/ota-vendor/" + vendor_xlsx.NAME)

    def test_no_seed_without_pnpm_fetch(self):
        out = build_shim.render(self.src, self.tmp / "o").read_text()
        self.assertNotIn("pnpm store add", out)

    def test_rewrite_args_substitutes_file(self):
        (self.tmp / "ctx").mkdir()
        (self.tmp / "ctx" / "Dockerfile").write_text(FIXTURE)
        argv = ["build", "-f", "Dockerfile", "-t", "x", str(self.tmp / "ctx")]
        new = build_shim.rewrite_args(argv, self.tmp / "work")
        self.assertNotEqual(new[2], "Dockerfile")
        self.assertNotIn("COPY --link", Path(new[2]).read_text().split("RUN")[0])
        self.assertEqual(new[:2] + new[3:], argv[:2] + argv[3:])
        self.assertEqual(build_shim.rewrite_args(["images"], self.tmp), ["images"])


if __name__ == "__main__":
    unittest.main()
