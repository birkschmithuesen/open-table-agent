#!/usr/bin/env python3
"""Build shim for buildah 1.28 (podman 4.3.1), which rejects `COPY --link`.

render(src, dst): copy a Dockerfile, dropping the `--link` flag from COPY/ADD lines (idempotent).
`--link` only changes layer caching, not the resulting image. The source file is never modified.

CLI (used by e2e/bin/podman):
  build_shim.py rewrite-args <podman args...>
    For `podman build [-f|--file FILE] ... CONTEXT`, renders FILE into <ROOT>/.work/build-shim/ and
    prints the argv with FILE replaced, NUL-separated. Other commands are echoed unchanged.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / ".work" / "build-shim"

_INSTR = re.compile(r"^(\s*(?:COPY|ADD)\s+)((?:--\S+\s+)*)", re.IGNORECASE)
_LINK = re.compile(r"--link(?:=\S+)?$")


def _fix_line(line: str) -> str:
    m = _INSTR.match(line)
    if not m or "--link" not in m.group(2):
        return line
    flags = [f for f in m.group(2).split() if not _LINK.match(f)]
    rest = line[m.end():]
    return m.group(1) + "".join(f + " " for f in flags) + rest


def render(src: Path, dst: Path) -> Path:
    src, dst = Path(src), Path(dst)
    text = src.read_bytes().decode("utf-8")
    out = "".join(_fix_line(l) for l in text.splitlines(keepends=True))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(out.encode("utf-8"))
    return dst


def _resolve(file_arg: str, context: str) -> Path:
    p = Path(file_arg)
    if p.is_file():
        return p
    return Path(context) / p


def rewrite_args(argv: list[str], out_dir: Path = OUT_DIR) -> list[str]:
    if not argv or argv[0] != "build":
        return list(argv)
    context = argv[-1]
    res = list(argv)
    for i, a in enumerate(argv):
        idx = val = None
        if a in ("-f", "--file") and i + 1 < len(argv) - 1:
            idx, val = i + 1, argv[i + 1]
        elif a.startswith("--file="):
            idx, val = i, a[len("--file="):]
        if idx is None:
            continue
        src = _resolve(val, context).resolve()
        tag = hashlib.sha256(str(src).encode()).hexdigest()[:12]
        dst = render(src, out_dir / f"{src.name}.{tag}")
        res[idx] = str(dst) if idx != i else f"--file={dst}"
        break
    return res


def main(argv: list[str]) -> int:
    if not argv or argv[0] != "rewrite-args":
        print(__doc__, file=sys.stderr)
        return 2
    sys.stdout.write("".join(a + "\0" for a in rewrite_args(argv[1:])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
