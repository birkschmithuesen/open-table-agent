"""Shared post-build cleanup for the two Chain-D build entry points (e2e/stack.py,
scripts/sync-upstream.py --build): after a SUCCESSFUL build, reclaim dangling (untagged,
unreferenced) image layers only.

Concurrency: the 2026-11-20 ruling asks that this only run when no other build is in flight,
to avoid pruning layers a concurrent build still needs. Neither build entry point tracks
concurrent runs (no lock file, no PID registry), so a concurrency check is not feasible here.
Documenting that assumption instead: callers invoke this right after their own build exits 0,
which is safe as long as Chain-D builds are not run concurrently against the same podman store.
"""
import subprocess


def prune_dangling_images(podman_bin="podman"):
    """Run `<podman_bin> image prune -f` and print one line with freed space.

    Never raises: a prune failure (non-zero exit, missing binary, ...) is logged as a warning
    so it cannot fail or abort the build that just succeeded.
    """
    try:
        r = subprocess.run([podman_bin, "image", "prune", "-f"], capture_output=True, text=True)
    except OSError as e:
        print(f"warning: podman image prune -f failed to start: {e}")
        return
    if r.returncode != 0:
        print(f"warning: podman image prune -f exited {r.returncode}: {r.stderr.strip()}")
        return
    freed = _freed_space(r.stdout)
    print(f"podman image prune -f: freed {freed}" if freed else "podman image prune -f: nothing to free")


def _freed_space(prune_stdout):
    for line in prune_stdout.splitlines():
        if line.lower().startswith("total reclaimed space:"):
            return line.split(":", 1)[1].strip()
    return None
