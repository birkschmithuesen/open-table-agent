#!/usr/bin/env python3
"""Fetch upstream Teable, apply patches/*.patch in a fresh worktree, record upstream.lock.json (spec §6)."""
from __future__ import annotations
import argparse, datetime, hashlib, json, os, re, subprocess, sys
from pathlib import Path

DEFAULT_URL = "https://github.com/teableio/teable.git"
IDENT = ["-c", "user.name=open-table-agent-sync", "-c", "user.email=sync@open-table-agent.invalid"]


class EnvError(Exception):
    pass


def git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    except FileNotFoundError as e:
        raise EnvError(f"git not found: {e}")
    if check and r.returncode != 0:
        raise EnvError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r


def full_ref(ref: str | None, tag: str | None) -> str:
    if tag:
        return f"refs/tags/{tag}"
    ref = ref or "develop"
    return ref if ref.startswith("refs/") else f"refs/heads/{ref}"


def fetch(cache: Path, url: str, ref: str) -> str:
    if not cache.exists():
        git("init", "--bare", "--quiet", str(cache))
    git("fetch", "--no-tags", "--quiet", url, f"+{ref}:refs/ota/upstream", cwd=cache)
    return git("rev-parse", "refs/ota/upstream^{commit}", cwd=cache).stdout.strip()


def patch_files(d: Path) -> list[Path]:
    files = sorted(d.glob("[0-9][0-9][0-9][0-9]-*.patch"))
    if not files:
        raise EnvError(f"no NNNN-*.patch in {d}")
    return files


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def image_tag(upstream_sha: str, hashes: list[str]) -> str:
    return f"localhost/ota-teable:{upstream_sha[:12]}-{hashlib.sha256(''.join(hashes).encode()).hexdigest()[:8]}"


def fresh_worktree(cache: Path, wt: Path, sha: str) -> None:
    if wt.exists():
        git("worktree", "remove", "--force", str(wt), cwd=cache, check=False)
    git("worktree", "prune", cwd=cache)
    git("worktree", "add", "--detach", "--quiet", str(wt), sha, cwd=cache)


def hunk_report(wt: Path, patch: Path) -> list[str]:
    """Per failing hunk: 'path=<p> hunk=<@@ header @@>' from `git apply --check -v`."""
    r = git("apply", "--check", "-v", str(patch.resolve()), cwd=wt, check=False)
    out = []
    for path, line in re.findall(r"error: patch failed: (\S+):(\d+)", r.stderr):
        out.append(f"path={path} hunk={find_hunk(patch, path, int(line))}")
    for path in re.findall(r"error: (\S+): does not exist in index", r.stderr):
        out.append(f"path={path} hunk=(file missing)")
    return out or [f"path=? hunk=? ({r.stderr.strip().splitlines()[-1] if r.stderr.strip() else 'git am failed'})"]


def find_hunk(patch: Path, path: str, old_start: int) -> str:
    cur = None
    for l in patch.read_text().splitlines():
        m = re.match(r"diff --git a/(\S+) b/", l)
        if m:
            cur = m.group(1)
        h = re.match(r"(@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@)", l)
        if h and cur == path and int(h.group(2)) == old_start:
            return h.group(1)
    return f"@@ -{old_start} @@"


def apply_series(wt: Path, patches: list[Path]) -> list[str]:
    """Apply one patch per `git am` session; return CONFLICT lines (empty = success)."""
    for p in patches:
        r = git(*IDENT, "am", "--3way", "--quiet", str(p.resolve()), cwd=wt, check=False)
        if r.returncode != 0:
            git("am", "--abort", cwd=wt, check=False)
            return [f"CONFLICT patch={p.name} {h}" for h in hunk_report(wt, p)]
    return []


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="sync-upstream.py")
    p.add_argument("--upstream-url", default=DEFAULT_URL)
    ref_group = p.add_mutually_exclusive_group()
    ref_group.add_argument("--ref")
    ref_group.add_argument("--tag")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--build", action="store_true")
    p.add_argument("--podman-arg", action="append", default=[])
    p.add_argument("--work-dir", default=".work")
    p.add_argument("--lock", default="upstream.lock.json")
    p.add_argument("--patches", default="patches")
    return p.parse_args(argv)


def write_lock(lock_path: Path, lock: dict) -> None:
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")


def build_lock(url: str, ref: str, sha: str, files: list[Path], hashes: list[str], patched: str, tag: str) -> dict:
    return {
        "schema": 1,
        "upstream": {"url": url, "ref": ref, "sha": sha},
        "patches": [{"file": f.name, "sha256": h} for f, h in zip(files, hashes)],
        "patched_commit": patched,
        "image": {"tag": tag, "built": False},
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def podman_build(build_cmd: list[str]) -> int:
    try:
        r = subprocess.run(build_cmd)
    except FileNotFoundError:
        return 127
    return r.returncode


def load_lock(lock_path: Path) -> dict | None:
    if not lock_path.exists():
        return None
    try:
        return json.loads(lock_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def is_up_to_date(existing: dict, url: str, ref: str, sha: str, hashes: list[str], existing_wt: Path) -> bool:
    if existing.get("upstream") != {"url": url, "ref": ref, "sha": sha}:
        return False
    if [p.get("sha256") for p in existing.get("patches", [])] != hashes:
        return False
    if not existing_wt.exists():
        return False
    head = git("rev-parse", "HEAD", cwd=existing_wt, check=False).stdout.strip()
    return head == existing.get("patched_commit")


def run(argv: list[str]) -> int:
    args = parse_args(argv)
    git("--version")

    work = Path(args.work_dir)
    work.mkdir(parents=True, exist_ok=True)
    cache = work / "upstream.git"
    ref = full_ref(args.ref, args.tag)
    sha = fetch(cache, args.upstream_url, ref)
    print(f"UPSTREAM {sha}")

    files = patch_files(Path(args.patches))
    hashes = [sha256(f) for f in files]
    tag = image_tag(sha, hashes)
    podman_bin = os.environ.get("OTA_PODMAN", "podman")
    lock_path = Path(args.lock)

    if not args.dry_run:
        existing = load_lock(lock_path)
        existing_wt = work / f"teable-{sha[:12]}"
        if existing is not None and is_up_to_date(existing, args.upstream_url, ref, sha, hashes, existing_wt):
            print(f"UP-TO-DATE {sha}")
            if args.build and not existing.get("image", {}).get("built", False):
                build_cmd = [podman_bin, "build", "-f", "dockers/teable/Dockerfile", "-t", tag, *args.podman_arg, str(existing_wt)]
                if podman_build(build_cmd) != 0:
                    return 3
                existing["image"]["built"] = True
                write_lock(lock_path, existing)
            return 0

    wt = work / (("dry-run-" if args.dry_run else "teable-") + sha[:12])
    fresh_worktree(cache, wt, sha)

    conflicts = apply_series(wt, files)
    if conflicts:
        for c in conflicts:
            print(c)
        git("worktree", "remove", "--force", str(wt), cwd=cache, check=False)
        return 1

    patched = git("rev-parse", "HEAD", cwd=wt).stdout.strip()
    print(f"PATCHED {patched}")
    print(f"IMAGE {tag}")

    if args.dry_run:
        git("worktree", "remove", "--force", str(wt), cwd=cache, check=False)
        print("DRY-RUN ok")
        return 0

    lock = build_lock(args.upstream_url, ref, sha, files, hashes, patched, tag)
    write_lock(lock_path, lock)

    build_cmd = [podman_bin, "build", "-f", "dockers/teable/Dockerfile", "-t", tag, *args.podman_arg, str(wt)]
    if args.build:
        if podman_build(build_cmd) != 0:
            return 3
        lock["image"]["built"] = True
        write_lock(lock_path, lock)
    else:
        print("BUILD " + " ".join(build_cmd))
    return 0


def main(argv: list[str]) -> int:
    try:
        return run(argv)
    except EnvError as e:
        print(f"sync-upstream: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
