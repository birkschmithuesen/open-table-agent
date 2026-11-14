"""Hermetic tests for the pure parts of e2e/apt_proxy.py (no network; broker call injected)."""
import gzip
import hashlib
import lzma
import tempfile
import unittest
from pathlib import Path

from e2e import apt_proxy as ap


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


PKGS = (b"Package: rsync\nVersion: 1\nFilename: pool/main/r/rsync/rsync_1_amd64.deb\n"
        b"SHA256: " + sha(b"DEB-RSYNC").encode() + b"\n\n"
        b"Package: curl\nFilename: pool/main/c/curl/curl_1_amd64.deb\nSHA256: " + sha(b"DEB-CURL").encode() + b"\n")


def release_text(entries: dict[str, bytes]) -> bytes:
    lines = ["-----BEGIN PGP SIGNED MESSAGE-----", "Hash: SHA512", "", "Origin: Debian", "MD5Sum:",
             " " + "0" * 32 + " 5 main/binary-amd64/Packages.xz", "SHA256:"]
    for rel, data in entries.items():
        lines.append(f" {sha(data)} {len(data)} {rel}")
    lines += ["SHA512:", " " + "f" * 128 + " 5 main/binary-amd64/Packages.xz", "-----BEGIN PGP SIGNATURE-----", "x"]
    return ("\n".join(lines) + "\n").encode()


class AptConf(unittest.TestCase):
    def test_apt_conf_args_scope_proxy_to_apt_only(self):
        d = Path(tempfile.mkdtemp())
        args = ap.apt_conf_args(d, 8766)
        self.assertEqual((d / "apt.conf").read_text(), 'Acquire::http::Proxy "http://127.0.0.1:8766";\n')
        self.assertIn(f"--podman-arg=--volume={d.resolve()}:/ota-apt:ro", args)
        self.assertIn("--podman-arg=--build-arg=APT_CONFIG=/ota-apt/apt.conf", args)
        self.assertFalse([a for a in args if "http_proxy" in a])


class Pure(unittest.TestCase):
    def test_parse_release_only_sha256_block(self):
        t = release_text({"main/binary-amd64/Packages.xz": b"abc"}).decode()
        self.assertEqual(ap.parse_release(t), {"main/binary-amd64/Packages.xz": sha(b"abc")})

    def test_parse_packages(self):
        self.assertEqual(ap.parse_packages(PKGS.decode()), {
            "pool/main/r/rsync/rsync_1_amd64.deb": sha(b"DEB-RSYNC"),
            "pool/main/c/curl/curl_1_amd64.deb": sha(b"DEB-CURL")})

    def test_classify(self):
        c = ap.classify
        self.assertEqual(c("/debian/dists/bookworm/InRelease"), ("release", "debian", "bookworm", "InRelease"))
        self.assertEqual(c("/debian-security/dists/bookworm-security/Release.gpg")[0], "release")
        self.assertEqual(c("/debian/dists/bookworm/main/binary-amd64/Packages.xz"),
                         ("index", "debian", "bookworm", "main/binary-amd64/Packages.xz"))
        self.assertEqual(c("/debian/dists/bookworm/main/binary-amd64/by-hash/SHA256/" + "a" * 64)[0], "byhash")
        self.assertEqual(c("/debian/pool/main/r/rsync/rsync_1_amd64.deb"),
                         ("deb", "debian", None, "pool/main/r/rsync/rsync_1_amd64.deb"))

    def test_classify_refuses(self):
        for p in ["/other/dists/x/InRelease", "/debian/dists/bookworm/../../etc/passwd",
                  "/debian/dists/bookworm/main/Contents-amd64.gz", "/debian/pool/main/x/evil.sh", "/", "//debian/pool/a.deb"]:
            with self.assertRaises(ap.Refused, msg=p):
                ap.classify(p)

    def test_split_target(self):
        self.assertEqual(ap.split_target("http://deb.debian.org/debian/dists/a/InRelease"),
                         ("deb.debian.org", "/debian/dists/a/InRelease"))
        self.assertEqual(ap.split_target("/debian/x", host_header="security.debian.org"), ("security.debian.org", "/debian/x"))
        with self.assertRaises(ap.Refused):
            ap.split_target("http://evil.example/debian/x")
        with self.assertRaises(ap.Refused):
            ap.split_target("deb.debian.org:443")  # CONNECT


class Mirror(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pkgs_xz = lzma.compress(PKGS)
        self.remote = {
            "https://deb.debian.org/debian/dists/bookworm/InRelease":
                release_text({"main/binary-amd64/Packages.xz": self.pkgs_xz, "main/binary-amd64/Packages.gz": gzip.compress(PKGS)}),
            "https://deb.debian.org/debian/dists/bookworm/Release.gpg": b"sig",
            "https://deb.debian.org/debian/dists/bookworm/main/binary-amd64/Packages.xz": self.pkgs_xz,
            "https://deb.debian.org/debian/pool/main/r/rsync/rsync_1_amd64.deb": b"DEB-RSYNC",
            "https://deb.debian.org/debian/pool/main/c/curl/curl_1_amd64.deb": b"DEB-BAD",
        }
        self.calls = []
        self.m = ap.Mirror(Path(self.tmp.name), self.fetch)

    def fetch(self, url, out, expect):
        self.calls.append((url, expect))
        if url not in self.remote:
            return False
        Path(out).write_bytes(self.remote[url])
        return True

    def get(self, path):
        return self.m.get("deb.debian.org", path).read_bytes()

    def test_release_unverified_then_index_and_deb_verified(self):
        self.get("/debian/dists/bookworm/InRelease")
        self.get("/debian/dists/bookworm/Release.gpg")
        self.assertTrue(all(e is None for _, e in self.calls))
        self.get("/debian/dists/bookworm/main/binary-amd64/Packages.xz")
        self.assertEqual(self.calls[-1][1], sha(self.pkgs_xz))
        self.assertEqual(self.get("/debian/pool/main/r/rsync/rsync_1_amd64.deb"), b"DEB-RSYNC")
        self.assertEqual(self.calls[-1][1], sha(b"DEB-RSYNC"))

    def test_index_without_release_refused(self):
        with self.assertRaises(ap.Refused):
            self.get("/debian/dists/bookworm/main/binary-amd64/Packages.xz")
        self.assertEqual(self.calls, [])

    def test_index_not_listed_in_release_refused(self):
        self.get("/debian/dists/bookworm/InRelease")
        with self.assertRaises(ap.Refused):
            self.get("/debian/dists/bookworm/contrib/binary-amd64/Packages.xz")

    def test_byhash_must_be_listed(self):
        self.get("/debian/dists/bookworm/InRelease")
        self.remote["https://deb.debian.org/debian/dists/bookworm/main/binary-amd64/by-hash/SHA256/" + sha(self.pkgs_xz)] = self.pkgs_xz
        self.assertEqual(self.get("/debian/dists/bookworm/main/binary-amd64/by-hash/SHA256/" + sha(self.pkgs_xz)), self.pkgs_xz)
        with self.assertRaises(ap.Refused):
            self.get("/debian/dists/bookworm/main/binary-amd64/by-hash/SHA256/" + "0" * 64)

    def test_deb_not_in_any_packages_refused(self):
        self.get("/debian/dists/bookworm/InRelease")
        self.get("/debian/dists/bookworm/main/binary-amd64/Packages.xz")
        with self.assertRaises(ap.Refused):
            self.get("/debian/pool/main/z/zzz/zzz_1_amd64.deb")

    def test_deb_checksum_mismatch_refused_and_not_cached(self):
        self.get("/debian/dists/bookworm/InRelease")
        self.get("/debian/dists/bookworm/main/binary-amd64/Packages.xz")
        with self.assertRaises(ap.Refused):
            self.get("/debian/pool/main/c/curl/curl_1_amd64.deb")
        self.assertFalse((Path(self.tmp.name) / "debian/pool/main/c/curl/curl_1_amd64.deb").exists())

    def test_cached_files_not_refetched_and_index_survives_restart(self):
        self.get("/debian/dists/bookworm/InRelease")
        self.get("/debian/dists/bookworm/main/binary-amd64/Packages.xz")
        self.get("/debian/pool/main/r/rsync/rsync_1_amd64.deb")
        n = len(self.calls)
        m2 = ap.Mirror(Path(self.tmp.name), self.fetch)
        m2.get("deb.debian.org", "/debian/dists/bookworm/InRelease")  # refreshed once per run
        self.assertEqual(len(self.calls), n + 1)
        m2.get("deb.debian.org", "/debian/dists/bookworm/main/binary-amd64/Packages.xz")
        m2.get("deb.debian.org", "/debian/pool/main/r/rsync/rsync_1_amd64.deb")
        self.assertEqual(len(self.calls), n + 1)

    def test_upstream_failure_is_refused_404(self):
        with self.assertRaises(ap.Refused) as cm:
            self.m.get("deb.debian.org", "/debian/dists/other/InRelease")
        self.assertEqual(cm.exception.status, 404)


if __name__ == "__main__":
    unittest.main()
