#!/usr/bin/env python3
"""Node headers for node-gyp in the patched-Teable build, fetched only via the download broker.

Under the build's local proxy node-gyp cannot download node-v<ver>-headers.tar.gz from nodejs.org
(CONNECT refused; the optional `cpu-features` native build would be rolled back). Instead this fetches
SHASUMS256.txt (--unverified: nodejs.org signs it only with a detached GPG signature we cannot check
here; the tarball hash below is then the only chain) and the headers tarball (--sha256 from that file),
extracts it, and prints one PODMAN_ARGS line: a read-only volume plus
`--build-arg=npm_config_nodedir=...` (declared as ARG per stage by e2e/build_shim.py; never image ENV).
Idempotent.

Usage: node_headers.py [--version 24.22.2] [--dir DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VERSION = "24.22.2"  # ARG NODE_VERSION of upstream dockers/teable/Dockerfile (build image node:<v>-bookworm)
DEFAULT_DIR = ROOT / ".work" / "node-headers"
MOUNT = "/ota-node-headers"
BASE = "https://nodejs.org/dist"


def headers_name(version: str) -> str:
    return f"node-v{version}-headers.tar.gz"


def parse_shasums(text: str, name: str) -> str:
    """sha256 hex of `name` from a SHASUMS256.txt body; SystemExit if absent/malformed."""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == name:
            h = parts[0].lower()
            if len(h) == 64 and all(c in "0123456789abcdef" for c in h):
                return h
            break
    raise SystemExit(f"no valid sha256 for {name} in SHASUMS256.txt")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def broker(url: str, out: Path, check: list[str]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["hermes-download", url, *check, "-o", str(out)])
    if r.returncode != 0:
        raise SystemExit(f"hermes-download failed ({r.returncode}) for {url}")


def extract(tgz: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tgz) as t:
        t.extractall(dest, filter="data")  # rejects absolute paths, .., links outside dest


def podman_args(nodedir_host: Path, version: str) -> list[str]:
    return [f"--volume={nodedir_host}:{MOUNT}:ro",
            f"--build-arg=npm_config_nodedir={MOUNT}/node-v{version}"]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default=DEFAULT_VERSION)
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    a = ap.parse_args(argv)
    d = a.dir.resolve()
    name = headers_name(a.version)
    shasums, tgz = d / f"SHASUMS256-v{a.version}.txt", d / name
    marker = d / f"node-v{a.version}" / "include" / "node" / "common.gypi"
    broker(f"{BASE}/v{a.version}/SHASUMS256.txt", shasums, ["--unverified"])
    expect = parse_shasums(shasums.read_text(), name)
    if not (tgz.is_file() and sha256_file(tgz) == expect):
        broker(f"{BASE}/v{a.version}/{name}", tgz, ["--sha256", expect])
        if sha256_file(tgz) != expect:
            print(f"checksum mismatch for {tgz}", file=sys.stderr)
            return 1
    if not marker.is_file():
        extract(tgz, d)
    if not marker.is_file():
        print(f"{marker} missing after extract", file=sys.stderr)
        return 1
    print(f"NODE_HEADERS {tgz} sha256={expect}")
    print("PODMAN_ARGS " + " ".join("--podman-arg=" + x for x in podman_args(d, a.version)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
