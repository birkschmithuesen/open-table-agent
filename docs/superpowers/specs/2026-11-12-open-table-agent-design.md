# open-table-agent — design spec

Date: 2026-11-12. Card: t_bd29c389. Status: design, no product code yet.
Binding input: `docs/decisions.md` (8 decisions, Birk 2026-11-12). They are not reopened here.

Notation: **[src: …]** names the source a decision rests on. **ANNAHME:** marks a fact that was not
verified in this run, plus what must be checked. **D-n:** a decision taken by Birk/Robo on a former open question
(section 12).

## 1. Goal and scope

An MCP client (Hermes first, any MCP client later) gets the 12 publicly documented tools of Teable's
licence-gated MCP server against a self-hosted Teable Community Edition (CE). Teable stays as close to
unmodified upstream as possible: one small AGPL patch, re-applied by a sync script.

In scope: MCP server (`server/`), upstream patch (`patches/`), sync script (`scripts/`), tests incl. one
end-to-end run against a real CE instance (`e2e/`), Hermes wiring doc (`docs/hermes.md`), `make test` / `make e2e`.

Out of scope: a PR to Teable; the Teable chat panel; deploying Teable for festival-desk; OAuth for the
MCP server (bearer tokens only); the 13th closed tool `query-data` (not in the public list, decision 2).

## 2. Facts measured in this run (2026-11-12)

| Fact | How measured |
|---|---|
| `teable-fork` `origin/develop` = `fc4126e945a212aa637c4134c373416df69bb982` (2026-11-11 10:14 +0800); local `develop` is 1 commit ahead (`2079432c9`, factory placeholder) | `git rev-parse`, `git log origin/develop..develop` |
| Upstream has no `v*` tags; tags are `release.<ISO>.<n>`, newest `release.2026-11-10T05-38-53Z.3830` → `10a97939` | `git for-each-ref refs/tags` |
| `BaseSqlExecutorModule` is imported by no module in `apps/nestjs-backend/src`; only `test/utils/init-app.ts:74,119` imports it | grep |
| `BaseSqlExecutorService.executeQuerySql(baseId, sql, opts?)` (`base-sql-executor.service.ts:349`) returns raw row objects; enforces SQL parse + function allow-list + table allow-list (`utils.ts:137`), forbids role switching (`utils.ts:13`), runs in a READ ONLY transaction with `statement_timeout`, and `SET LOCAL ROLE base_read_only_role_<baseId>` when the base data lives in the meta DB. No row limit. | read source |
| `PermissionGuard` and `AuthGuard` are global `APP_GUARD`s (`src/global/global.module.ts:126-133`); a controller only needs `@Permissions(...)` | read source |
| CE permission actions include both `base|read` and `base|query_data` (`packages/core/src/auth/actions.ts:35,43`). Role matrix (`packages/core/src/auth/role/constant.ts`): Owner/Creator/Editor/Viewer have both; **Commenter has `base|read` but `base|query_data: false`** (line 231). `base|query_data` is a token scope of level R (`access-token-scope.ts:62`). | grep |
| Route ledger: `test/admin/table-route-ledger.ts:72` `'POST /api/base/:baseId/sql-query': 'EE'` (TABLE_ROUTE_EDITIONS), `:145` `… : 'host'` (TABLE_ROUTE_LEDGER). `auditTableRoutes` (`test/admin/table-route-audit.ts:37-55`) reports `stale` = ledger keys that are applicable and not registered *anywhere in the app*; `'EE'` keys are not applicable for CE. | read source |
| CE REST (all under `/api`): `GET /base/access/all`, `GET /base/{baseId}/table`, `GET /table/{tableId}/field`, `GET|POST|PATCH /table/{tableId}/record`, `DELETE /table/{tableId}/record?recordIds=…`; token as `Authorization: Bearer` | `packages/openapi/src/**` route constants |
| CE serves `POST /api/v2/tables/updateRecords` (`record|update`) and `DELETE /api/v2/tables/deleteRecords` (`record|delete`), body carries `tableId` and a filter node (`apps/nestjs-backend/src/features/v2/v2.controller.ts:508-540`, `packages/v2/contract-http/src/contract.ts:146,173`) | read source |
| v2 filter node: condition `{fieldId, operator, value}`, group `{conjunction:'and'|'or', items|filterSet:[…]}`, `{not: node}`; field-reference values `{type:'field', fieldId}` (`packages/v2/core/src/queries/RecordFilterDto.ts:64-188`) | read source |
| OpenAPI served at `/redocs/swagger.json` (and Swagger UI `/docs`), on unless `API_DOC_DISENABLED=true` (`src/swagger.ts:77-110`, `configs/bootstrap.config.ts:45`); built from `@teable/openapi` registrations | read source |
| Dockerfile `dockers/teable/Dockerfile`: stages `deps` (`node:24.22.2-bookworm`, corepack pnpm@12.11.2, `pnpm fetch/install`, prisma generate), `builder`, `post-builder`, `gosu` (`tianon/gosu:1.19`), `runner` (`node:24.22.2-bookworm-slim`); uses `COPY --link` | grep |
| Teable pins `prisma` / `@prisma/client` 6.2.1 with `prisma-client-js` (`packages/db-main-prisma/package.json:60-61`, schema.prisma) — engines are downloaded from `binaries.prisma.sh` | read source |
| Egress: `https://binaries.prisma.sh/` **times out** for uid birk | `curl --max-time 10` → exit 28 |
| Prisma engines-version in upstream lock: `6.2.0-14.4123509d24aa4dede1e864b46351bf2790323b69` | `grep engines-version pnpm-lock.yaml` (lines 9281, 24940) |
| The download broker `/usr/local/bin/hermes-download` reaches `binaries.prisma.sh`. Checksum files exist at `…/all_commits/4123509d…/debian-openssl-3.0.x/{libquery_engine.so.node.gz,schema-engine.gz}.sha256`, each with the content `<hex>  ./debian-openssl-3.0.x/<file>.gz` (query engine `d75ffb69…ea188`, schema engine `17f75cc8…fb767`). The broker needs the output directory to exist already. | `hermes-download … --unverified -o .scratch/prisma-probe/…` → exit 0 |
| Redis is mandatory for CE (`BACKEND_CACHE_REDIS_URI`, `env.validation.schema.ts:115-118`) | read source |
| Host: git 2.39.5, Python 3.11.15, GNU Make 4.3, podman 4.3.1 (no images), `/usr/local/bin/docker-compose`, no psql/redis binaries; `/var/lib/admin-jobs-images/` does not exist | command output |
| `teableio/agent-skills` HEAD `01408885444a66f68b721d6eaae70159d3db7e3d` (2026-11-11), MIT ("Copyright (c) 2026"); 23 topic docs in `skills/teable-assistant-ops/api-reference/*.md` (≈123 kB) | `git clone` |
| npm: `@modelcontextprotocol/sdk` 1.32.2, `zod` 4.6.7, `vitest` 5.1.0, `@teable/openapi` 1.10.0 (MIT) | `npm view` |
| teable-mcp `wt/t_9b7b6010` is main + 4 commits `fc8dff1 f053f03 45f55f4 a015834`; ESM/NodeNext, `node:http`, `StreamableHTTPServerTransport({sessionIdGenerator: undefined, enableJsonResponse: true})` | `git log`, file reads |
| Hermes `mcp_servers` entries: stdio = `command`/`args`/`env`/`connect_timeout`/`enabled`; remote = `url` + `headers`, `${VAR}` interpolated from the profile `.env` (`hermes-agent/tools/mcp_tool_config.py:596-606`, `config.yaml:927-934`) | read source |

## 3. Architecture

```
Hermes / MCP client
   │ stdio (token from env)          │ HTTP POST /mcp (Authorization: Bearer <caller token>)
   ▼                                 ▼
server/  open-table-agent (TypeScript, @modelcontextprotocol/sdk)
   │  per call: TeableClient(token)  → REST /api/...  (+ /api/v2/tables/* , /redocs/swagger.json)
   ▼
Teable CE (upstream develop + patches/0001-sql-query-route.patch)  ── Postgres 15.4, Redis 7.2.4
```

The MCP server is a pure REST client. It holds no database credentials and no admin token. Every
permission decision is Teable's, made on the caller's token [src: decision 2, 3; closed reference
`backend-ee/src/features/mcp/mcp.service.ts` calls Teable's own REST API with the caller's bearer].

## 4. Part 1 — MCP server (`server/`)

### 4.1 Stack and package

- TypeScript, ESM (`"type": "module"`, `module`/`moduleResolution: NodeNext`, `target ES2022`, `strict`)
  [src: teable-mcp tsconfig, ported code stays drop-in].
- Runtime deps: `@modelcontextprotocol/sdk` ^1.32, `zod` ^4. Dev: `typescript` ^5.9, `vitest` ^5.1, `@types/node`.
  ANNAHME: SDK 1.32 accepts zod 4 raw shapes in `registerTool` (teable-mcp ran SDK 1.24.3 with zod 4.1.13) —
  check with the first tool test.
- HTTP client: Node's global `fetch` (Node ≥ 22; host has v22.23.1). axios and dotenv are dropped (fewer deps).
- `@teable/openapi` is **not** a dependency. Reason: the npm release (1.10.0) is published separately from
  CE `develop`, so its schemas can drift from the instance we talk to; and we need only ~10 response shapes.
  Local minimal types in `src/teable/types.ts` instead. `search-api` reads the instance's live spec (4.6).
- Package name/bin: `open-table-agent` (no "Teable" in the product name, decision 8). MCP `serverInfo.name`:
  `open-table-agent`. `"private": true`, `"engines": {"node": ">=22"}`, licence MIT.
- Repo licence: root `LICENSE` (MIT, "Copyright (c) 2026 open-table-agent contributors"). Ported files keep a
  header `// Portions Copyright (c) 2024 Teable MCP Server Contributors (MIT), ported from teable-mcp` and
  `server/THIRD_PARTY_NOTICES.md` carries the full teable-mcp MIT text and the agent-skills MIT text.

### 4.2 Module layout (one purpose per file)

| File | Purpose / interface |
|---|---|
| `src/config.ts` | `loadConfig(argv, env): Config` — `{transport:'stdio'|'http', teableUrl, token?, http:{host, port, allowedOrigins}, openapiUrl}`; throws `ConfigError` with a human message |
| `src/teable/client.ts` | `class TeableClient(token, teableUrl, {timeoutMs=120000, fetchImpl?})` with `request(method, path, {query?, body?}) → Promise<{status:number, data:unknown}>`; throws `TeableApiError{status, message, body}` for non-2xx; `path` is relative to `<teableUrl>/api` |
| `src/teable/types.ts` | minimal response types (base, table, field, record) |
| `src/teable/fields.ts` | `loadFields(client, tableId)`, `resolveFieldKey(fields, key) → fieldId` (exact id, else case-insensitive name, else `UnknownFieldError{key, suggestions}`), `mapFilterFieldIds(filter, fields)` (walks condition / group (`items` and `filterSet`) / `not` nodes and `{type:'field', fieldId}` values) |
| `src/result.ts` | `toToolResult(output)` (JSON text, 60 000-char cut with a note, `isError` when `success===false`), `errorResult(err)` |
| `src/openapi/index.ts` | `getApiIndex(client, openapiUrl) → ApiIndex` (fetch + parse + 10-min cache keyed by URL), `ApiIndex.search(query, {tags, limit})`, `ApiIndex.lookup(method, urlTemplate)` |
| `src/docs/index.ts` | `DOC_TOPICS` (23 keys), `readDoc(topic) → string` from `server/docs-bundle/<topic>.md` |
| `src/tools/<tool-name>.ts` | one file per tool, each `export const tool: ToolDef` |
| `src/tools/index.ts` | `export const TOOLS: ToolDef[]` — exactly the 12 |
| `src/tools/types.ts` | `ToolDef {name, title, description, inputSchema (zod raw shape), annotations, handler(args, ctx: {client, config}) → Promise<object>}` |
| `src/server.ts` | `createMcpServer(client, config) → McpServer` (ported from fc8dff1, changed: errors returned, not thrown) |
| `src/http.ts` | `createHttpRequestListener(opts)`, `startHttpServer(opts) → http.Server` (ported from f053f03, changed: bind host) |
| `src/index.ts` | CLI entry (ported from 45f55f4, changed: loud startup errors, env names) |
| `docs-bundle/*.md` + `docs-bundle/SOURCE.md` | 23 agent-skills topic docs copied verbatim at `01408885`, `SOURCE.md` names repo, sha, licence |

### 4.3 Configuration

| Variable / flag | Default | Meaning |
|---|---|---|
| `TEABLE_URL` | — (required) | Instance origin, e.g. `http://127.0.0.1:3000`. API base = `${TEABLE_URL}/api`. No default to a hosted instance. |
| `TEABLE_TOKEN` | — (required in stdio) | Personal access token. **Never read in HTTP mode.** |
| `--http` or `OTA_TRANSPORT=http` | stdio | transport choice [src: 45f55f4 logic, renamed env] |
| `OTA_HTTP_HOST` | `127.0.0.1` | bind address. Changed from teable-mcp, which bound all interfaces with no option. |
| `OTA_HTTP_PORT` | `3100` | port (Teable itself uses 3000) |
| `OTA_ALLOWED_ORIGINS` | empty | comma list; empty = Origin host must equal `Host` [src: f053f03] |
| `OTA_OPENAPI_URL` | `${TEABLE_URL}/redocs/swagger.json` | where `search-api` reads the spec |

Startup errors (missing `TEABLE_URL`, missing `TEABLE_TOKEN` in stdio, bad port) print one line
`open-table-agent: <message>` to stderr and exit 2. teable-mcp exited 1 silently.

### 4.4 Transports

- **stdio** (default): one `TeableClient(TEABLE_TOKEN)`, one `McpServer`, `StdioServerTransport`.
- **Streamable HTTP, stateless** (ported f053f03): `node:http`; per POST a fresh `TeableClient(<bearer>)`,
  `createMcpServer`, `StreamableHTTPServerTransport({sessionIdGenerator: undefined, enableJsonResponse: true})`;
  closed on `res` close. Routing: `/health` → `200 {"ok":true}` (no auth); path ≠ `/mcp` → 404; Origin check →
  403; method ≠ POST → 405 + `Allow: POST`; no `Authorization: Bearer …` → 401 `{"error":"Missing bearer token"}`;
  exception before headers → 500. [src: f053f03; the closed reference behaves the same way: stateless, POST only,
  405 with `Allow: POST`, JSON responses — `backend-ee/src/features/mcp/mcp.service.ts`]

### 4.5 Result and error convention

- Every tool handler returns a plain object; `toToolResult` serializes it as one `text` content item (JSON).
- Text longer than **60 000** characters is cut, and a note is appended saying how many characters were
  dropped and to narrow the query (projection / take / skip) [src: closed `mcp-result.ts`].
- `isError: true` iff the object has `success === false`.
- Teable HTTP errors and validation failures **never throw out of the tool**: `errorResult` produces
  `{success:false, status?, error:<Teable message or validation text>, hint?}` with `isError: true`.
  teable-mcp threw instead, which turned errors into protocol errors. That is changed here so the agent sees the
  Teable status (e.g. 403) and can react.
- Input size guard: a tool call whose arguments contain more than 100 000 array elements + object keys
  in total is rejected with `isError` before any request [src: closed `mcp.service.ts`, `MCP_MAX_TOOL_INPUT_ELEMENTS`].

### 4.6 The 12 tools

All 12 are always listed, for every token. **No tool is hidden by permission level** (decision 2: safety
from the token, not from fewer tools). This deliberately differs from the closed server, which hides
write tools for read-only tokens [src: closed `mcp-permission.ts`]. A call the token may not make
returns Teable's 403 as an `isError` result.

Annotations [src: closed `mcp-tool-catalog.ts` `buildAnnotations`]: every tool has a `title`; `openWorldHint:false`.
Read tools: `readOnlyHint:true, destructiveHint:false, idempotentHint:true`. Write tools: `readOnlyHint:false,
idempotentHint:false`; `destructiveHint:true` for `update-records`, `delete-records`, `call-api-write`;
`destructiveHint:false` for `create-records`.

| Tool | Input (zod) | Teable call | Output |
|---|---|---|---|
| `list-bases` | `search?` (case-insensitive on name or id), `spaceId?`, `limit` 1–100 =50, `offset` ≥0 =0 | `GET /base/access/all`, filtered + paged locally | `{success, offset, hasMore, nextOffset?, bases:[{id,name,spaceId,role}]}`; names > 200 chars clipped |
| `get-tables-meta` | `baseId`, `tableId?`, `tableName?` (exact; id wins) | `GET /base/{baseId}/table` | `{success, count, tables:[{id,name,dbTableName,description,icon}]}`; unknown id/name → `success:false` |
| `get-fields` | `tableId`, `fieldId?`, `fieldName?` | `GET /table/{tableId}/field` | `{success, count, fields:[full field objects incl. dbFieldName]}` |
| `get-records` | `tableId`, `viewId?`, `recordId?`, `take` 1–1000 =100, `skip?`, `projection?` (≤50 names/ids or `"all"`), `filter?` (v1 filter object, names allowed), `search?` `{value, field?}`, `orderBy?` `[{field, order:'asc'|'desc'}]` | `GET /table/{tableId}/record` (or `/record/{recordId}`) with `fieldKeyType=id`; `filter`/`orderBy` JSON-encoded after name→id mapping | tabular `{success, total, hint?, format:'tabular', header:['id',…names], rows:[[recId,…]], meta:{fields:{name:{id,type}}}}`; default projection = first 50 fields + hint; thumbnail URLs dropped |
| `sql-query` | `baseId`, `sql` | `POST /base/{baseId}/sql-query` body `{sql}` (patched route, Part 2) | `{success, rowCount, columnCount, columns, rows}`; columns = keys of first row |
| `get-doc` | `topic` (enum of the 23 bundled keys) | none (bundled) | `{success, topic, content}` |
| `search-api` | `query` (≥1 char), `tags?`, `limit` 1–10 =5 | instance OpenAPI (cached) | `{success, totalApiCount, results:[{method,url,summary,description,parameters,requestBody?}]}`; no hit → `availableTags` |
| `call-api-read` | `url` (template from search-api), `params?` | `GET` that endpoint | `{success, statusCode, data}` |
| `call-api-write` | `method` POST/PUT/PATCH/DELETE, `url`, `params?`, `data?` (object or JSON string) | that endpoint | `{success, statusCode, data}` |
| `create-records` | `tableId`, `header` (names/ids), `records` (2-D, header order), `typecast` =true | `POST /table/{tableId}/record` `{fieldKeyType:'id', typecast, records:[{fields}]}` | `{success, recordsCreated, recordIds, warnings?}` |
| `update-records` | `tableId` + exactly one mode: A `filter`+`fields`; B `header` (contains `recordId`) + `records`; `typecast` =true | A: `POST /v2/tables/updateRecords` `{tableId, filter, fields, typecast, fieldKeyType:'id'}`; B: `PATCH /table/{tableId}/record` `{fieldKeyType:'id', typecast, records:[{id, fields}]}` | A `{success, updatedCount}`; B `{success, updated, warnings?}` |
| `delete-records` | `tableId` + exactly one of `recordIds` (1–1000) or `filter` | ids: `DELETE /table/{tableId}/record?recordIds=…`; filter: `DELETE /v2/tables/deleteRecords` `{tableId, filter}` | `{success, deletedCount}` |

Details that carry design weight:

1. **Field names → field IDs** (card requirement; silent-failure risk otherwise). Wherever a tool accepts a
   field reference — `get-records` `projection`/`filter`/`search.field`/`orderBy`, `create-records` and
   `update-records` `header`/`fields` keys, `update-records`/`delete-records` `filter` — the server resolves it
   with `resolveFieldKey`: exact field id first, then case-insensitive name. An unresolvable key is an
   `isError` result listing up to 5 suggestions (substring match) and the table's field names; **the request is
   not sent**. The closed reference maps names for headers/projection only and requires IDs in filters
   [src: closed `ai-tools/src/tools/update-records/execute.ts`, `delete-records/execute.ts`]; mapping inside filters
   goes beyond it on purpose. Filter shapes: v1 `{conjunction, filterSet:[{fieldId, operator, value}]}` and v2
   `{conjunction, items:[…]}` / `{not:…}`; both carry the key in `fieldId`, so one walker serves both [src:
   `RecordFilterDto.ts:64-188`].
   ANNAHME: the v1 `GET /table/{tableId}/record?filter=` accepts the `{conjunction, filterSet}` JSON with field
   IDs and ignores unknown field keys silently (the reason for the card's warning) — the unit test only asserts
   that IDs are sent; the e2e test filters by a field *name* and checks the result set.
2. **Cell value handling** in `create-records`/`update-records` B [src: closed `ai-tools/src/tools/create-records/execute.ts`,
   `update-records/execute.ts`]: create omits `null`/`undefined`/`""` cells; update B treats `""` as "leave
   unchanged" and `null` as "clear". Row length ≠ header length → `isError` naming up to 3 rows, no request.
   Warnings: a field that was given a non-empty value but comes back empty is listed ("N value(s) not written"),
   checkbox `false` excluded.
3. **Mode exclusivity** for `update-records` (A xor B) and `delete-records` (ids xor filter): enforced before any
   request; both or neither → `isError`.
4. **`sql-query` description** tells the agent: PostgreSQL, single read-only `SELECT`/`WITH`; tables as
   `"<baseId>"."<dbTableName>"` (from `get-tables-meta`), columns as quoted `dbFieldName` (from `get-fields`);
   system columns `__id`, `__auto_number`, `__created_time`, `__last_modified_time`, `__created_by`,
   `__last_modified_by`; add `LIMIT`; timestamps are UTC. The server does **not** rewrite or limit the SQL —
   enforcement is Teable's (Part 2). Prefer `get-records` when record IDs are needed. [src: closed
   `mcp-tool-catalog.ts` sql description; agent-skills `guides/cli-reference.md` 44-54.]
   ANNAHME: `dbTableName` from `GET /base/{baseId}/table` is the bare table name, not `schema.table` — the closed
   description says it is already `schema.table`. The e2e test runs a query built exactly the way the tool
   description instructs; whichever form is true, the description is fixed to match before Chain D closes.
5. **`get-doc`**: topics = filename stems of `skills/teable-assistant-ops/api-reference/*.md` at agent-skills
   `01408885` (23: `automation.api automation.send-email automation.trigger field.basic field.colors
   field.formatting field.formula field.link field.lookup field.rollup field.select field.show-as field.simple
   integration.slack record.value-format reference.url scrape.datasets scrape.guide view.column view.filter
   view.group view.sort view.statistic`). No `baseId` argument: the closed server needs one only for the
   AI-config topics (`field.ai`, `app.ai`, `automation.ai`), which agent-skills deliberately does not ship.
6. **`search-api` index** [src: closed `ai-tools/src/openapi-index/parser.ts`, `search.ts`]: parse the spec into
   endpoints `METHOD:/path` for GET/POST/PUT/PATCH/DELETE, with parameters and JSON request-body properties
   (3 levels). Paths are normalized relative to `/api` (strip a leading `/api` if the spec includes it — ANNAHME:
   which form CE emits; the parser handles both and the unit fixture covers both). Scoring is our own,
   deterministic, no Fuse dependency: case-insensitive token match, weights summary 4, path 2, description 2,
   tags 1.5, method 0.5; ties by path. Unlike the closed index there is **no endpoint exclusion list and no
   per-tag permission filter** — the token decides (decision 2). The patched `sql-query` route is not in the CE
   spec (it is not registered in `@teable/openapi`), which is fine: it has its own tool.
7. **`call-api-read` / `call-api-write`** [src: closed `ai-tools/src/tools/call-api/execute.ts`,
   `openapi-index/validator.ts`]: the `METHOD:url` pair must exist in the index, otherwise `isError` "Unknown API —
   use search-api". This also blocks arbitrary paths (`..`, absolute URLs, other hosts). `params` whose name is a
   path parameter of the template are substituted URL-encoded; the rest become query parameters (arrays → repeated
   keys, objects → JSON). Missing required path/query params or required body → `isError` listing the parameters,
   no request. `call-api-read` forces GET. Response: `{success: 2xx, statusCode, data}`; on HTTP error `error` is
   Teable's message or the JSON body.

## 5. Part 2 — upstream patch (`patches/`)

### 5.1 Shared facts for Chains B and C (fixed here so neither decides it)

- Patch files: `patches/NNNN-<slug>.patch`, 4-digit, applied in lexical order; each is `git format-patch`
  output (mbox, one commit per file) created against the upstream sha in `patches/BASE`.
- `patches/BASE`: one line, the 40-hex upstream sha the series was last regenerated on
  (initially `fc4126e945a212aa637c4134c373416df69bb982`). Informational for C; C records the sha it really used.
- Application: `git am --3way` with committer identity `open-table-agent-sync <sync@open-table-agent.invalid>`.
- Patch identity in the lock file: sha256 of the patch file bytes.

### 5.2 `0001-sql-query-route.patch` content (AGPL-3.0)

1. **New** `apps/nestjs-backend/src/features/base-sql-executor/base-sql-query.controller.ts`:
   `@Controller('api/base/') class BaseSqlQueryController`, one route
   `@Post(':baseId/sql-query') @Permissions('base|query_data')`, body validated by `ZodValidationPipe` with an
   inline schema `{ sql: string (min 1), parameters?: unknown[] }`, calls
   `baseSqlExecutorService.executeQuerySql(baseId, sql, { parameters, structuredCoverage: true })` and returns
   `{ rows }` with values made JSON-safe (`bigint` → number if safe integer else string; objects with `toJSON`
   serialized). Response shape `{rows: object[]}` matches what CE's own generated v2 client already expects
   (`packages/v2/data-query/src/managedQueryTool.generated.ts:4903-4918`). Errors keep the service's
   `CustomHttpException` (not redacted — the agent needs the parser message to fix its SQL).
   ANNAHME: Postgres `count(*)` arrives as JS `bigint` through `$queryRawUnsafe` and Nest's JSON serializer
   throws on it — the e2e `SELECT count(*)` query proves the conversion is needed and works.
2. **Modify** `base-sql-executor.module.ts`: add `controllers: [BaseSqlQueryController]`.
3. **Modify** `apps/nestjs-backend/src/features/base/base.module.ts`: add `BaseSqlExecutorModule` to `imports`
   (BaseModule is already imported by `app.module.ts:77`; no `app.module.ts` change). This is the smallest
   wiring place found: one import line + one array entry.
4. **Modify** `apps/nestjs-backend/test/admin/table-route-ledger.ts`: delete the line
   `'POST /api/base/:baseId/sql-query': 'EE',`. Without this nothing fails (the `'host'` entry already covers the
   route), but with it removed the CE guard test `table-route-guard.e2e-spec.ts` reports the route as `stale` if
   our controller ever stops being registered — the upstream test suite then guards our patch for free.

Permission decision: **`base|query_data`**, not `base|read`. The brief says "base read permission". CE has a
dedicated read-level permission for exactly this (`query_data`, token scope level R). It is granted to every
role that has `base|read` except Commenter, whom Teable deliberately denies it. The closed EE route uses it
too [src: closed `backend-ee/src/features/override/controller/base.controller.ts`]. Using `base|read` would give
Commenters SQL access that Teable withholds from them. Consequence for setup: the agent's token must include the
`base|query_data` scope (docs/hermes.md). **Decided (D-1, section 12):** `base|query_data` stays.

Why a new controller file instead of a method on `BaseController`: `base.controller.ts` is a large, frequently
changing upstream file. A new file never conflicts on sync; only the two one-line module edits and the ledger
line can conflict.

`patches/README.md`: "The patches in this directory modify Teable Community Edition and are licensed under
AGPL-3.0 (same as upstream). The rest of this repository is MIT." plus how to regenerate (`git format-patch`
from a worktree on `BASE`).

## 6. Part 3 — sync script (`scripts/sync-upstream.py`)

Python 3.11 stdlib only (host has 3.11.15; testable with `unittest`, no deps).

```
scripts/sync-upstream.py [--upstream-url URL] [--ref develop | --tag TAG] [--dry-run]
                         [--build] [--podman-arg ARG]... [--work-dir .work] [--lock upstream.lock.json]
                         [--patches patches]
```

`--podman-arg` (repeatable) is inserted verbatim into the `podman build` command before the context path. It is
needed for the Prisma engine injection (section 8, D-2), e.g. `--podman-arg=--volume=<dir>:/ota-prisma:ro`
`--podman-arg=--env=PRISMA_QUERY_ENGINE_LIBRARY=/ota-prisma/…`. It does not change the upstream Dockerfile.

- Default URL `https://github.com/teableio/teable.git` (github.com reachable; codeload is not and is not used).
- Fetch: `git fetch <url> <ref>` into a bare cache `.work/upstream.git` (created on first run). The script
  resolves the sha **from what it fetched for the given ref on the given URL**, never from any local branch;
  this avoids the trap of `teable-fork`'s local `develop`, which carries an extra commit. `--tag` fetches `refs/tags/<TAG>`.
- Fresh worktree `.work/teable-<sha12>` (`git worktree add --detach`), removed and recreated if it exists.
- Apply `patches/*.patch` in order with `git am --3way`. On failure: print
  `CONFLICT patch=<file> path=<repo path> hunk=@@ <hunk header> @@` for every failing hunk (from
  `git apply --check -v` of the failing patch against the pre-patch tree), print the upstream sha, run
  `git am --abort`, **do not write the lock**, exit 1.
- On success: print `UPSTREAM <sha>` and `PATCHED <commit sha>` and `IMAGE localhost/ota-teable:<sha12>-<patchset8>`
  (patchset8 = first 8 hex of sha256 over the concatenated patch sha256s). Without `--build`, print the exact build
  command `podman build -f dockers/teable/Dockerfile -t <tag> <worktree>`; with `--build` run it (exit 3 on failure).
- Lock file `upstream.lock.json` (written only on success and not with `--dry-run`):
  ```json
  {"schema": 1,
   "upstream": {"url": "...", "ref": "develop", "sha": "<40 hex>"},
   "patches": [{"file": "0001-sql-query-route.patch", "sha256": "<64 hex>"}],
   "patched_commit": "<40 hex>",
   "image": {"tag": "localhost/ota-teable:<sha12>-<patchset8>", "built": false},
   "generated_at": "<UTC ISO-8601>"}
  ```
- Idempotent: if the lock matches (same url/ref/sha and same patch hashes) and the worktree exists at
  `patched_commit`, print `UP-TO-DATE <sha>` and exit 0 without touching anything (a `--build` still builds when
  `image.built` is false).
- `--dry-run`: fetch + apply in a throwaway worktree `.work/dry-run-<sha12>`, report, remove the worktree, never
  write the lock, never build. Exit codes are the same as for a real run.
- Exit codes: 0 ok / up to date, 1 conflict, 2 usage or environment error (git missing, no patches, fetch failed),
  3 build failed.

## 7. Part 4 — tests

### 7.1 Make layout

Top-level `Makefile` (written in this run) includes `mk/*.mk`. Each chain owns one fragment that appends its target
to `TEST_TARGETS` (and D to `E2E_TARGETS`). `make test` fails with exit 2 and a message when `TEST_TARGETS` is empty —
no silent green. Targeted runs: `make test <path>…` — extra goals are collected in `TEST_ARGS` and turned into no-op
phony goals. Fragments call `$(call ota_selected,<dir>)`, which returns the args under `<dir>/` (or `all` when no
args were given), and only register their target when it is non-empty. So a path selects only the owning chain.
A path outside the known roots (`OTA_ROOTS := server patches scripts e2e`) stops make with an error. So does a set
of paths that selects no registered fragment. Neither case runs as a silent skip. The roots list is the only line a
future chain would add to; no current chain needs to touch it.

Fragment contract (each chain writes its own):

```make
# mk/server.mk (Chain A) — pattern for all fragments
ifneq ($(call ota_selected,server),)
TEST_TARGETS += test-server
endif
.PHONY: test-server
test-server:
	cd server && npm ci --no-audit --no-fund && npx vitest run $(patsubst server/%,%,$(call ota_args,server))
```

`make test` needs no containers and no network except npm registry access for `npm ci` (dependency install) and
local git objects (Chain B reads the local `teable-fork` object store, see 7.3). `make e2e` is separate.

### 7.2 MUSTs with named mutations

Each MUST names one mutation and the test that turns red. The plan carries them into the task that implements
the MUST. Test files are relative to their chain root.

| ID | MUST | Mutation | Red test |
|---|---|---|---|
| S1 | `tools/list` returns exactly the 12 names, for every token | remove `call-api-write` from `TOOLS` | `server/test/tools-list.test.ts` › "lists exactly the 12 tools" |
| S2 | annotations as in 4.6 | set `delete-records` `destructiveHint:false` | `server/test/annotations.test.ts` › "write tools carry destructive/readOnly hints" |
| S3 | field names in filters/projection/headers become IDs; unknown name → isError, no request | make `mapFilterFieldIds` return its input | `server/test/fields.test.ts` › "maps names inside nested filter groups" and `server/test/get-records.test.ts` › "sends field IDs in filter" |
| S4 | HTTP mode forwards the caller's bearer and never uses `TEABLE_TOKEN` | build the client from `config.token` in `http.ts` | `server/test/http.test.ts` › "forwards caller bearer to Teable" |
| S5 | HTTP: no bearer → 401, GET → 405 `Allow: POST`, foreign Origin → 403, default bind 127.0.0.1 | delete the 401 branch | `server/test/http.test.ts` › "rejects missing bearer with 401" |
| S6 | Teable errors come back as `isError` results carrying the status | rethrow in `server.ts` handler | `server/test/server.test.ts` › "Teable 403 becomes isError result with status" |
| S7 | output > 60 000 chars is cut with a note | raise the limit to 600 000 | `server/test/result.test.ts` › "truncates at 60000 chars" |
| S8 | call-api-* only call indexed `METHOD:url` pairs; path params URL-encoded | skip `lookup` | `server/test/call-api.test.ts` › "rejects unknown endpoint without a request" |
| S9 | `get-doc` serves all 23 topics, rejects others | delete `docs-bundle/view.sort.md` | `server/test/get-doc.test.ts` › "every topic resolves" |
| S10 | `sql-query` posts `{sql}` to `/base/{baseId}/sql-query` and returns rows/columns | change path to `/base/{baseId}/sql` | `server/test/sql-query.test.ts` › "posts sql to the patched route" |
| S11 | create/update: row length ≠ header length → isError, no request | remove the length check | `server/test/create-records.test.ts` › "rejects ragged rows without a request" |
| S12 | update/delete mode exclusivity | accept both `filter` and `recordIds` | `server/test/delete-records.test.ts` › "rejects filter plus recordIds" |
| S13 | startup without `TEABLE_URL` prints `open-table-agent: …` to stderr, exit 2 | swallow the error and exit 1 silently | `server/test/cli.test.ts` › "fails loudly without TEABLE_URL" |
| P1 | patch applies cleanly to `patches/BASE` | change one context line in the patch's `base.module.ts` hunk | `patches/tests/test_patch_series.py` › `test_applies_to_base` |
| P2 | route is `POST :baseId/sql-query` guarded by `@Permissions('base|query_data')` | change to `@Permissions('base|read')` | `patches/tests/test_patch_series.py` › `test_route_permission` |
| P3 | patch touches only the 4 allow-listed paths | add a hunk to `app.module.ts` | `patches/tests/test_patch_series.py` › `test_touches_only_allowlisted_paths` |
| P4 | `patches/README.md` states AGPL-3.0 | delete the AGPL sentence | `patches/tests/test_patch_series.py` › `test_readme_states_agpl` |
| C1 | clean series → exit 0, lock with upstream sha + patch sha256 | skip writing `patches[]` | `scripts/tests/test_sync_upstream.py` › `test_clean_apply_writes_lock` |
| C2 | broken hunk context → exit 1, `CONFLICT patch=… path=… hunk=…`, no lock | ignore `git am` exit status | `scripts/tests/test_sync_upstream.py` › `test_broken_context_reports_conflict` |
| C3 | sha comes from the fetched ref, not a local branch | resolve `develop` in the fixture's local clone instead of the fetched ref | `scripts/tests/test_sync_upstream.py` › `test_ignores_local_branch_with_extra_commit` |
| C4 | second run is a no-op `UP-TO-DATE` | always recreate the worktree | `scripts/tests/test_sync_upstream.py` › `test_second_run_is_up_to_date` |
| C5 | `--dry-run` writes no lock and leaves no worktree | write lock in dry run | `scripts/tests/test_sync_upstream.py` › `test_dry_run_leaves_no_trace` |
| M1 | `make test` with no registered targets fails; an unowned path argument fails | make the empty check `true` | verified in this run: `make test` → exit 2 `make test: FAIL - no test target selected …`; `make test srver/x` → exit 2 `path argument(s) outside …` (plan, Chain 0) |
| E1 | real CE: `tools/list` has 12 tools (stdio and HTTP) | build the server with `get-doc` removed from `TOOLS` | `e2e/tests/acceptance.e2e.test.ts` › "lists 12 tools" |
| E2 | `get-records` + `create-records` round trip, filter by field *name* | drop name mapping (S3 mutation) | same file › "create then read back by field name filter" |
| E3 | `sql-query` returns rows incl. `count(*)` through the patched route; refused (isError, 403) for a token without base access | remove the controller from the patch (no route → 404) | same file › "sql-query returns rows" and "sql-query refused without base access" |
| E4 | `sync-upstream` applies the series on current upstream `develop` and reports the sha | run it with a copy of the series whose `base.module.ts` hunk context is altered → must exit 1 with `CONFLICT` | `e2e/tests/test_sync_real.py` › `test_real_develop_applies` / `test_real_develop_broken_copy_conflicts` |

### 7.3 Test strategy per chain

- **A (unit):** vitest. Teable is stubbed by a local `node:http` server on `127.0.0.1:0` that records method,
  path, query, body and `Authorization`, and serves canned JSON fixtures [src: teable-mcp `tests/http-server.test.ts`
  stub pattern]. Tools are exercised through a real MCP client from the SDK (`Client` + `InMemoryTransport`) so
  schemas and annotations are tested as the client sees them. ANNAHME: `InMemoryTransport` is exported by SDK 1.32
  (`@modelcontextprotocol/sdk/inMemory.js`) — fall back to the HTTP transport if not.
- **B (static):** python unittest. Applies the series with `git apply --cached --check` against a temporary index
  built from `patches/BASE` (`GIT_DIR=<teable-fork>/.git GIT_INDEX_FILE=<tmp> git read-tree <BASE>`). That needs
  only the local object store, with no checkout and no network. The upstream repo path comes from `OTA_UPSTREAM_GIT_DIR`,
  default `/mnt/HC_Volume_106183673/projekte/teable-fork/.git`. If the path or the sha is missing, the test fails
  with a message; it is never skipped. Runtime behaviour of the controller (types, permission, rows) is proven
  in D. ANNAHME: no CE type check runs before D — the Dockerfile builds with `NEST_BUILD_TYPE_CHECK=0`, so Chain B
  must also run `tsc --noEmit` on the patched backend if a usable install exists (B's Task 3; `pnpm install
  --ignore-scripts` avoids the Prisma engine download, see D-2).
- **C (unit, offline):** each test builds a throwaway "upstream" git repo in a temp dir (file URL), a patch made
  with `git format-patch` from it, and runs the script as a subprocess. A mutation fixture breaks one context line
  to force the conflict.
- **D (e2e, containers):** see section 8.

## 8. Part 4b — how the patched Teable runs for e2e

Constraints (measured): no images in podman; `ghcr.io`, `registry-1.docker.io` and `codeload.github.com` are
unreachable; images come only via the admin job `image-holen` (Birk taps); `binaries.prisma.sh` is unreachable.

Options considered:

- **(a) Build the patched tree's own Dockerfile with podman** (base images via image-holen). This is what the sync
  script's `--build` produces, so the e2e run exercises the real deployment artefact. Costs 5 image fetches and a long
  build (`pnpm -r run build` of the monorepo).
- **(b) Run the patched backend from source** (`pnpm`, host node 22 vs `.nvmrc` 24.22.2) against Postgres + Redis
  containers. Needs only 2 images. But `pnpm install` + `prisma generate` hit the same unreachable prisma host, the
  node version mismatches the pin, and it is not what gets deployed.
- **(c) Prebuilt upstream CE image** — cannot contain our patch. Rejected.

**Decision: (a).** It gives a single artefact for the sync script, the e2e run and a later deployment, and
the Node version matches the pin. (b) has the same prisma blocker and fewer guarantees.

Run shape: `e2e/stack.py up|down|status` (stdlib Python, plain `podman` commands, no compose socket) creates a
pod `ota-e2e` publishing `127.0.0.1:3010→3000`, with `docker.io/library/postgres:15.4`, `docker.io/library/redis:7.2.4`
and the patched image tag read from `upstream.lock.json`. Env: `PRISMA_DATABASE_URL`, `BACKEND_CACHE_REDIS_URI`,
`PUBLIC_ORIGIN=http://127.0.0.1:3010`, `SECRET_KEY` (random per run), mirroring the probe compose
`/home/birk/scratch/teable-probe/docker-compose.yaml`. Bootstrap via REST: sign up user A (agent), create space +
base + table with fields `Name` (text) and `Count` (number), create token A with scopes incl. `base|query_data`,
`record|*`, `table|read`, `field|read`; sign up user B with no access to that base, token B. ANNAHME: sign-up and
access-token endpoints and their bodies (`packages/openapi/src/auth/signup.ts`, `access-token/create.ts`) and that
sign-up needs no email verification on CE — verify in Chain D Task D3 against the source before writing the bootstrap.

**Prisma engines (D-2).** Egress to `binaries.prisma.sh` is **not** requested. The two engines for
engines-version `4123509d24aa4dede1e864b46351bf2790323b69`, platform `debian-openssl-3.0.x`, come through the download
broker:
1. Fetch `<file>.gz.sha256` with `hermes-download <url> --unverified -o <path>`.
2. Fetch `<file>.gz` with `hermes-download <url> --sha256 <hex from step 1> -o <path>` (exit 4 on mismatch).
3. Gunzip into a cache outside git: `.work/prisma-engines/4123509d…/` (ignored), as
   `libquery_engine-debian-openssl-3.0.x.so.node` and `schema-engine-debian-openssl-3.0.x` (+x).

Base URL `https://binaries.prisma.sh/all_commits/<hash>/debian-openssl-3.0.x/`, files `libquery_engine.so.node.gz`
and `schema-engine.gz` (layout measured, section 2).

Injection into the unmodified upstream Dockerfile goes through `sync-upstream.py --podman-arg`: a read-only build
volume carrying the cache, plus `PRISMA_QUERY_ENGINE_LIBRARY` / `PRISMA_SCHEMA_ENGINE_BINARY` pointing into it.
ANNAHME (two unknowns, measured first in Chain D Task 1 before the full build):
- (i) Prisma 6.2.1 `prisma generate` honours these env vars and makes no download;
- (ii) `podman build --env` / `--volume` reach the Dockerfile's `RUN` steps in podman 4.3.1.

Fallbacks, in order:
- (a) a local `PRISMA_ENGINES_MIRROR` (`python3 -m http.server` over the cache in mirror layout, with
  `podman build --network=host`);
- (b) extract the engines from an upstream Teable image fetched via image-holen.

This is not a blocker for Chains A–C.

**image-holen (D-3).** The admin job (merge card t_296d1445, chain t_ba874608) accepts `ghcr.io/…` and `docker.io/…`
refs with a tag or `@sha256:`. Submit: `~/.hermes/profiles/birk/scripts/admin-job-submit.py image-holen <ref> --key
<unique-key>`. Result: `/var/spool/admin-jobs/done/<key>.json(l)`, tarball under `/var/lib/admin-jobs-images/`, then
`podman load -i <tarball>`. It is live only after Birk's admin install of that merge. Until then Chain D blocks with
`kanban_block(kind="dependency")` on t_296d1445; it does not fail.

Admin steps for Birk (preconditions of Chain D, not agent work):
1. Review, merge (card t_296d1445) and admin-install the `image-holen` job.
2. Approve 5 fetches (taps), submitted by the Chain D agent: `docker.io/library/node:24.22.2-bookworm`,
   `docker.io/library/node:24.22.2-bookworm-slim`, `docker.io/tianon/gosu:1.19`, `docker.io/library/postgres:15.4`,
   `docker.io/library/redis:7.2.4`. A 6th only if fallback (b) is needed: an upstream Teable image (`ghcr.io/teableio/…`).

ANNAHME: podman 4.3.1 (buildah 1.28) builds `COPY --link` and the build container reaches `registry.npmjs.org`
— Chain D Task D1 (its probe Containerfile uses `COPY --link`) checks this before the full build.

Chain D task order: D0 gate on t_296d1445 + 5 image fetches → D1 Prisma engines + injection measurement → D2 real
sync + patched image build → D3 pod + bootstrap → D4 acceptance tests.

## 9. Part 5 — Hermes wiring (`docs/hermes.md`, Chain A)

Content to write:
- Agent identity: a dedicated Teable user (e.g. `agent@<domain>`), invited to the spaces/bases it may touch with
  the lowest sufficient role; a personal access token of that user with exactly the scopes it needs
  (`base|read`, `base|query_data`, `table|read`, `field|read`, `record|read`, plus `record|create|update|delete`
  for write access). The token lives in the Hermes profile `.env` as `OTA_TEABLE_TOKEN`, never in `config.yaml`.
- stdio entry (Hermes on the same host):
  ```yaml
  mcp_servers:
    open-table-agent:
      command: node
      args: [/mnt/HC_Volume_106183673/projekte/open-table-agent/server/dist/index.js]
      env: {TEABLE_URL: "http://127.0.0.1:3000", TEABLE_TOKEN: "${OTA_TEABLE_TOKEN}"}
      connect_timeout: 30.0
      enabled: true
  ```
- HTTP entry (server started with `--http`, bound to 127.0.0.1 or a Tailscale address via `OTA_HTTP_HOST`):
  ```yaml
  mcp_servers:
    open-table-agent-http:
      url: "http://127.0.0.1:3100/mcp"
      headers: {Authorization: "Bearer ${OTA_TEABLE_TOKEN}"}
      enabled: true
  ```
  ANNAHME: Hermes interpolates `${VAR}` in stdio `env` values as it does for `url`/`headers`
  (`mcp_tool_config.py` resolves placeholders recursively, lines 565ff) — Chain A verifies with `hermes` config
  validation if available, otherwise states it as an assumption in the doc.
- How to check: `tools/list` shows 12 tools; a write tool triggers Hermes' confirmation because of the annotations.

## 10. Repository layout and chain ownership

| Path | Owner |
|---|---|
| `Makefile`, `.gitignore` (root: `.scratch/`, `.work/`), `docs/superpowers/**`, `docs/spec.md`, `docs/plan.md`, `docs/decisions.md` | this run (frozen afterwards; changes go through a new card) |
| `server/**`, `mk/server.mk`, `docs/hermes.md`, `LICENSE` | Chain A |
| `patches/**`, `mk/patches.mk` | Chain B |
| `scripts/sync-upstream.py`, `scripts/tests/**`, `mk/sync.mk` | Chain C |
| `e2e/**`, `mk/e2e.mk`, `upstream.lock.json` (first real sync), `README.md` (status line) | Chain D |

## 11. Behaviour taken from the closed reference

Behaviour only; no code copied. Paths are relative to `/home/birk/scratch/teable-closed-reference/backend-ee/`.

| Behaviour | Reference file |
|---|---|
| Stateless Streamable HTTP, POST only, 405 + `Allow: POST`, JSON responses, fresh server per request | `src/features/mcp/mcp.service.ts`, `src/features/mcp/mcp.controller.ts` |
| Tools call Teable's own REST API with the caller's bearer; all API permission checks apply; 120 s timeout | `src/features/mcp/mcp.service.ts` |
| Tool-input size cap of 100 000 elements + keys | `src/features/mcp/mcp.service.ts` (`MCP_MAX_TOOL_INPUT_ELEMENTS`) |
| Result = one JSON text item; 60 000-char cut with a note; `isError` when `success===false`; thrown errors → `{success:false,error}` | `src/features/mcp/mcp-result.ts` |
| Annotations: read tools readOnly/idempotent; write tools not; destructive for `delete-*` and explicitly marked; `openWorldHint` false; titles | `src/features/mcp/mcp-tool-catalog.ts` (`buildAnnotations`, `TOOL_TITLES`) |
| Server instructions: hierarchy space→base→table; start with list-bases/get-tables-meta; get-fields before writes; update/delete modes; search-api → call-api for the rest (paraphrased into our own text) | `src/features/mcp/mcp-tool-catalog.ts` (`buildServerInstructions`) |
| Permission tiers hide tools (we deliberately do **not** adopt this) | `src/features/mcp/mcp-permission.ts`, `mcp.service.ts` (`resolvePermissionLevel`) |
| `list-bases` inputs (search/spaceId/limit/offset), paging, 200-char name clip, output fields | `src/features/mcp/mcp-tool-catalog.ts` (`listBasesSpec`) |
| `get-tables-meta` inputs and output fields incl. `dbTableName` | `packages/ai-tools/src/tools/get-tables-meta/execute.ts` |
| `get-fields` returns full field objects, optional id/name filter | `packages/ai-tools/src/tools/get-fields/execute.ts` |
| `get-records` tabular output, take 1–1000 default 100, projection ≤50 or "all", first-50 default with hint, search tuple, thumbnail removal | `packages/ai-tools/src/tools/get-records/execute.ts`, `packages/ai-tools/src/core/response-compressor.ts` |
| `sql-query` input `sql`, output rowCount/columnCount/columns/rows, dialect guidance, dedicated tool because the endpoint is POST | `packages/ai-tools/src/tools/sql-query/execute.ts`, `src/features/mcp/mcp-tool-catalog.ts` |
| sql-query route guarded by `base|query_data`, rows made JSON-safe | `src/features/override/controller/base.controller.ts` |
| `get-doc` topic enum and bundled markdown | `packages/ai-tools/src/tools/get-doc/execute.ts`, `packages/ai-tools/src/docs/index.ts` |
| `search-api` index from the instance's OpenAPI doc, endpoint id `METHOD:/path`, params + body props 3 levels, field weighting, limit 1–10 default 5, no-hit `availableTags` | `packages/ai-tools/src/openapi-index/parser.ts`, `search.ts`, `packages/ai-tools/src/tools/search-api/execute.ts` |
| call-api: endpoint must be in the index; path vs query param split; arrays repeated, objects JSON; required-param validation; `{success,statusCode,data}` | `packages/ai-tools/src/tools/call-api/execute.ts`, `packages/ai-tools/src/openapi-index/validator.ts` |
| `create-records` header/records/typecast default true, ragged-row error, name→id with suggestions, empty cells omitted, "not written" warnings | `packages/ai-tools/src/tools/create-records/execute.ts`, `packages/ai-tools/src/utils/common.util.ts` |
| `update-records` two exclusive modes, filter mode via `/v2/tables/updateRecords`, `""` = unchanged / `null` = clear in fixed-record mode | `packages/ai-tools/src/tools/update-records/execute.ts` |
| `delete-records` ids (1–1000) xor filter, filter mode via `/v2/tables/deleteRecords` | `packages/ai-tools/src/tools/delete-records/execute.ts` |

## 12. Decided

Former open questions FRAGE-1..3, answered 2026-11-12 02:30 by Robo for Birk (operator note on card t_bd29c389;
technical decisions, binding). No open questions remain.

- **D-1 (was FRAGE-1):** the SQL route keeps `@Permissions('base|query_data')`. Reason: it matches Teable's own
  permission model, and Commenters must not run SQL. Affects section 5.2 (patch), section 9 (token scopes) and MUST P2.
- **D-2 (was FRAGE-2):** no egress request for `binaries.prisma.sh`. The Prisma 6.2.1 engines (engines-version
  `4123509d24aa4dede1e864b46351bf2790323b69`, `debian-openssl-3.0.x`) are fetched through `hermes-download`. Each is
  verified against the `.sha256` file Prisma publishes next to it (that file is fetched with `--unverified`), stored
  in a cache outside git, and injected into the build via `PRISMA_QUERY_ENGINE_LIBRARY` /
  `PRISMA_SCHEMA_ENGINE_BINARY` or a local `PRISMA_ENGINES_MIRROR`. Whether 6.2.1's `generate` honours these is
  unverified, so Chain D Task 1 measures it first. Fallback: extract the engines from an upstream Teable image fetched
  via image-holen. Not a blocker. Affects section 6 (`--podman-arg`), section 8 and Chain D Task 1.
- **D-3 (was FRAGE-3):** image-holen (chain t_ba874608, merge card t_296d1445, in review) accepts `ghcr.io/…` and
  `docker.io/…` refs with a tag or `@sha256:`. Submit with `~/.hermes/profiles/birk/scripts/admin-job-submit.py
  image-holen <ref> --key <unique-key>`. The result is in `/var/spool/admin-jobs/done/<key>.json(l)`, the tarball
  under `/var/lib/admin-jobs-images/`, then `podman load -i <tarball>`. It is live only after Birk's admin install of
  that merge. Chain D's first step is `kanban_block(kind="dependency")` on t_296d1445 rather than failing.
  Affects section 8 and Chain D.
