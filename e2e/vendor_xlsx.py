#!/usr/bin/env python3
"""xlsx-0.20.3.tgz for the patched-Teable build, fetched only via the download broker.

Upstream's `pnpm fetch` cannot reach cdn.sheetjs.com. This fetches the tarball through the broker
(--sha256), verifies sha512 against the upstream lockfile integrity (pinned below, from
pnpm-lock.yaml `xlsx@https://cdn.sheetjs.com/xlsx-0.20.3/xlsx-0.20.3.tgz`), and prints one
PODMAN_ARGS line exposing it at the path e2e/build_shim.py seeds into the pnpm store. Idempotent.

Usage: vendor_xlsx.py [--dir DIR]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://cdn.sheetjs.com/xlsx-0.20.3/xlsx-0.20.3.tgz"
NAME = "xlsx-0.20.3.tgz"
SHA256 = "8dc73fc3b00203e72d176e85b50938627c7b086e607c682e8d3c22c02bb99fe8"
INTEGRITY = "sha512-oLDq3jw7AcLqKWH2AhCpVTZl8mf6X2YReP+Neh0SJUzV/BdZYjth94tG5toiMB1PPrYtxOCfaoUCkvtuH+3AJA=="
DEFAULT_DIR = ROOT / ".work" / "sheetjs"


def integrity_ok(p: Path) -> bool:
    if not p.is_file():
        return False
    data = p.read_bytes()
    return ("sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode() == INTEGRITY
            and hashlib.sha256(data).hexdigest() == SHA256)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    d = ap.parse_args(argv).dir.resolve()
    tgz = d / NAME
    if integrity_ok(tgz):
        print(f"cached {NAME}")
    else:
        d.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["hermes-download", URL, "--sha256", SHA256, "-o", str(tgz)])
        if r.returncode != 0:
            print(f"hermes-download failed ({r.returncode}) for {URL}", file=sys.stderr)
            return 1
        if not integrity_ok(tgz):
            print(f"integrity mismatch for {tgz} (lockfile {INTEGRITY})", file=sys.stderr)
            return 1
    print(f"XLSX {tgz} integrity={INTEGRITY}")
    print(f"PODMAN_ARGS --podman-arg=--volume={d}:/ota-vendor:ro")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
