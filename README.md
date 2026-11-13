# open-table-agent

MCP server and a minimal patch set that give AI agents full access to a self-hosted open-source Teable (Community Edition).

Status: planning. See `docs/decisions.md`.

## Build shim

The host has podman 4.3.1 / buildah 1.28, which rejects `COPY --link` (used by the upstream Teable Dockerfile). `e2e/bin/podman` (set as `OTA_PODMAN`) renders a derived Containerfile into `.work/build-shim/` with `--link` removed from COPY/ADD lines (`e2e/build_shim.py`) and builds that one. `--link` only affects layer caching, not the image. The same rendering prefixes upstream's `RUN pnpm fetch` with a pnpm-store seed of `xlsx-0.20.3.tgz` (cdn.sheetjs.com is unreachable): `python3 e2e/vendor_xlsx.py` fetches it via the download broker, verifies it against the lockfile sha512 and prints the `--podman-arg=--volume=...:/ota-vendor:ro` to pass to `sync-upstream.py --build`. The upstream Dockerfile is never edited. `upstream.lock.json` is rewritten wholesale by `scripts/sync-upstream.py`, so the shim is documented here only.
