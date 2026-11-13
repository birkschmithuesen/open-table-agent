#!/usr/bin/env python3
"""Prisma engines for the patched-Teable build, fetched only via the download broker (spec D-2).

Subcommands:
  fetch [--cache DIR]          idempotent; prints ENGINE lines and one PODMAN_ARGS line (mode env)
  serve [--cache DIR] --port N serve the cache in mirror layout (fallback a)
  build-with-mirror            serve + run scripts/sync-upstream.py --build against the mirror
"""
from __future__ import annotations

import argparse
import functools
import gzip
import hashlib
import http.server
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HASH = "4123509d24aa4dede1e864b46351bf2790323b69"
PLATFORM = "debian-openssl-3.0.x"
BASE = f"https://binaries.prisma.sh/all_commits/{HASH}/{PLATFORM}"
DEFAULT_CACHE = ROOT / ".work" / "prisma-engines"
DEFAULT_MODE = "env"
# (kind, gz file, engine file name)
FILES = [
    ("query", "libquery_engine.so.node.gz", f"libquery_engine-{PLATFORM}.so.node"),
    ("schema", "schema-engine.gz", f"schema-engine-{PLATFORM}"),
]
MIRROR_PORT = 8765


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def broker(url: str, out: Path, check: list[str]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["hermes-download", url, *check, "-o", str(out)])
    if r.returncode == 4:
        print(f"checksum mismatch for {url}", file=sys.stderr)
        sys.exit(1)
    if r.returncode != 0:
        print(f"hermes-download failed ({r.returncode}) for {url}", file=sys.stderr)
        sys.exit(1)


def parse_sha_file(p: Path) -> str:
    m = re.match(r"\s*([0-9a-fA-F]{64})\b", p.read_text())
    if not m:
        print(f"no sha256 in {p}", file=sys.stderr)
        sys.exit(1)
    return m.group(1).lower()


def podman_args(cache: Path) -> list[str]:
    eng = cache.resolve() / "engines"
    return [
        f"--volume={eng}:/ota-prisma:ro",
        f"--env=PRISMA_QUERY_ENGINE_LIBRARY=/ota-prisma/libquery_engine-{PLATFORM}.so.node",
        f"--env=PRISMA_SCHEMA_ENGINE_BINARY=/ota-prisma/schema-engine-{PLATFORM}",
    ]


def cmd_fetch(cache: Path) -> int:
    cache = cache.resolve()
    d = cache / "all_commits" / HASH / PLATFORM
    (cache / "engines").mkdir(parents=True, exist_ok=True)
    for kind, gz_name, eng_name in FILES:
        gz, shaf, eng = d / gz_name, d / (gz_name + ".sha256"), cache / "engines" / eng_name
        if shaf.is_file() and gz.is_file() and sha256_file(gz) == parse_sha_file(shaf):
            hexv = parse_sha_file(shaf)
            print(f"cached {gz_name}")
        else:
            broker(f"{BASE}/{gz_name}.sha256", shaf, ["--unverified"])
            hexv = parse_sha_file(shaf)
            broker(f"{BASE}/{gz_name}", gz, ["--sha256", hexv])
            if sha256_file(gz) != hexv:
                print(f"checksum mismatch for {gz}", file=sys.stderr)
                return 1
        with gzip.open(gz, "rb") as src, eng.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        eng.chmod(0o755)
        print(f"ENGINE {kind} {eng} gz_sha256={hexv}")
    print("PODMAN_ARGS " + " ".join("--podman-arg=" + a for a in podman_args(cache)))
    return 0


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *a):
        sys.stderr.write("mirror: " + fmt % a + "\n")


def start_server(cache: Path, port: int) -> http.server.ThreadingHTTPServer:
    handler = functools.partial(_Quiet, directory=str(cache.resolve()))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def podman_bin() -> str:
    return os.environ.get("OTA_PODMAN") or str(ROOT / "e2e" / "bin" / "podman")


def with_mirror(cache: Path, port: int, cmd: list[str], env: dict[str, str]) -> int:
    srv = start_server(cache, port)
    try:
        return subprocess.run(cmd, env=env).returncode
    finally:
        srv.shutdown()
        srv.server_close()


def cmd_build_with_mirror(cache: Path, port: int, extra: list[str]) -> int:
    cmd = [sys.executable, str(ROOT / "scripts/sync-upstream.py"), "--build",
           "--podman-arg=--network=host",
           f"--podman-arg=--env=PRISMA_ENGINES_MIRROR=http://127.0.0.1:{port}", *extra]
    env = dict(os.environ, OTA_PODMAN=podman_bin())
    return with_mirror(cache, port, cmd, env)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("fetch", "serve", "build-with-mirror"):
        sp = sub.add_parser(name)
        sp.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
        if name != "fetch":
            sp.add_argument("--port", type=int, default=MIRROR_PORT)
        if name == "build-with-mirror":
            sp.add_argument("extra", nargs="*")
    a = ap.parse_args(argv)
    if a.cmd == "fetch":
        return cmd_fetch(a.cache)
    if a.cmd == "serve":
        srv = start_server(a.cache, a.port)
        print(f"serving {a.cache} on http://127.0.0.1:{a.port}", flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            srv.shutdown()
        return 0
    return cmd_build_with_mirror(a.cache, a.port, a.extra)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
