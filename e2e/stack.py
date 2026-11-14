#!/usr/bin/env python3
"""Podman stack for the e2e run: pod ota-e2e with postgres, redis and the patched Teable CE image.

  stack.py up|down|status

Every podman call goes through the committed shim e2e/bin/podman (resolved from this file's path).
`up` writes the per-run random secrets to e2e/.state (mode 0600, gitignored) for debugging; bootstrap.py
does not need them (it only talks REST to the published port).
"""
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PODMAN = os.path.join(HERE, "bin", "podman")
POD = "ota-e2e"
PORT = 3010
URL = f"http://127.0.0.1:{PORT}"
POSTGRES = "docker.io/library/postgres:15.4"
REDIS = "docker.io/library/redis:7.2.4"
# No catatonit on this host, so podman cannot build its own pause image. Infra image: redis base whose
# entrypoint is `sleep` (e2e/infra/Containerfile), built on first use.
INFRA_IMAGE = "localhost/ota-e2e-infra:1"
HEALTH_PATHS = ("/health", "/api/health")
TIMEOUT_S = 300
STATE = os.path.join(HERE, ".state")


def podman(*args, check=True, capture=False):
    # The shim runs podman in a transient systemd unit and the default cgroupfs manager leaves the containers
    # in that unit's cgroup: they are killed when the shim call returns. The systemd manager gives each
    # container its own scope, so detached containers survive.
    r = subprocess.run([PODMAN, "--cgroup-manager=systemd", *args], text=True, capture_output=capture)
    if check and r.returncode != 0:
        if capture:
            sys.stderr.write(r.stdout + r.stderr)
        raise RuntimeError(f"podman {' '.join(args[:2])} failed with {r.returncode}")
    return r


def image_tag(root=ROOT):
    with open(os.path.join(root, "upstream.lock.json"), encoding="utf-8") as f:
        return json.load(f)["image"]["tag"]


def new_secrets():
    return {"pg": secrets.token_hex(16), "redis": secrets.token_hex(16), "secret_key": secrets.token_hex(32)}


def run_args(tag, s):
    """Argument lists (after `podman`) for the pod and its three containers."""
    pg_url = f"postgresql://teable:{s['pg']}@127.0.0.1:5432/teable"
    redis_url = f"redis://default:{s['redis']}@127.0.0.1:6379/0"
    return [
        ["pod", "create", "--name", POD, "--infra-image", INFRA_IMAGE, "-p", f"127.0.0.1:{PORT}:3000"],
        ["run", "-d", "--pod", POD, "--name", f"{POD}-db",
         "-e", "POSTGRES_USER=teable", "-e", f"POSTGRES_PASSWORD={s['pg']}", "-e", "POSTGRES_DB=teable", POSTGRES],
        ["run", "-d", "--pod", POD, "--name", f"{POD}-cache", REDIS, "redis-server", "--requirepass", s["redis"]],
        ["run", "-d", "--pod", POD, "--name", f"{POD}-teable",
         "-e", f"PRISMA_DATABASE_URL={pg_url}", "-e", f"BACKEND_CACHE_REDIS_URI={redis_url}",
         "-e", f"PUBLIC_ORIGIN={URL}", "-e", f"SECRET_KEY={s['secret_key']}", tag],
    ]


def healthy():
    for p in HEALTH_PATHS:
        try:
            with urllib.request.urlopen(URL + p, timeout=3) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
    return False


def ensure_infra_image():
    if podman("image", "exists", INFRA_IMAGE, check=False, capture=True).returncode != 0:
        infra = os.path.join(HERE, "infra")
        podman("build", "-t", INFRA_IMAGE, "-f", os.path.join(infra, "Containerfile"), infra, capture=True)


def _started(a):
    """`systemd-run --wait` reports 1 for `run -d` even though the container is up; accept if it exists."""
    if a[0] != "run":
        return False
    name = a[a.index("--name") + 1]
    return podman("container", "exists", name, check=False, capture=True).returncode == 0


def wait_db(timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = podman("exec", f"{POD}-db", "pg_isready", "-h", "127.0.0.1", "-U", "teable", check=False, capture=True)
        if r.returncode == 0:
            return
        time.sleep(2)
    raise RuntimeError(f"postgres not ready after {timeout}s")


def pod_exists():
    return podman("pod", "exists", POD, check=False, capture=True).returncode == 0


def down():
    if pod_exists():
        podman("pod", "rm", "-f", POD, check=False, capture=True)
    if os.path.exists(STATE):
        os.remove(STATE)
    return 0


def up(timeout=TIMEOUT_S):
    tag = os.environ.get("OTA_E2E_IMAGE") or image_tag()  # override only for diagnosing, e.g. a baseline image
    down()
    s = new_secrets()
    fd = os.open(STATE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"pod": POD, "url": URL, "tag": tag, **s}, f)
    try:
        ensure_infra_image()
        for a in run_args(tag, s):
            if a[0] == "run" and a[-1] == tag:
                wait_db()  # the teable entrypoint migrates once and exits if postgres is not accepting TCP yet
            r = podman(*a, check=False, capture=True)
            if r.returncode != 0 and not _started(a):
                sys.stderr.write(r.stdout + r.stderr)
                raise RuntimeError(f"podman {' '.join(a[:2])} failed with {r.returncode}")
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    deadline = time.time() + timeout
    while time.time() < deadline:
        if healthy():
            print(f"ready {URL}")
            return 0
        time.sleep(3)
    print(f"timeout after {timeout}s waiting for {URL}; last 50 log lines of {POD}-teable:", file=sys.stderr)
    r = podman("logs", "--tail", "50", f"{POD}-teable", check=False, capture=True)
    sys.stderr.write(r.stdout + r.stderr)
    return 1


def status():
    if not pod_exists():
        print("absent")
        return 1
    r = podman("ps", "--pod", "--filter", f"pod={POD}", "--format", "{{.Names}} {{.Status}}", capture=True)
    print(r.stdout.strip())
    print("healthy" if healthy() else "unhealthy")
    return 0 if healthy() else 1


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    fn = {"up": up, "down": down, "status": status}.get(cmd)
    if not fn:
        print("usage: stack.py up|down|status", file=sys.stderr)
        return 2
    return fn()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
