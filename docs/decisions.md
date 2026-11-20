# Decisions (Birk, 2026-11-12)

1. **Teable stays the unmodified upstream Community Edition** (`teableio/teable`, AGPL-3.0) wherever possible.
   No long-lived fork.
2. **Full agent functionality, not a reduced tool set.** Target = the publicly documented tool list of
   Teable's official (licence-gated) MCP server: `list-bases`, `get-tables-meta`, `get-fields`,
   `get-records`, `sql-query`, `get-doc`, `search-api`, `call-api-read`, `create-records`,
   `update-records`, `delete-records`, `call-api-write` (source: `teableio/agent-skills` README, MIT).
   Safety comes from the token's permissions (the agent gets its own Teable user), not from fewer tools.
3. **Standalone MCP server** in this repo, talking to Teable's public REST API only.
4. **One small upstream patch** for what the API cannot do: an HTTP route for read-only SQL
   (`POST /api/base/:baseId/sql-query`) on top of the existing AGPL `BaseSqlExecutorService`
   (`apps/nestjs-backend/src/features/base-sql-executor/`). The route is marked
   "absent from the community build" in `apps/nestjs-backend/test/admin/table-route-ledger.ts`.
5. **No pull request to Teable** for now.
6. **Sync script** fetches upstream, re-applies our patch(es), reports conflicts, builds the patched tree.
7. **Not building on `ltphat2204/teable-mcp-server`** (small, unmaintained). Our own remote-mode code from
   that work may be ported (MIT, keep notice).
8. Working name `open-table-agent`; no "Teable" in the product name (brand clause in Teable's LICENSE §7(e)).
9. **Goes public** once the first version is merged and checked (Birk 2026-11-12): MCP server under MIT,
   the Teable patch under AGPL-3.0 (it modifies Teable). Gate before flipping visibility: copy check against
   the recovered closed reference (no verbatim/near-verbatim code), licence files present, no secrets,
   no instance or personal data in history.
10. **festival-desk consumes this repo as a pinned dependency**, never as copied code: `deploy/teable/` builds
    the patched Teable via `scripts/sync-upstream`, the MCP server runs as its own service (or is started by
    Hermes), version pinned to a tag of this repo.
11. **Auto `podman image prune -f` (dangling layers only) after every successful Chain-D build**
    (Factory-lead/Birk ruling, 2026-11-20). Never `-a`, never `system prune`; a failed build leaves
    everything untouched. See `scripts/podman_prune.py`, called from `e2e/stack.py` and
    `scripts/sync-upstream.py --build`.
