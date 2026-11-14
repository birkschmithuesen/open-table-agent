"""Hermetic tests for e2e/node_headers.py (no network)."""
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from e2e import node_headers as nh

H = "ab" * 32
SUMS = f"{'cd' * 32}  node-v24.22.2-linux-x64.tar.xz\n{H}  node-v24.22.2-headers.tar.gz\n"


class NodeHeaders(unittest.TestCase):
    def test_parse_shasums(self):
        self.assertEqual(nh.parse_shasums(SUMS, "node-v24.22.2-headers.tar.gz"), H)

    def test_parse_shasums_missing_or_bad(self):
        with self.assertRaises(SystemExit):
            nh.parse_shasums(SUMS, "node-v1.0.0-headers.tar.gz")
        with self.assertRaises(SystemExit):
            nh.parse_shasums("zz  node-v1-headers.tar.gz\n", "node-v1-headers.tar.gz")

    def test_expected_sha256_pinned_match(self):
        v = "24.22.2"
        good = f"{nh.PINNED_SHA256[v]}  node-v{v}-headers.tar.gz\n"
        self.assertEqual(nh.expected_sha256(v, good), nh.PINNED_SHA256[v])

    def test_expected_sha256_mismatch_exits(self):
        v = "24.22.2"
        with self.assertRaises(SystemExit):
            nh.expected_sha256(v, f"{H}  node-v{v}-headers.tar.gz\n")

    def test_expected_sha256_unpinned_exits(self):
        with self.assertRaises(SystemExit):
            nh.expected_sha256("1.2.3", f"{H}  node-v1.2.3-headers.tar.gz\n")

    def test_podman_args(self):
        a = nh.podman_args(Path("/h"), "24.22.2")
        self.assertEqual(a, ["--volume=/h:/ota-node-headers:ro",
                             "--build-arg=npm_config_nodedir=/ota-node-headers/node-v24.22.2"])

    def test_extract_rejects_escape(self):
        tmp = Path(tempfile.mkdtemp())
        tgz = tmp / "x.tgz"
        with tarfile.open(tgz, "w:gz") as t:
            ti = tarfile.TarInfo("../evil")
            ti.size = 1
            t.addfile(ti, io.BytesIO(b"x"))
        with self.assertRaises(Exception):
            nh.extract(tgz, tmp / "out")
        self.assertFalse((tmp / "evil").exists())


if __name__ == "__main__":
    unittest.main()
