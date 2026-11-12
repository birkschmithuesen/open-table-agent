# open-table-agent server

An MCP server that gives an AI agent access to a self-hosted Teable instance. It exposes 12 tools over
stdio or stateless Streamable HTTP. Safety comes from the token you give it: all 12 tools are always
listed, and a call the token may not make returns Teable's 403 as an error result.

## Install

Requires Node.js 22 or newer.

```
npm ci --prefix server
npm run build --prefix server
```

The build writes `server/dist/index.js` (bin name `open-table-agent`).

## Configuration

| Variable / flag | Default | Meaning |
|---|---|---|
| `TEABLE_URL` | required | Instance origin, e.g. `http://127.0.0.1:3000`. The API base is `${TEABLE_URL}/api`. |
| `TEABLE_TOKEN` | required in stdio mode | Personal access token. Never read in HTTP mode. |
| `--http` or `OTA_TRANSPORT=http` | stdio | Select the HTTP transport. |
| `OTA_HTTP_HOST` | `127.0.0.1` | Bind address (HTTP mode). |
| `OTA_HTTP_PORT` | `3100` | Port (HTTP mode). `0` picks a free port. |
| `OTA_ALLOWED_ORIGINS` | empty | Comma-separated list of allowed `Origin` values. Empty means the Origin host must equal the `Host` header. |
| `OTA_OPENAPI_URL` | `${TEABLE_URL}/redocs/swagger.json` | Where `search-api` reads the OpenAPI spec. |

Startup errors (missing `TEABLE_URL`, missing `TEABLE_TOKEN` in stdio mode, invalid port) print one line
`open-table-agent: <message>` to stderr and exit with code 2.

## Run

stdio:

```
TEABLE_URL=http://127.0.0.1:3000 TEABLE_TOKEN=<token> node server/dist/index.js
```

HTTP:

```
TEABLE_URL=http://127.0.0.1:3000 node server/dist/index.js --http
```

## HTTP transport

Stateless Streamable HTTP on `http://<OTA_HTTP_HOST>:<OTA_HTTP_PORT>/mcp`. Each request gets a fresh
Teable client, MCP server and transport, so no session state is kept. The server never uses
`TEABLE_TOKEN` in this mode: the caller's bearer token is forwarded to Teable.

| Request | Response |
|---|---|
| `GET /health` | `200 {"ok":true}`, no authentication |
| any path other than `/mcp` | `404` |
| `Origin` not allowed | `403 {"error":"Origin not allowed"}` |
| method other than `POST` on `/mcp` | `405` with `Allow: POST` |
| no `Authorization: Bearer <token>` | `401 {"error":"Missing bearer token"}` |
| exception before headers are sent | `500` |

Requests without an `Origin` header always pass the origin check. By default the server binds to
`127.0.0.1`; set `OTA_HTTP_HOST` to expose it on another interface (for example a Tailscale address) and
put it behind a trusted network or reverse proxy.

Example call:

```
curl -s http://127.0.0.1:3100/mcp \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Tools

| Tool | Kind | Purpose |
|---|---|---|
| `list-bases` | read | List accessible bases, with optional search and paging. |
| `get-tables-meta` | read | List the tables of a base (id, name, `dbTableName`). |
| `get-fields` | read | List the fields of a table. |
| `get-records` | read | Read records with projection, filter, search and ordering. Field names are mapped to ids. |
| `sql-query` | read | Run a read-only PostgreSQL `SELECT`/`WITH` against a base (needs the patched Teable route). |
| `get-doc` | read | Return one of the 23 bundled Teable API reference topics. |
| `search-api` | read | Search the instance OpenAPI spec for endpoints. |
| `call-api-read` | read | Call a GET endpoint found with `search-api`. |
| `create-records` | write | Create records from a header and a 2-D list of rows. |
| `update-records` | write (destructive) | Update by filter, or by `recordId` rows. |
| `delete-records` | write (destructive) | Delete by record ids or by filter. |
| `call-api-write` | write (destructive) | Call a POST/PUT/PATCH/DELETE endpoint found with `search-api`. |

Every tool carries a `title` and annotations. Read tools set `readOnlyHint: true`; write tools set
`readOnlyHint: false`, with `destructiveHint: true` for `update-records`, `delete-records` and
`call-api-write`. Errors, including Teable HTTP errors, are returned as `isError` results with the Teable
status, never as protocol errors. Output longer than 60 000 characters is cut with a note.

## Tests

```
npm test --prefix server
```

## Licence

The server is MIT licensed. Parts are ported from teable-mcp (MIT, Copyright (c) 2024 Teable MCP Server
Contributors); those files carry the header `Portions Copyright (c) 2024 Teable MCP Server Contributors (MIT),
ported from teable-mcp`. The documents in `server/docs-bundle/` come from teableio/agent-skills; see
`server/docs-bundle/SOURCE.md` and `server/THIRD_PARTY_NOTICES.md`. The `patches/` directory of the
repository is AGPL-3.0 and is separate from this package.
