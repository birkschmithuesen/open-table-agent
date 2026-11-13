#!/usr/bin/env python3
"""Broker-backed local APT proxy for the patched-Teable image build (no direct egress to Debian hosts).

The build (--network=host, --build-arg http_proxy=http://127.0.0.1:<port>, which reaches every stage's RUN) sends plain-http apt requests
for deb.debian.org / security.debian.org (upstream's Debian sources are http://). Every request is
served from a cache under .work/apt-cache/ that is filled only through `hermes-download`:
  * InRelease / Release / Release.gpg  --unverified (apt verifies the GPG signature itself)
  * Packages indexes (also by-hash)     --sha256 from the Release/InRelease sha256 table
  * pool/**.deb                         --sha256 from the Packages index (Filename -> SHA256)
Anything that cannot be tied to a published checksum (unlisted index, unknown deb, Contents, CONNECT,
other hosts) is refused. Release files are refreshed once per proxy run; everything else is cached.

Usage:
  apt_proxy.py serve [--cache DIR] [--port N]
  apt_proxy.py build [--cache DIR] [--port N] [-- <sync-upstream.py args>]
    Fetches Prisma engines + xlsx via the broker, runs the proxy in-process (thread) and
    `scripts/sync-upstream.py --build` with e2e/bin/podman against it. This is the D2 build command.
"""
from __future__ import annotations

import argparse
import bz2
import gzip
import hashlib
import http.server
import lzma
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE = ROOT / ".work" / "apt-cache"
DEFAULT_PORT = 8766
ALLOWED_HOSTS = {"deb.debian.org", "security.debian.org"}

_REPO = r"/(?P<repo>debian|debian-security)"
_SUITE = r"(?P<suite>[a-z][a-z0-9-]*)"
_RELEASE = re.compile(_REPO + r"/dists/" + _SUITE + r"/(?P<rel>InRelease|Release|Release\.gpg)$")
_INDEX = re.compile(_REPO + r"/dists/" + _SUITE + r"/(?P<rel>[a-z-]+/binary-[a-z0-9]+/Packages(?:\.xz|\.gz|\.bz2)?)$")
_BYHASH = re.compile(_REPO + r"/dists/" + _SUITE + r"/(?P<rel>[a-z-]+/binary-[a-z0-9]+/by-hash/SHA256/(?P<hex>[0-9a-f]{64}))$")
_DEB = re.compile(_REPO + r"/(?P<rel>pool/[A-Za-z0-9._+~:/-]+\.deb)$")


class Refused(Exception):
    def __init__(self, msg: str, status: int = 403):
        super().__init__(msg)
        self.status = status


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_release(text: str) -> dict[str, str]:
    """relative path -> sha256, from the `SHA256:` block of a Release/InRelease."""
    out: dict[str, str] = {}
    inblock = False
    for line in text.splitlines():
        if line.startswith((" ", "\t")):
            parts = line.split()
            if inblock and len(parts) == 3 and re.fullmatch(r"[0-9a-f]{64}", parts[0]):
                out[parts[2]] = parts[0]
        else:
            inblock = line.strip() == "SHA256:"
    return out


def parse_packages(text: str) -> dict[str, str]:
    """Filename -> SHA256 from a Packages index."""
    out: dict[str, str] = {}
    for stanza in re.split(r"\n\s*\n", text):
        fn = sh = None
        for line in stanza.splitlines():
            if line.startswith("Filename:"):
                fn = line.split(":", 1)[1].strip()
            elif line.startswith("SHA256:"):
                sh = line.split(":", 1)[1].strip()
        if fn and sh:
            out[fn] = sh
    return out


def decompress(data: bytes) -> bytes:
    if data[:6] == b"\xfd7zXZ\x00":
        return lzma.decompress(data)
    if data[:2] == b"\x1f\x8b":
        return gzip.decompress(data)
    if data[:3] == b"BZh":
        return bz2.decompress(data)
    return data


def classify(path: str) -> tuple[str, str, str | None, str]:
    """(kind, repo, suite, rel); kind in release|index|byhash|deb. Raises Refused for everything else."""
    p = unquote(path.split("?", 1)[0])
    if ".." in p.split("/") or "//" in p:
        raise Refused(f"bad path {path}")
    for kind, rx in (("release", _RELEASE), ("byhash", _BYHASH), ("index", _INDEX), ("deb", _DEB)):
        m = rx.match(p)
        if m:
            return kind, m["repo"], (m.groupdict().get("suite")), m["rel"]
    raise Refused(f"not served (no published checksum path): {path}", 404)


def split_target(target: str, host_header: str | None = None) -> tuple[str, str]:
    """Request target -> (host, path). Accepts absolute-URI (proxy) or origin-form with Host header."""
    m = re.match(r"^http://([^/:]+)(?::80)?(/.*)$", target)
    if m:
        host, path = m.group(1), m.group(2)
    elif target.startswith("/") and host_header:
        host, path = host_header.split(":")[0], target
    else:
        raise Refused(f"unsupported request target {target} (CONNECT/https not served)")
    if host not in ALLOWED_HOSTS:
        raise Refused(f"host {host} not allowed")
    return host, path


class Mirror:
    """fetch(url, out_path, expected_sha256_or_None) -> bool is the injected broker call."""

    def __init__(self, cache: Path, fetch):
        self.cache = Path(cache)
        self.fetch = fetch
        self.lock = threading.RLock()
        self.refreshed: set[Path] = set()
        self.release: dict[tuple[str, str], dict[str, str]] = {}
        self.packages: dict[tuple[str, str], str] = {}
        self.scanned = False

    def _get_file(self, url: str, dst: Path, expect: str | None) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".part")
        tmp.unlink(missing_ok=True)
        if not self.fetch(url, tmp, expect):
            tmp.unlink(missing_ok=True)
            raise Refused(f"broker could not fetch {url}", 404)
        if expect is not None and sha256_file(tmp) != expect:
            tmp.unlink(missing_ok=True)
            raise Refused(f"checksum mismatch for {url}", 502)
        tmp.replace(dst)

    def _release_table(self, repo: str, suite: str) -> dict[str, str]:
        key = (repo, suite)
        if key not in self.release:
            for name in ("InRelease", "Release"):
                f = self.cache / repo / "dists" / suite / name
                if f.is_file():
                    self.release[key] = parse_release(f.read_text(errors="replace"))
                    break
            else:
                raise Refused(f"no Release for {repo}/{suite} fetched yet; no checksum available")
        return self.release[key]

    def _learn_index(self, repo: str, f: Path) -> None:
        for fn, sh in parse_packages(decompress(f.read_bytes()).decode("utf-8", "replace")).items():
            self.packages[(repo, fn)] = sh

    def _scan_cached_indexes(self) -> None:
        for repo in ("debian", "debian-security"):
            for f in (self.cache / repo / "dists").glob("*/*/binary-*/**/*"):
                if f.is_file() and not f.name.endswith(".part") and ("Packages" in f.name or f.parent.name == "SHA256"):
                    try:
                        self._learn_index(repo, f)
                    except (OSError, lzma.LZMAError, EOFError):
                        pass
        self.scanned = True

    def get(self, host: str, path: str) -> Path:
        kind, repo, suite, rel = classify(path)
        raw = path.split("?", 1)[0]
        url = f"https://{host}{raw}"
        with self.lock:
            if kind == "release":
                dst = self.cache / repo / "dists" / suite / rel
                if dst not in self.refreshed:
                    self._get_file(url, dst, None)
                    self.refreshed.add(dst)
                    self.release.pop((repo, suite), None)
                return dst
            if kind in ("index", "byhash"):
                table = self._release_table(repo, suite)
                if kind == "index":
                    expect = table.get(rel)
                else:
                    m = _BYHASH.match(unquote(raw))
                    expect = m["hex"] if m["hex"] in table.values() else None
                if not expect:
                    raise Refused(f"{rel} is not listed in the signed Release sha256 table")
                dst = self.cache / repo / "dists" / suite / rel
                if not (dst.is_file() and sha256_file(dst) == expect):
                    self._get_file(url, dst, expect)
                self._learn_index(repo, dst)
                return dst
            # deb
            if not self.scanned:
                self._scan_cached_indexes()
            expect = self.packages.get((repo, rel))
            if not expect:
                raise Refused(f"{rel} not listed in any fetched Packages index; no checksum available")
            dst = self.cache / repo / rel
            if not (dst.is_file() and sha256_file(dst) == expect):
                self._get_file(url, dst, expect)
            return dst


def broker_fetch(url: str, out: Path, expect: str | None) -> bool:
    check = ["--sha256", expect] if expect else ["--unverified"]
    r = subprocess.run(["hermes-download", url, *check, "-o", str(out)], stdout=subprocess.DEVNULL)
    if r.returncode != 0:
        sys.stderr.write(f"apt-proxy: hermes-download exit {r.returncode} for {url}\n")
    return r.returncode == 0


def make_handler(mirror: Mirror):
    class H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *a):
            sys.stderr.write("apt-proxy: " + fmt % a + "\n")

        def _serve(self, head: bool):
            try:
                host, path = split_target(self.path, self.headers.get("Host"))
                f = mirror.get(host, path)
                size = f.stat().st_size
                self.send_response(200)
                self.send_header("Content-Length", str(size))
                self.send_header("Content-Type", "application/octet-stream")
                self.end_headers()
                if not head:
                    with f.open("rb") as fh:
                        while chunk := fh.read(1 << 20):
                            self.wfile.write(chunk)
            except Refused as e:
                sys.stderr.write(f"apt-proxy: REFUSED {e.status} {e}\n")
                body = str(e).encode()
                self.send_response(e.status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if not head:
                    self.wfile.write(body)

        def do_GET(self):
            self._serve(False)

        def do_HEAD(self):
            self._serve(True)

        def do_CONNECT(self):
            body = b"CONNECT not served"
            self.send_response(403)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return H


def start_server(cache: Path, port: int, fetch=broker_fetch) -> http.server.ThreadingHTTPServer:
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), make_handler(Mirror(cache, fetch)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _podman_args(script: str) -> list[str]:
    r = subprocess.run([sys.executable, str(ROOT / "e2e" / script), "fetch" if script == "prisma_engines.py" else "--dir",
                        *([] if script == "prisma_engines.py" else [str(ROOT / ".work" / "sheetjs")])],
                       capture_output=True, text=True)
    sys.stderr.write(r.stderr)
    if r.returncode != 0:
        raise SystemExit(f"{script} failed ({r.returncode})")
    for line in r.stdout.splitlines():
        if line.startswith("PODMAN_ARGS "):
            return line.split()[1:]
    raise SystemExit(f"{script}: no PODMAN_ARGS line")


def cmd_build(cache: Path, port: int, extra: list[str]) -> int:
    pargs = _podman_args("prisma_engines.py") + _podman_args("vendor_xlsx.py")
    # --build-arg (predefined proxy arg) reaches RUN in EVERY stage; --env would only hit the final one,
    # and with --network=host the other stages would silently go direct to deb.debian.org.
    pargs += ["--podman-arg=--network=host", f"--podman-arg=--build-arg=http_proxy=http://127.0.0.1:{port}"]
    if not any(a.startswith("--work-dir") for a in extra):
        extra = ["--work-dir", str(ROOT / ".work"), *extra]
    cmd = [sys.executable, str(ROOT / "scripts" / "sync-upstream.py"), "--build", *pargs, *extra]
    env = dict(os.environ, OTA_PODMAN=os.environ.get("OTA_PODMAN") or str(ROOT / "e2e" / "bin" / "podman"))
    srv = start_server(cache, port)
    try:
        return subprocess.run(cmd, env=env).returncode
    finally:
        srv.shutdown()
        srv.server_close()


def main(argv: list[str]) -> int:
    extra: list[str] = []
    if "--" in argv:
        i = argv.index("--")
        argv, extra = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["serve", "build"])
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        return cmd_build(a.cache, a.port, extra)
    srv = start_server(a.cache, a.port)
    print(f"apt proxy on http://127.0.0.1:{a.port}, cache {a.cache}", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
