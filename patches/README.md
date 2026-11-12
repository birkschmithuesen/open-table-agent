# patches/

The patches in this directory modify Teable Community Edition and are licensed under AGPL-3.0
(same as upstream). The rest of this repository is MIT.

## What this series does

`0001-sql-query-route.patch` adds `POST /api/base/:baseId/sql-query`, a thin controller on top of
the existing CE `BaseSqlExecutorService` (`apps/nestjs-backend/src/features/base-sql-executor/`).
It is guarded by `@Permissions('base|query_data')`, not `base|read` (decision D-1,
`docs/decisions.md` / `docs/superpowers/specs/2026-11-12-open-table-agent-design.md` §12): CE's
own role matrix grants `base|query_data` to every role with `base|read` except Commenter, and
Teable's closed EE route uses the same permission. Using `base|read` would give Commenters SQL
access that Teable deliberately withholds from them.

## Layout

- `BASE`: the 40-hex upstream `teableio/teable` commit the series applies to.
- `NNNN-<slug>.patch`: `git format-patch` output (mbox, one commit per file), applied in lexical
  order with `git am --3way`.
- `tests/test_patch_series.py`: static checks (no checkout, no network) — the series applies to
  `BASE`, touches only the allow-listed paths, keeps the `base|query_data` permission, and this
  README keeps the AGPL-3.0 sentence above.

## Regenerating the series

```
git clone --shared --no-checkout https://github.com/teableio/teable.git .work/b-upstream   # or a local object store
git -C .work/b-upstream checkout --detach "$(cat patches/BASE)"
git -C .work/b-upstream am patches/*.patch
# edit the series under .work/b-upstream
git -C .work/b-upstream format-patch -o ../../patches "$(cat patches/BASE)"
```

`scripts/sync-upstream.py` (Chain C) re-applies the series against current upstream and records
the sha it actually used in `upstream.lock.json`; `patches/BASE` here is informational.
