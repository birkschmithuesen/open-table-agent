"""Synthetic git repos and subprocess helpers for scripts/sync-upstream.py tests."""
from __future__ import annotations
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IDENT = ["-c", "user.name=t", "-c", "user.email=t@t"]


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r


def make_upstream(tmp: Path) -> tuple[Path, str]:
    tmp.mkdir(parents=True)
    _git("init", "-q", "-b", "develop", str(tmp), cwd=tmp.parent)
    module = tmp / "app" / "module.ts"
    module.parent.mkdir(parents=True)
    module.write_text("".join(f"line {i}\n" for i in range(1, 11)))
    (tmp / "README").write_text("upstream\n")
    _git("add", ".", cwd=tmp)
    _git(*IDENT, "commit", "-q", "-m", "initial", cwd=tmp)
    sha = _git("rev-parse", "HEAD", cwd=tmp).stdout.strip()
    return tmp, sha


def make_patch(upstream: Path, out_dir: Path, name: str = "0001-demo.patch") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    clone = out_dir.parent / "_patch_clone"
    if clone.exists():
        shutil.rmtree(clone)
    _git("clone", "-q", str(upstream), str(clone), cwd=out_dir.parent)
    module = clone / "app" / "module.ts"
    lines = module.read_text().splitlines(keepends=True)
    lines[4] = "line 5 edited\n"
    module.write_text("".join(lines))
    (clone / "app" / "new.ts").write_text("new file\n")
    _git("add", ".", cwd=clone)
    _git(*IDENT, "commit", "-q", "-m", "demo patch", cwd=clone)
    _git("format-patch", "-1", "-o", str(out_dir), cwd=clone)
    [produced] = list(out_dir.glob("0001-*.patch"))
    target = out_dir / name
    if produced != target:
        produced.rename(target)
    shutil.rmtree(clone)
    return target


def break_context(patch: Path) -> None:
    lines = patch.read_text().splitlines(keepends=True)
    seen_at = False
    for i, line in enumerate(lines):
        if line.startswith("@@"):
            seen_at = True
            continue
        if seen_at and line.startswith(" "):
            lines[i] = " BROKEN CONTEXT\n"
            break
    patch.write_text("".join(lines))


def make_fake_podman(path: Path, build_exit: int = 0) -> Path:
    """Fake podman binary: appends each invocation's argv (as a JSON line) to `<path>.log`.
    Exits `build_exit` for `build`, 0 for everything else (including `image prune -f`)."""
    log = path.with_suffix(".log")
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"with open({str(log)!r}, 'a') as f:\n"
        "    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        f"sys.exit({build_exit} if sys.argv[1:2] == ['build'] else 0)\n"
    )
    path.chmod(0o755)
    return path


def run_sync(tmp: Path, *args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    cmd = [
        "python3", str(ROOT / "scripts" / "sync-upstream.py"),
        "--work-dir", str(tmp / ".work"),
        "--lock", str(tmp / "upstream.lock.json"),
        *args,
    ]
    return subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, env=env)
