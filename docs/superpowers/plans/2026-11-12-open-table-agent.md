# open-table-agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An MCP server with Teable's 12 public agent tools against self-hosted Teable CE. It is backed by one AGPL upstream patch (`POST /api/base/:baseId/sql-query`), a sync script that re-applies the patch on upstream, and unit + end-to-end tests.

**Architecture:** `server/` is a standalone TypeScript MCP server (stdio + stateless Streamable HTTP). It talks only to Teable's REST API with the caller's token. `patches/` holds `git format-patch` files against upstream `teableio/teable`. `scripts/sync-upstream.py` fetches upstream, applies the series in a fresh worktree, writes `upstream.lock.json` and builds the patched image. `e2e/` runs the patched image with podman and drives the server through a real MCP client.

**Tech Stack:** Node ≥ 22, TypeScript 5.9 (ESM/NodeNext), `@modelcontextprotocol/sdk` ^1.32, `zod` ^4, `vitest` ^5.1; Python 3.11 stdlib (`unittest`); git 2.39; podman 4.3.1; GNU Make 4.3.

**Spec:** `docs/superpowers/specs/2026-11-12-open-table-agent-design.md` (below: "spec §N"). MUST ids (S1…, P1…, C1…, E1…) refer to spec §7.2.

## Global Constraints

- Binding decisions: `docs/decisions.md` (8 decisions). Never reopen them.
- Product name `open-table-agent`; no "Teable" in product/package/bin names (decision 8). Env var names may say `TEABLE_`.
- Licence of this repo: MIT. `patches/**` are AGPL-3.0. Ported teable-mcp code keeps the header `// Portions Copyright (c) 2024 Teable MCP Server Contributors (MIT), ported from teable-mcp`.
- Closed reference (`/home/birk/scratch/teable-closed-reference/`): behaviour only, **no verbatim or near-verbatim code**. Only the spec §11 behaviours are used, and the plan quotes none of its code.
- The AGPL CE source (`/mnt/HC_Volume_106183673/projekte/teable-fork`) may only be copied into `patches/`.
- `make test` needs no containers and no network beyond the npm registry for `npm ci`; containers only in `make e2e`.
- Each chain edits only the files it owns (spec §10). Nobody edits the top-level `Makefile`.
- Agent shell rules (cc-run): one command per Bash call, no `cd`, no `&&`/`;`, no `$VAR`, no `$( )`; recipes inside `mk/*.mk` may use shell freely.
- Facts marked **ANNAHME:** are unverified; the task that relies on one names the check.
- Test command for every chain: `make test` (targeted: `make test <path>`).
- Commits: one per finished task, on the chain's branch, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No merge, no push.

## File structure (all chains)

```
Makefile                         (done, this run)  top-level, includes mk/*.mk
LICENSE                          A   MIT
mk/server.mk                     A   registers test-server
server/package.json, package-lock.json, tsconfig.json, vitest.config.ts, .gitignore      A
server/THIRD_PARTY_NOTICES.md    A   teable-mcp MIT + agent-skills MIT texts
server/README.md                 A   usage
server/src/config.ts             A   env/argv → Config
server/src/index.ts              A   CLI entry (stdio | http)
server/src/http.ts               A   stateless Streamable HTTP (ported)
server/src/server.ts             A   createMcpServer (ported factory)
server/src/result.ts             A   toToolResult / errorResult / input-size guard
server/src/teable/client.ts      A   TeableClient (fetch)
server/src/teable/types.ts       A   minimal response types
server/src/teable/fields.ts      A   field loading + name→id mapping
server/src/openapi/index.ts      A   OpenAPI index: parse, search, lookup
server/src/docs/index.ts         A   DOC_TOPICS + readDoc
server/src/tools/types.ts        A   ToolDef
server/src/tools/index.ts        A   TOOLS (12)
server/src/tools/<12 files>.ts   A   one per tool
server/docs-bundle/*.md          A   23 topics + SOURCE.md (agent-skills @01408885)
server/test/helpers/*.ts         A   stub Teable + MCP client harness
server/test/*.test.ts            A
docs/hermes.md                   A
patches/BASE, README.md, 0001-sql-query-route.patch          B
patches/tests/test_patch_series.py                           B
mk/patches.mk                    B
scripts/sync-upstream.py         C
scripts/tests/test_sync_upstream.py, scripts/tests/fixtures.py   C
mk/sync.mk                       C
.gitignore                       C   (.work/)
e2e/stack.py, e2e/bootstrap.py   D
e2e/package.json, package-lock.json, tsconfig.json, vitest.config.ts     D
e2e/tests/acceptance.e2e.test.ts, e2e/tests/test_sync_real.py            D
mk/e2e.mk                        D
upstream.lock.json               D   (written by the first real sync)
README.md                        D   (status line)
```

---

## Chain 0 — this run (done)

Owned: `Makefile`, `docs/superpowers/**`, `docs/spec.md`, `docs/plan.md`. Base: `main`.

Verification (run in this run, 2026-11-12):

- `make test` → exit 2, stderr `make test: FAIL - no test target selected (mk/*.mk registered none)` (MUST M1).
- With two demo fragments (`.scratch/mkdemo/mk/{server,sync}.mk`, not committed):
  `make -C .scratch/mkdemo -f <repo>/Makefile test server/test/http.test.ts` → only `test-server` runs, `make test: OK (test-server)`.
  A full run where one fragment fails → exit 2.
  `make … test srver/typo.ts` → exit 2 `path argument(s) outside server patches scripts e2e: srver/typo.ts`.
  `make … e2e` → exit 2 `make e2e: FAIL - no e2e target registered`.

**Fragment contract (all chains):**

```make
ifneq ($(call ota_selected,<root>),)
TEST_TARGETS += test-<name>
endif
.PHONY: test-<name>
test-<name>:
	<recipe; use $(call ota_args,<root>) for targeted paths>
```

---

## Chain A — MCP server

**Owned files:** `server/**`, `mk/server.mk`, `docs/hermes.md`, `LICENSE`.
**Base:** `main` after the commit of this plan. **Test command:** `make test` (targeted: `make test server/test/<file>`).
**Size:** L (largest chain). **Depends on:** nothing (Teable is stubbed).

Shared test harness (created in A1, used by all A tasks):

`server/test/helpers/stub-teable.ts`
```ts
import http from "node:http";
import type { AddressInfo } from "node:net";

export interface StubCall { method: string; path: string; query: URLSearchParams; body: unknown; authorization?: string; }
export type StubHandler = (call: StubCall) => { status?: number; body: unknown };

/** Local fake Teable. Routes are keyed "METHOD /api/path" (no query). Unknown routes → 404. */
export async function startStubTeable(routes: Record<string, StubHandler>) {
  const calls: StubCall[] = [];
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url ?? "/", "http://stub");
    const chunks: Buffer[] = [];
    for await (const c of req) chunks.push(c as Buffer);
    const raw = Buffer.concat(chunks).toString("utf8");
    const call: StubCall = {
      method: req.method ?? "GET", path: url.pathname, query: url.searchParams,
      body: raw ? JSON.parse(raw) : undefined, authorization: req.headers.authorization,
    };
    calls.push(call);
    const handler = routes[`${call.method} ${call.path}`];
    const out = handler ? handler(call) : { status: 404, body: { message: `no stub for ${call.method} ${call.path}` } };
    res.writeHead(out.status ?? 200, { "content-type": "application/json" });
    res.end(JSON.stringify(out.body));
  });
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  const { port } = server.address() as AddressInfo;
  return { url: `http://127.0.0.1:${port}`, calls, close: () => new Promise<void>((r) => server.close(() => r())) };
}
```

`server/test/helpers/mcp-client.ts` (created in A4, once `createMcpServer` exists)
```ts
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { createMcpServer } from "../../src/server.js";
import { TeableClient } from "../../src/teable/client.js";
import { loadConfig } from "../../src/config.js";

/** Real MCP client ↔ server over an in-memory pair, server talking to `teableUrl`. */
export async function connectClient(teableUrl: string, token = "test-token") {
  const config = loadConfig([], { TEABLE_URL: teableUrl, TEABLE_TOKEN: token });
  const server = createMcpServer(new TeableClient(token, teableUrl), config);
  const [clientT, serverT] = InMemoryTransport.createLinkedPair();
  await server.connect(serverT);
  const client = new Client({ name: "test", version: "0" });
  await client.connect(clientT);
  return client;
}

export function parseText(result: { content: Array<{ type: string; text?: string }> }) {
  return JSON.parse(result.content[0].text as string);
}
```
ANNAHME: `InMemoryTransport` is exported from `@modelcontextprotocol/sdk/inMemory.js` in 1.32. Check: `ls server/node_modules/@modelcontextprotocol/sdk/dist/esm/inMemory.js`. If it is missing, start `startHttpServer` (A10) on port 0 and use `StreamableHTTPClientTransport`, and move A4–A9 tests behind A10.

### Task A1: Package scaffold, config, CLI failure path, make fragment

**Files:**
- Create: `LICENSE`, `mk/server.mk`, `server/package.json`, `server/tsconfig.json`, `server/vitest.config.ts`, `server/.gitignore`, `server/src/config.ts`, `server/src/index.ts` (stub that only loads config), `server/test/helpers/stub-teable.ts`, `server/test/cli.test.ts`, `server/test/config.test.ts`
- Generated + committed: `server/package-lock.json`

**Interfaces:**
- Produces: `loadConfig(argv: string[], env: Record<string,string|undefined>): Config`; `class ConfigError extends Error`;
  `interface Config { transport: "stdio"|"http"; teableUrl: string; token?: string; http: { host: string; port: number; allowedOrigins: string[] }; openapiUrl: string }`.
  CLI contract: config error → stderr `open-table-agent: <message>`, exit 2.

- [ ] **Step 1: scaffold**

`LICENSE`: standard MIT text, line 3 `Copyright (c) 2026 open-table-agent contributors`.

`server/package.json`
```json
{
  "name": "open-table-agent",
  "version": "0.1.0",
  "private": true,
  "license": "MIT",
  "type": "module",
  "bin": { "open-table-agent": "./dist/index.js" },
  "engines": { "node": ">=22" },
  "scripts": { "build": "tsc", "test": "vitest run", "start": "node dist/index.js" },
  "dependencies": { "@modelcontextprotocol/sdk": "^1.32.2", "zod": "^4.6.7" },
  "devDependencies": { "@types/node": "^22", "tsx": "^4", "typescript": "^5.9.3", "vitest": "^5.1.0" }
}
```
`server/tsconfig.json`: `{"compilerOptions":{"target":"ES2022","module":"NodeNext","moduleResolution":"NodeNext","strict":true,"outDir":"dist","rootDir":"src","declaration":false,"esModuleInterop":true,"skipLibCheck":true,"resolveJsonModule":true},"include":["src"]}`
`server/vitest.config.ts`: `export default { test: { include: ["test/**/*.test.ts"], testTimeout: 20000 } };`
`server/.gitignore`: `node_modules/` and `dist/`.

`mk/server.mk`
```make
ifneq ($(call ota_selected,server),)
TEST_TARGETS += test-server
endif
.PHONY: test-server
test-server: server/node_modules/.ota-stamp
	cd server && npx tsc --noEmit && npx vitest run $(patsubst server/%,%,$(filter-out server,$(call ota_args,server)))

server/node_modules/.ota-stamp: server/package-lock.json
	cd server && npm ci --no-audit --no-fund
	touch $@
```
Generate the lock: `npm install --prefix server` (one call; registry.npmjs.org reachable).

- [ ] **Step 2: failing tests**

`server/test/config.test.ts`
```ts
import { describe, it, expect } from "vitest";
import { loadConfig, ConfigError } from "../src/config.js";

describe("loadConfig", () => {
  it("defaults to stdio, needs TEABLE_URL and TEABLE_TOKEN", () => {
    const c = loadConfig([], { TEABLE_URL: "http://t:3000/", TEABLE_TOKEN: "tok" });
    expect(c).toMatchObject({ transport: "stdio", teableUrl: "http://t:3000", token: "tok",
      http: { host: "127.0.0.1", port: 3100, allowedOrigins: [] }, openapiUrl: "http://t:3000/redocs/swagger.json" });
  });
  it("http mode via --http ignores TEABLE_TOKEN", () => {
    const c = loadConfig(["--http"], { TEABLE_URL: "http://t", TEABLE_TOKEN: "env-secret", OTA_HTTP_PORT: "4000",
      OTA_ALLOWED_ORIGINS: " https://a , ,https://b" });
    expect(c.transport).toBe("http");
    expect(c.token).toBeUndefined();
    expect(c.http).toEqual({ host: "127.0.0.1", port: 4000, allowedOrigins: ["https://a", "https://b"] });
  });
  it("rejects missing TEABLE_URL, missing stdio token, bad port", () => {
    expect(() => loadConfig([], { TEABLE_TOKEN: "x" })).toThrow(ConfigError);
    expect(() => loadConfig([], { TEABLE_URL: "http://t" })).toThrow(/TEABLE_TOKEN/);
    expect(() => loadConfig(["--http"], { TEABLE_URL: "http://t", OTA_HTTP_PORT: "70000" })).toThrow(/OTA_HTTP_PORT/);
  });
});
```
`server/test/cli.test.ts` (S13)
```ts
import { it, expect } from "vitest";
import { spawnSync } from "node:child_process";

it("fails loudly without TEABLE_URL", () => {
  const r = spawnSync(process.execPath, ["--import", "tsx", "src/index.ts"], {
    cwd: new URL("..", import.meta.url).pathname, env: { PATH: process.env.PATH }, encoding: "utf8" });
  expect(r.status).toBe(2);
  expect(r.stderr).toMatch(/^open-table-agent: .*TEABLE_URL/m);
});
```

- [ ] **Step 3: run, expect FAIL** — `make test server/test/config.test.ts server/test/cli.test.ts` → vitest reports `Failed to load url ../src/config.js` (module missing); make exits 2.

- [ ] **Step 4: implement `server/src/config.ts`**
```ts
export class ConfigError extends Error {}
export interface Config {
  transport: "stdio" | "http"; teableUrl: string; token?: string;
  http: { host: string; port: number; allowedOrigins: string[] }; openapiUrl: string;
}
type Env = Record<string, string | undefined>;

export function loadConfig(argv: string[], env: Env): Config {
  const transport = argv.includes("--http") || env.OTA_TRANSPORT === "http" ? "http" : "stdio";
  const rawUrl = env.TEABLE_URL?.trim();
  if (!rawUrl) throw new ConfigError("TEABLE_URL is required (Teable origin, e.g. http://127.0.0.1:3000)");
  let teableUrl: string;
  try { teableUrl = new URL(rawUrl).toString().replace(/\/+$/, ""); }
  catch { throw new ConfigError(`TEABLE_URL is not a valid URL: ${rawUrl}`); }
  const token = transport === "stdio" ? env.TEABLE_TOKEN?.trim() : undefined;
  if (transport === "stdio" && !token) throw new ConfigError("TEABLE_TOKEN is required in stdio mode");
  const port = env.OTA_HTTP_PORT ? Number(env.OTA_HTTP_PORT) : 3100;
  if (!Number.isInteger(port) || port < 0 || port > 65535) throw new ConfigError(`OTA_HTTP_PORT invalid: ${env.OTA_HTTP_PORT}`);
  const allowedOrigins = (env.OTA_ALLOWED_ORIGINS ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  return { transport, teableUrl, token, http: { host: env.OTA_HTTP_HOST?.trim() || "127.0.0.1", port, allowedOrigins },
    openapiUrl: env.OTA_OPENAPI_URL?.trim() || `${teableUrl}/redocs/swagger.json` };
}
```
`server/src/index.ts` (stub; A10 completes it)
```ts
#!/usr/bin/env node
import { loadConfig, ConfigError } from "./config.js";

export async function main(argv = process.argv.slice(2), env = process.env): Promise<void> {
  loadConfig(argv, env);
}
main().catch((err) => {
  process.stderr.write(`open-table-agent: ${err instanceof ConfigError ? err.message : String(err?.stack ?? err)}\n`);
  process.exit(err instanceof ConfigError ? 2 : 1);
});
```
Also create `server/test/helpers/stub-teable.ts` exactly as in the chain header.

- [ ] **Step 5: run, expect PASS** — `make test server/test/config.test.ts server/test/cli.test.ts` → `Test Files  2 passed`, last line `make test: OK (test-server)`.
- [ ] **Step 6: mutation S13** — in `index.ts` replace the catch body with `process.exit(1)`; same command → `cli.test.ts` FAIL (`expected 1 to be 2`). Revert.
- [ ] **Step 7: commit** `feat(server): scaffold package, config loading and CLI failure path`.

### Task A2: Teable client and result convention

**Files:** Create `server/src/teable/client.ts`, `server/src/teable/types.ts`, `server/src/result.ts`; Test `server/test/client.test.ts`, `server/test/result.test.ts`.

**Interfaces:**
- Consumes: `startStubTeable` (A1).
- Produces:
  - `class TeableClient { constructor(token: string, teableUrl: string, opts?: { timeoutMs?: number; fetchImpl?: typeof fetch }); request<T=unknown>(method: string, path: string, opts?: { query?: Record<string, string|number|boolean|string[]|undefined>; body?: unknown }): Promise<{ status: number; data: T }> }`. `path` is relative to `<teableUrl>/api` and must start with `/`.
  - `class TeableApiError extends Error { status: number; body: unknown }`. The message is Teable's `message` field, else the JSON body.
  - `MAX_TEXT = 60000`; `toToolResult(output: object): CallToolResult`; `errorResult(err: unknown): CallToolResult`; `assertInputSize(args: unknown, max = 100000): void` (throws `InputTooLargeError`).
  - `types.ts`: `TeableField { id: string; name: string; type: string; dbFieldName?: string; [k: string]: unknown }`, `TeableTable { id; name; dbTableName; description?; icon? }`, `TeableBase { id; name; spaceId; role? }`, `TeableRecord { id: string; fields: Record<string, unknown> }`.

- [ ] **Step 1: failing tests**

`server/test/client.test.ts`
```ts
import { describe, it, expect, afterEach } from "vitest";
import { startStubTeable } from "./helpers/stub-teable.js";
import { TeableClient, TeableApiError } from "../src/teable/client.js";

let stub: Awaited<ReturnType<typeof startStubTeable>>;
afterEach(() => stub?.close());

describe("TeableClient", () => {
  it("sends bearer, JSON body and encoded query to /api + path", async () => {
    stub = await startStubTeable({ "POST /api/table/tbl1/record": () => ({ body: { ok: 1 } }) });
    const c = new TeableClient("tok-1", stub.url);
    const r = await c.request("POST", "/table/tbl1/record", { query: { fieldKeyType: "id", recordIds: ["a", "b"] }, body: { x: 1 } });
    expect(r).toEqual({ status: 200, data: { ok: 1 } });
    expect(stub.calls[0].authorization).toBe("Bearer tok-1");
    expect(stub.calls[0].query.getAll("recordIds")).toEqual(["a", "b"]);
    expect(stub.calls[0].body).toEqual({ x: 1 });
  });
  it("throws TeableApiError with status and Teable message", async () => {
    stub = await startStubTeable({ "GET /api/base/b1/table": () => ({ status: 403, body: { message: "not allowed to base" } }) });
    const err = await new TeableClient("t", stub.url).request("GET", "/base/b1/table").catch((e) => e);
    expect(err).toBeInstanceOf(TeableApiError);
    expect(err).toMatchObject({ status: 403, message: "not allowed to base" });
  });
});
```
`server/test/result.test.ts` (S7)
```ts
import { it, expect } from "vitest";
import { toToolResult, errorResult, assertInputSize, MAX_TEXT } from "../src/result.js";
import { TeableApiError } from "../src/teable/client.js";

it("truncates at 60000 chars", () => {
  const r = toToolResult({ success: true, blob: "x".repeat(70000) });
  const text = r.content[0].text as string;
  expect(MAX_TEXT).toBe(60000);
  expect(text.length).toBeLessThan(60400);
  expect(text).toMatch(/truncated: \d+ characters dropped/);
});
it("isError iff success === false", () => {
  expect(toToolResult({ success: true }).isError).toBeFalsy();
  expect(toToolResult({ success: false, error: "x" }).isError).toBe(true);
});
it("errorResult carries Teable status", () => {
  const r = errorResult(new TeableApiError(403, "nope", { message: "nope" }));
  expect(r.isError).toBe(true);
  expect(JSON.parse(r.content[0].text as string)).toEqual({ success: false, status: 403, error: "nope" });
});
it("rejects inputs above the element cap", () => {
  expect(() => assertInputSize({ a: new Array(11).fill(0) }, 10)).toThrow(/too large/);
  expect(() => assertInputSize({ a: [1, 2] }, 10)).not.toThrow();
});
```
- [ ] **Step 2: run, expect FAIL** — `make test server/test/client.test.ts server/test/result.test.ts` → module-not-found failures.
- [ ] **Step 3: implement**

`server/src/teable/client.ts`
```ts
export class TeableApiError extends Error {
  constructor(public status: number, message: string, public body: unknown) { super(message); }
}
type QueryValue = string | number | boolean | string[] | undefined;

export class TeableClient {
  private readonly apiBase: string;
  constructor(private readonly token: string, teableUrl: string,
              private readonly opts: { timeoutMs?: number; fetchImpl?: typeof fetch } = {}) {
    this.apiBase = `${teableUrl.replace(/\/+$/, "")}/api`;
  }
  async request<T = unknown>(method: string, path: string,
      o: { query?: Record<string, QueryValue>; body?: unknown } = {}): Promise<{ status: number; data: T }> {
    if (!path.startsWith("/")) throw new Error(`path must start with /: ${path}`);
    const url = new URL(this.apiBase + path);
    for (const [k, v] of Object.entries(o.query ?? {})) {
      if (v === undefined) continue;
      for (const item of Array.isArray(v) ? v : [v]) url.searchParams.append(k, String(item));
    }
    const res = await (this.opts.fetchImpl ?? fetch)(url, {
      method,
      headers: { Authorization: `Bearer ${this.token}`, Accept: "application/json",
                 ...(o.body !== undefined ? { "Content-Type": "application/json" } : {}) },
      body: o.body !== undefined ? JSON.stringify(o.body) : undefined,
      signal: AbortSignal.timeout(this.opts.timeoutMs ?? 120_000),
    });
    const text = await res.text();
    let data: unknown = text;
    try { data = text ? JSON.parse(text) : null; } catch { /* keep text */ }
    if (!res.ok) {
      const msg = typeof data === "object" && data && "message" in data ? String((data as { message: unknown }).message)
        : typeof data === "string" ? data : JSON.stringify(data);
      throw new TeableApiError(res.status, msg || `HTTP ${res.status}`, data);
    }
    return { status: res.status, data: data as T };
  }
}
```
`server/src/result.ts`
```ts
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { TeableApiError } from "./teable/client.js";

export const MAX_TEXT = 60000;
export class InputTooLargeError extends Error {}
export class ToolInputError extends Error {
  constructor(message: string, public extra: Record<string, unknown> = {}) { super(message); }
}

export function toToolResult(output: object): CallToolResult {
  let text = JSON.stringify(output);
  if (text.length > MAX_TEXT) {
    const dropped = text.length - MAX_TEXT;
    text = text.slice(0, MAX_TEXT) +
      `\n[truncated: ${dropped} characters dropped. Narrow the request: projection, take/skip, or a tighter filter/query.]`;
  }
  const isError = (output as { success?: unknown }).success === false;
  return { content: [{ type: "text", text }], ...(isError ? { isError: true } : {}) };
}

export function errorResult(err: unknown): CallToolResult {
  if (err instanceof TeableApiError) return toToolResult({ success: false, status: err.status, error: err.message });
  if (err instanceof ToolInputError) return toToolResult({ success: false, error: err.message, ...err.extra });
  return toToolResult({ success: false, error: err instanceof Error ? err.message : String(err) });
}

export function assertInputSize(args: unknown, max = 100000): void {
  let count = 0;
  const stack: unknown[] = [args];
  while (stack.length) {
    const v = stack.pop();
    if (Array.isArray(v)) { count += v.length; stack.push(...v); }
    else if (v && typeof v === "object") { const vals = Object.values(v); count += vals.length; stack.push(...vals); }
    if (count > max) throw new InputTooLargeError(`input too large: more than ${max} array elements + object keys`);
  }
}
```
`server/src/teable/types.ts`: the interfaces listed under Interfaces.
- [ ] **Step 4: run, expect PASS** — same command → `Test Files  2 passed`; `make test: OK (test-server)`.
- [ ] **Step 5: mutation S7** — set `MAX_TEXT = 600000` → `result.test.ts` › "truncates at 60000 chars" FAIL. Revert.
- [ ] **Step 6: commit** `feat(server): add Teable REST client and tool result convention`.

### Task A3: Field resolution and filter mapping

**Files:** Create `server/src/teable/fields.ts`; Test `server/test/fields.test.ts`.

**Interfaces:**
- Consumes: `TeableClient`, `TeableField`, `ToolInputError` (A2).
- Produces:
  - `loadFields(client, tableId): Promise<TeableField[]>` (GET `/table/{tableId}/field`).
  - `resolveFieldKey(fields, key): string` — exact id, else case-insensitive name. Otherwise it throws `ToolInputError("Unknown field: <key>", { suggestions: string[] (≤5, substring match), availableFields: string[] })`.
  - `mapFilterFieldIds<T>(filter: T, fields): T` — deep copy; maps every `fieldId` in condition nodes (`{fieldId, operator, …}`) and in field-reference values (`{type:"field", fieldId}`). It recurses into `filterSet`, `items`, `not` and `value`.

- [ ] **Step 1: failing test** `server/test/fields.test.ts` (S3)
```ts
import { describe, it, expect } from "vitest";
import { resolveFieldKey, mapFilterFieldIds } from "../src/teable/fields.js";
import { ToolInputError } from "../src/result.js";

const fields = [
  { id: "fldName0001", name: "Name", type: "singleLineText" },
  { id: "fldCount001", name: "Count", type: "number" },
  { id: "fldLimit001", name: "Limit", type: "number" },
];

describe("resolveFieldKey", () => {
  it("prefers exact id, then case-insensitive name", () => {
    expect(resolveFieldKey(fields, "fldCount001")).toBe("fldCount001");
    expect(resolveFieldKey(fields, "count")).toBe("fldCount001");
  });
  it("unknown key throws with suggestions", () => {
    try { resolveFieldKey(fields, "Coun"); throw new Error("no throw"); }
    catch (e) {
      expect(e).toBeInstanceOf(ToolInputError);
      expect((e as ToolInputError).extra.suggestions).toEqual(["Count"]);
    }
  });
});

describe("mapFilterFieldIds", () => {
  it("maps names inside nested filter groups", () => {
    const v1 = { conjunction: "and", filterSet: [
      { fieldId: "Name", operator: "is", value: "a" },
      { conjunction: "or", filterSet: [{ fieldId: "count", operator: "isGreater", value: { type: "field", fieldId: "Limit" } }] },
    ] };
    expect(mapFilterFieldIds(v1, fields)).toEqual({ conjunction: "and", filterSet: [
      { fieldId: "fldName0001", operator: "is", value: "a" },
      { conjunction: "or", filterSet: [{ fieldId: "fldCount001", operator: "isGreater", value: { type: "field", fieldId: "fldLimit001" } }] },
    ] });
    const v2 = { not: { conjunction: "and", items: [{ fieldId: "Name", operator: "isEmpty", value: null }] } };
    expect(mapFilterFieldIds(v2, fields)).toEqual({ not: { conjunction: "and", items: [{ fieldId: "fldName0001", operator: "isEmpty", value: null }] } });
  });
  it("throws on an unknown name instead of passing it through", () => {
    expect(() => mapFilterFieldIds({ fieldId: "Nope", operator: "is", value: 1 }, fields)).toThrow(/Unknown field: Nope/);
  });
});
```
- [ ] **Step 2: run, expect FAIL** — `make test server/test/fields.test.ts` → module not found.
- [ ] **Step 3: implement** `server/src/teable/fields.ts`
```ts
import type { TeableClient } from "./client.js";
import type { TeableField } from "./types.js";
import { ToolInputError } from "../result.js";

export async function loadFields(client: TeableClient, tableId: string): Promise<TeableField[]> {
  return (await client.request<TeableField[]>("GET", `/table/${encodeURIComponent(tableId)}/field`)).data;
}

export function resolveFieldKey(fields: TeableField[], key: string): string {
  const byId = fields.find((f) => f.id === key);
  if (byId) return byId.id;
  const lower = key.toLowerCase();
  const byName = fields.find((f) => f.name.toLowerCase() === lower);
  if (byName) return byName.id;
  const suggestions = fields.filter((f) => f.name.toLowerCase().includes(lower) || lower.includes(f.name.toLowerCase()))
    .slice(0, 5).map((f) => f.name);
  throw new ToolInputError(`Unknown field: ${key}`, { suggestions, availableFields: fields.map((f) => f.name) });
}

export function mapFilterFieldIds<T>(filter: T, fields: TeableField[]): T {
  const walk = (node: unknown): unknown => {
    if (Array.isArray(node)) return node.map(walk);
    if (!node || typeof node !== "object") return node;
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(node)) {
      out[k] = k === "fieldId" && typeof v === "string" ? resolveFieldKey(fields, v)
        : k === "filterSet" || k === "items" || k === "not" || k === "value" ? walk(v) : v;
    }
    return out;
  };
  return walk(filter) as T;
}
```
- [ ] **Step 4: run, expect PASS** — `make test server/test/fields.test.ts` → `4 passed`.
- [ ] **Step 5: mutation S3 (part 1)** — make `mapFilterFieldIds` `return filter;` → "maps names inside nested filter groups" FAIL. Revert.
- [ ] **Step 6: commit** `feat(server): resolve field names to ids in keys and filters`.

### Task A4: ToolDef, server factory, read tools list-bases / get-tables-meta / get-fields

**Files:** Create `server/src/tools/types.ts`, `server/src/server.ts`, `server/src/tools/index.ts`, `server/src/tools/list-bases.ts`, `server/src/tools/get-tables-meta.ts`, `server/src/tools/get-fields.ts`, `server/test/helpers/mcp-client.ts`; Test `server/test/read-tools.test.ts`, `server/test/server.test.ts`.

**Interfaces:**
- Consumes: A1–A3.
- Produces:
```ts
// tools/types.ts
import type { ZodRawShape } from "zod";
import type { ToolAnnotations } from "@modelcontextprotocol/sdk/types.js";
export interface ToolContext { client: TeableClient; config: Config }
export interface ToolDef {
  name: string; title: string; description: string; inputSchema: ZodRawShape;
  annotations: ToolAnnotations; handler(args: any, ctx: ToolContext): Promise<object>;
}
export const READ: ToolAnnotations = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
export const WRITE = (destructive: boolean): ToolAnnotations =>
  ({ readOnlyHint: false, destructiveHint: destructive, idempotentHint: false, openWorldHint: false });
```
  `createMcpServer(client: TeableClient, config: Config, tools: ToolDef[] = TOOLS): McpServer`, with `serverInfo {name:"open-table-agent", version:"0.1.0"}` and `instructions` = `SERVER_INSTRUCTIONS` (exported from `server.ts`).

- [ ] **Step 1: failing tests**

`server/test/server.test.ts` (S6)
```ts
import { it, expect, afterEach } from "vitest";
import { startStubTeable } from "./helpers/stub-teable.js";
import { connectClient, parseText } from "./helpers/mcp-client.js";

let stub: Awaited<ReturnType<typeof startStubTeable>>;
afterEach(() => stub?.close());

it("Teable 403 becomes isError result with status", async () => {
  stub = await startStubTeable({ "GET /api/base/bseX/table": () => ({ status: 403, body: { message: "no access" } }) });
  const client = await connectClient(stub.url);
  const r = await client.callTool({ name: "get-tables-meta", arguments: { baseId: "bseX" } });
  expect(r.isError).toBe(true);
  expect(parseText(r as any)).toEqual({ success: false, status: 403, error: "no access" });
});
it("server identifies as open-table-agent", async () => {
  stub = await startStubTeable({});
  const client = await connectClient(stub.url);
  expect(client.getServerVersion()?.name).toBe("open-table-agent");
});
```
`server/test/read-tools.test.ts`
```ts
import { describe, it, expect, afterEach } from "vitest";
import { startStubTeable } from "./helpers/stub-teable.js";
import { connectClient, parseText } from "./helpers/mcp-client.js";

let stub: Awaited<ReturnType<typeof startStubTeable>>;
afterEach(() => stub?.close());
const bases = Array.from({ length: 60 }, (_, i) => ({ id: `bse${i}`, name: i === 7 ? "Festival Desk" : `B${i}`, spaceId: i < 30 ? "spcA" : "spcB", role: "editor" }));

describe("list-bases", () => {
  it("pages with limit/offset and filters by search and spaceId", async () => {
    stub = await startStubTeable({ "GET /api/base/access/all": () => ({ body: bases }) });
    const c = await connectClient(stub.url);
    const p1 = parseText(await c.callTool({ name: "list-bases", arguments: {} }) as any);
    expect(p1).toMatchObject({ success: true, offset: 0, hasMore: true, nextOffset: 50 });
    expect(p1.bases).toHaveLength(50);
    const s = parseText(await c.callTool({ name: "list-bases", arguments: { search: "festival" } }) as any);
    expect(s.bases).toEqual([{ id: "bse7", name: "Festival Desk", spaceId: "spcA", role: "editor" }]);
    const sp = parseText(await c.callTool({ name: "list-bases", arguments: { spaceId: "spcB", limit: 100 } }) as any);
    expect(sp.bases).toHaveLength(30);
    expect(sp.hasMore).toBe(false);
  });
});
describe("get-tables-meta / get-fields", () => {
  it("returns table meta incl. dbTableName and filters by name", async () => {
    stub = await startStubTeable({ "GET /api/base/bse1/table": () => ({ body: [
      { id: "tblA", name: "Acts", dbTableName: "bse1.acts", description: null, icon: null, order: 1 },
      { id: "tblB", name: "Stages", dbTableName: "bse1.stages", description: "x", icon: "🎪", order: 2 } ] }) });
    const c = await connectClient(stub.url);
    const r = parseText(await c.callTool({ name: "get-tables-meta", arguments: { baseId: "bse1", tableName: "Stages" } }) as any);
    expect(r).toEqual({ success: true, count: 1, tables: [{ id: "tblB", name: "Stages", dbTableName: "bse1.stages", description: "x", icon: "🎪" }] });
    const miss = await c.callTool({ name: "get-tables-meta", arguments: { baseId: "bse1", tableId: "tblZ" } });
    expect(miss.isError).toBe(true);
  });
  it("get-fields returns full field objects", async () => {
    const f = [{ id: "fld1", name: "Name", type: "singleLineText", dbFieldName: "name", options: {} }];
    stub = await startStubTeable({ "GET /api/table/tblA/field": () => ({ body: f }) });
    const c = await connectClient(stub.url);
    expect(parseText(await c.callTool({ name: "get-fields", arguments: { tableId: "tblA" } }) as any))
      .toEqual({ success: true, count: 1, fields: f });
  });
});
```
- [ ] **Step 2: run, expect FAIL** — `make test server/test/server.test.ts server/test/read-tools.test.ts` → module not found.
- [ ] **Step 3: implement**

`server/src/server.ts` (ported factory from teable-mcp fc8dff1, with the MIT header; errors are returned, not thrown)
```ts
// Portions Copyright (c) 2024 Teable MCP Server Contributors (MIT), ported from teable-mcp
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { Config } from "./config.js";
import type { TeableClient } from "./teable/client.js";
import type { ToolDef } from "./tools/types.js";
import { TOOLS } from "./tools/index.js";
import { assertInputSize, errorResult, toToolResult } from "./result.js";

export const SERVER_INSTRUCTIONS = [
  "Data model: space > base > table; tables have fields, views and records.",
  "Start with list-bases, then get-tables-meta. Call get-fields before writing records.",
  "Field names are accepted wherever a field is referenced (projection, filters, headers); they are mapped to field IDs.",
  "update-records: either filter+fields (same values for all matches) or header+records (per-record values); never both.",
  "delete-records: either recordIds or filter; never both.",
  "sql-query is read-only PostgreSQL over one base; prefer get-records when you need record IDs.",
  "For anything else: search-api, then call-api-read (GET) or call-api-write. Every call runs with your own token's permissions; report 403s instead of working around them.",
].join("\n");

export function createMcpServer(client: TeableClient, config: Config, tools: ToolDef[] = TOOLS): McpServer {
  const server = new McpServer({ name: "open-table-agent", version: "0.1.0" }, { instructions: SERVER_INSTRUCTIONS });
  for (const tool of tools) {
    server.registerTool(tool.name,
      { title: tool.title, description: tool.description, inputSchema: tool.inputSchema, annotations: { title: tool.title, ...tool.annotations } },
      async (args: unknown) => {
        try { assertInputSize(args); return toToolResult(await tool.handler(args, { client, config })); }
        catch (err) { return errorResult(err); }
      });
  }
  return server;
}
```
`server/src/tools/list-bases.ts`
```ts
import { z } from "zod";
import { READ, type ToolDef } from "./types.js";
import type { TeableBase } from "../teable/types.js";

const PAGE_CHAR_BUDGET = 59000;
export const tool: ToolDef = {
  name: "list-bases", title: "List bases", annotations: READ,
  description: "List the bases (projects) the token can access. Optional case-insensitive search on name or id, optional spaceId, paging via limit/offset.",
  inputSchema: { search: z.string().optional(), spaceId: z.string().optional(),
    limit: z.number().int().min(1).max(100).default(50), offset: z.number().int().min(0).default(0) },
  async handler({ search, spaceId, limit, offset }, { client }) {
    const all = (await client.request<TeableBase[]>("GET", "/base/access/all")).data;
    const q = search?.toLowerCase();
    const matched = all.filter((b) => (!spaceId || b.spaceId === spaceId) &&
      (!q || b.name.toLowerCase().includes(q) || b.id.toLowerCase().includes(q)));
    const page: object[] = [];
    let chars = 0;
    for (const b of matched.slice(offset, offset + limit)) {
      const item = { id: b.id, name: b.name.length > 200 ? b.name.slice(0, 199) + "…" : b.name, spaceId: b.spaceId, role: b.role };
      chars += JSON.stringify(item).length;
      if (page.length > 0 && chars > PAGE_CHAR_BUDGET) break;
      page.push(item);
    }
    const next = offset + page.length;
    const hasMore = next < matched.length;
    return { success: true, offset, hasMore, ...(hasMore ? { nextOffset: next } : {}), bases: page };
  },
};
```
ANNAHME: `GET /api/base/access/all` returns an array of `{id, name, spaceId, role, …}`. Check: `packages/openapi/src/base/all-list.ts` in teable-fork (response schema). Adapt the type and the test fixture if it differs.

`server/src/tools/get-tables-meta.ts`: input `{ baseId: z.string().min(1), tableId: z.string().optional(), tableName: z.string().optional() }`; GET `/base/${encodeURIComponent(baseId)}/table`; map to `{id,name,dbTableName,description,icon}`; if `tableId` is given, filter by id, else if `tableName` is given, filter by exact name. An empty result with a filter given returns `{ success: false, error: "Table not found: <key>" }`. Otherwise `{ success: true, count, tables }`. Description: "List tables of a base with id, name, dbTableName (for sql-query), description, icon."
`server/src/tools/get-fields.ts`: input `{ tableId: z.string().min(1), fieldId: z.string().optional(), fieldName: z.string().optional() }`; `loadFields`; optional exact filter by id, else by name; same not-found rule; `{ success: true, count, fields }` (full objects). Description: "Field definitions of a table: id, name, type, dbFieldName (for sql-query), options."
`server/src/tools/index.ts`: `export const TOOLS: ToolDef[] = [listBases, getTablesMeta, getFields];`. Import each module's `tool` under a local name. Later tasks append to this array.
`server/test/helpers/mcp-client.ts`: exactly as in the chain header.

- [ ] **Step 4: run, expect PASS** — same command → `Test Files  2 passed`.
- [ ] **Step 5: mutation S6** — in `server.ts` replace `return errorResult(err);` with `throw err;` → "Teable 403 becomes isError result with status" FAIL. Revert.
- [ ] **Step 6: commit** `feat(server): add server factory and list-bases, get-tables-meta, get-fields`.

### Task A5: get-records

**Files:** Create `server/src/tools/get-records.ts`; Modify `server/src/tools/index.ts` (append); Test `server/test/get-records.test.ts`.

**Interfaces:**
- Consumes: `loadFields`, `resolveFieldKey`, `mapFilterFieldIds` (A3); `ToolDef`, `READ` (A4).
- Produces: tool `get-records`; output `{success, total, hint?, format:"tabular", header:string[], rows:unknown[][], meta:{fields:Record<string,{id,type}>}}`.

Behaviour (spec §4.6):
- Input schema:
  - `tableId: z.string().min(1)`
  - `viewId?: string`, `recordId?: string`
  - `take: z.coerce.number().int().min(1).max(1000).default(100)`, `skip?: z.coerce.number().int().min(0)`
  - `projection?: z.union([z.literal("all"), z.array(z.string()).max(50)])`
  - `filter?: z.record(z.string(), z.unknown())`
  - `search?: z.object({ value: z.string(), field: z.string().optional() })`
  - `orderBy?: z.array(z.object({ field: z.string(), order: z.enum(["asc","desc"]) }))`
- Field set:
  - `fields = await loadFields`.
  - Projected ids: if `projection` is an array, map each entry through `resolveFieldKey`. Otherwise (absent or `"all"`) take the first 50 fields; if the table has more than 50, set `hint` to "showing the first 50 of N fields; pass projection".
  - If `search.field` is given, resolve it and add it to the projection when missing.
- Request:
  - `recordId` given: `GET /table/{tableId}/record/{recordId}` with `fieldKeyType=id` and `projection`.
  - Otherwise: `GET /table/{tableId}/record` with query `fieldKeyType=id`, `take`, `skip`, `viewId`, and `projection` (array → repeated `projection` keys).
  - `filter=JSON.stringify(mapFilterFieldIds(filter))`.
  - `orderBy=JSON.stringify([{fieldId, order}])`.
  - `search=JSON.stringify([value, fieldId ?? "", true])`.
  - ANNAHME: the CE query param names and encodings are `projection` (repeated), `filter`/`orderBy`/`search` as JSON strings, and response `{records:[{id, fields}]}`. Check `packages/openapi/src/record/get-list.ts` (`getRecordsRoSchema`, :199) and `record/get.ts`, then adapt the encoding (only the encoding, not the tool's input schema).
- Output:
  - Header: `["id", ...projected names]`.
  - Each row: `[record.id, ...projected ids.map(id => clean(record.fields[id] ?? null))]`, where `clean` deep-removes `smThumbnailUrl` / `lgThumbnailUrl` keys.
  - `total` = number of rows; `meta.fields[name] = {id, type}`.

- [ ] **Step 1: failing test** `server/test/get-records.test.ts`
```ts
import { it, expect, afterEach } from "vitest";
import { startStubTeable } from "./helpers/stub-teable.js";
import { connectClient, parseText } from "./helpers/mcp-client.js";

let stub: Awaited<ReturnType<typeof startStubTeable>>;
afterEach(() => stub?.close());
const fields = [{ id: "fldName0001", name: "Name", type: "singleLineText" }, { id: "fldCount001", name: "Count", type: "number" },
  { id: "fldPic00001", name: "Pic", type: "attachment" }];
const routes = {
  "GET /api/table/tbl1/field": () => ({ body: fields }),
  "GET /api/table/tbl1/record": () => ({ body: { records: [
    { id: "rec1", fields: { fldName0001: "A", fldCount001: 3, fldPic00001: [{ name: "p.png", smThumbnailUrl: "u" }] } }] } }),
};

it("sends field IDs in filter and returns tabular rows", async () => {
  stub = await startStubTeable(routes);
  const c = await connectClient(stub.url);
  const r = parseText(await c.callTool({ name: "get-records", arguments: {
    tableId: "tbl1", projection: ["Name", "count", "Pic"],
    filter: { conjunction: "and", filterSet: [{ fieldId: "Count", operator: "isGreater", value: 1 }] },
    orderBy: [{ field: "Name", order: "asc" }] } }) as any);
  const call = stub.calls.find((x) => x.path === "/api/table/tbl1/record")!;
  expect(JSON.parse(call.query.get("filter")!)).toEqual({ conjunction: "and", filterSet: [{ fieldId: "fldCount001", operator: "isGreater", value: 1 }] });
  expect(JSON.parse(call.query.get("orderBy")!)).toEqual([{ fieldId: "fldName0001", order: "asc" }]);
  expect(call.query.get("fieldKeyType")).toBe("id");
  expect(r).toMatchObject({ success: true, total: 1, format: "tabular", header: ["id", "Name", "Count", "Pic"],
    rows: [["rec1", "A", 3, [{ name: "p.png" }]]] });
});
it("unknown filter field is an error and sends no record request", async () => {
  stub = await startStubTeable(routes);
  const c = await connectClient(stub.url);
  const r = await c.callTool({ name: "get-records", arguments: { tableId: "tbl1",
    filter: { conjunction: "and", filterSet: [{ fieldId: "Cnt", operator: "is", value: 1 }] } } });
  expect(r.isError).toBe(true);
  expect(stub.calls.some((x) => x.path === "/api/table/tbl1/record")).toBe(false);
});
```
- [ ] **Step 2: run, expect FAIL** — `make test server/test/get-records.test.ts` → `Tool get-records not found` (MCP error).
- [ ] **Step 3: implement** `server/src/tools/get-records.ts` per the behaviour list above, and append it to `TOOLS`.
- [ ] **Step 4: run, expect PASS** — same command → `2 passed`.
- [ ] **Step 5: mutation S3 (part 2)** — pass `filter` through unmapped → "sends field IDs in filter" FAIL. Revert.
- [ ] **Step 6: commit** `feat(server): add get-records with name-to-id mapping`.

### Task A6: sql-query and get-doc (with bundled docs)

**Files:** Create `server/src/tools/sql-query.ts`, `server/src/tools/get-doc.ts`, `server/src/docs/index.ts`, `server/docs-bundle/*.md` (23), `server/docs-bundle/SOURCE.md`, `server/THIRD_PARTY_NOTICES.md`; Modify `server/src/tools/index.ts`; Test `server/test/sql-query.test.ts`, `server/test/get-doc.test.ts`.

**Interfaces:**
- Produces: `DOC_TOPICS: readonly string[]` (23 keys, sorted); `readDoc(topic: string): string`. Docs are read from `new URL("../../docs-bundle/", import.meta.url)`, which resolves from both `src/docs/` and `dist/docs/`.
- `sql-query` output `{success, rowCount, columnCount, columns, rows}`. Request: `POST /base/{baseId}/sql-query` with body `{sql}`; expects the response `{rows: object[]}` (patch contract, spec §5.2).

- [ ] **Step 1: bundle docs.** Clone agent-skills into the ignored scratch dir: `git clone https://github.com/teableio/agent-skills .scratch/agent-skills`, then `git -C .scratch/agent-skills checkout 01408885444a66f68b721d6eaae70159d3db7e3d`. Copy the 23 files `skills/teable-assistant-ops/api-reference/*.md` unchanged to `server/docs-bundle/` (one `cp` call with all paths). Write `server/docs-bundle/SOURCE.md`: repo URL, sha, path, "MIT License, Copyright (c) 2026" + full MIT text. Write `server/THIRD_PARTY_NOTICES.md`: the teable-mcp MIT text ("Copyright (c) 2024 Teable MCP Server Contributors") and the agent-skills MIT text. Check: `ls server/docs-bundle` → 24 entries.
- [ ] **Step 2: failing tests**

`server/test/get-doc.test.ts` (S9)
```ts
import { it, expect, afterEach } from "vitest";
import { startStubTeable } from "./helpers/stub-teable.js";
import { connectClient, parseText } from "./helpers/mcp-client.js";
import { DOC_TOPICS } from "../src/docs/index.js";

const EXPECTED = ["automation.api","automation.send-email","automation.trigger","field.basic","field.colors","field.formatting",
  "field.formula","field.link","field.lookup","field.rollup","field.select","field.show-as","field.simple","integration.slack",
  "record.value-format","reference.url","scrape.datasets","scrape.guide","view.column","view.filter","view.group","view.sort","view.statistic"];
let stub: Awaited<ReturnType<typeof startStubTeable>>;
afterEach(() => stub?.close());

it("every topic resolves", async () => {
  expect([...DOC_TOPICS]).toEqual(EXPECTED);
  stub = await startStubTeable({});
  const c = await connectClient(stub.url);
  for (const topic of EXPECTED) {
    const r = parseText(await c.callTool({ name: "get-doc", arguments: { topic } }) as any);
    expect(r.success, topic).toBe(true);
    expect(r.content).toMatch(/^# /);
  }
});
it("rejects unknown topics", async () => {
  stub = await startStubTeable({});
  const c = await connectClient(stub.url);
  const r = await c.callTool({ name: "get-doc", arguments: { topic: "app.ai" } });
  expect(r.isError).toBe(true);
});
```
`server/test/sql-query.test.ts` (S10)
```ts
import { it, expect, afterEach } from "vitest";
import { startStubTeable } from "./helpers/stub-teable.js";
import { connectClient, parseText } from "./helpers/mcp-client.js";

let stub: Awaited<ReturnType<typeof startStubTeable>>;
afterEach(() => stub?.close());

it("posts sql to the patched route", async () => {
  stub = await startStubTeable({ "POST /api/base/bse1/sql-query": () => ({ body: { rows: [{ n: 2, name: "A" }, { n: 1, name: "B" }] } }) });
  const c = await connectClient(stub.url);
  const r = parseText(await c.callTool({ name: "sql-query", arguments: { baseId: "bse1", sql: 'SELECT 1 FROM "bse1"."acts" LIMIT 1' } }) as any);
  expect(stub.calls[0].body).toEqual({ sql: 'SELECT 1 FROM "bse1"."acts" LIMIT 1' });
  expect(r).toEqual({ success: true, rowCount: 2, columnCount: 2, columns: ["n", "name"], rows: [{ n: 2, name: "A" }, { n: 1, name: "B" }] });
});
it("refusal by Teable is an isError result", async () => {
  stub = await startStubTeable({ "POST /api/base/bse1/sql-query": () => ({ status: 403, body: { message: "forbidden" } }) });
  const c = await connectClient(stub.url);
  const r = await c.callTool({ name: "sql-query", arguments: { baseId: "bse1", sql: "SELECT 1" } });
  expect(r.isError).toBe(true);
});
```
- [ ] **Step 3: run, expect FAIL** — `make test server/test/get-doc.test.ts server/test/sql-query.test.ts` → module not found.
- [ ] **Step 4: implement**
  - `docs/index.ts`: `DOC_TOPICS` is a literal sorted array of the 23 keys. `readDoc` uses `readFileSync(new URL(\`../../docs-bundle/${topic}.md\`, import.meta.url), "utf8")` after checking `DOC_TOPICS.includes(topic)`.
  - `get-doc.ts`: `inputSchema: { topic: z.enum(DOC_TOPICS as [string, ...string[]]) }`; returns `{ success: true, topic, content }`; `READ`. Description lists the topic groups.
  - `sql-query.ts`: `inputSchema: { baseId: z.string().min(1), sql: z.string().min(1) }`; calls `client.request<{rows: Record<string, unknown>[]}>("POST", \`/base/${encodeURIComponent(baseId)}/sql-query\`, { body: { sql } })`; `columns = Object.keys(rows[0] ?? {})`; `READ`.
    Description (own wording, spec §4.6 item 4): read-only PostgreSQL; tables `"<baseId>"."<dbTableName>"` from get-tables-meta, columns are quoted `dbFieldName` from get-fields; system columns `__id, __auto_number, __created_time, __last_modified_time, __created_by, __last_modified_by`; always add LIMIT; timestamps UTC; use get-records when record IDs are needed for writes.
  - Append both tools to `TOOLS`.
- [ ] **Step 5: run, expect PASS** — same command → `3 passed`.
- [ ] **Step 6: mutations** — S9: move `server/docs-bundle/view.sort.md` to `.scratch/` → "every topic resolves" FAIL; move it back. S10: change the path to `/sql` → "posts sql to the patched route" FAIL; revert.
- [ ] **Step 7: commit** `feat(server): add sql-query and get-doc with bundled agent-skills topics`.

### Task A7: OpenAPI index, search-api, call-api-read, call-api-write

**Files:** Create `server/src/openapi/index.ts`, `server/src/tools/search-api.ts`, `server/src/tools/call-api-read.ts`, `server/src/tools/call-api-write.ts`, `server/test/fixtures/openapi-mini.json`; Modify `server/src/tools/index.ts`; Test `server/test/openapi.test.ts`, `server/test/call-api.test.ts`.

**Interfaces:**
- Produces:
```ts
export interface ApiParam { name: string; in: "path" | "query"; required: boolean; type?: string; description?: string }
export interface ApiEndpoint { id: string /* "GET:/table/{tableId}/record" */; method: string; url: string; summary: string;
  description: string; tags: string[]; parameters: ApiParam[];
  requestBody?: { required: boolean; properties: { name: string; type?: string; required: boolean; description?: string }[] } }
export class ApiIndex {
  static fromSpec(spec: unknown): ApiIndex;
  readonly endpoints: ApiEndpoint[];
  search(query: string, o?: { tags?: string[]; limit?: number }): ApiEndpoint[];
  lookup(method: string, url: string): ApiEndpoint | undefined;
  tags(): string[];
}
export async function getApiIndex(client: TeableClient, openapiUrl: string): Promise<ApiIndex>; // 10-min cache per URL
export function buildRequest(ep: ApiEndpoint, params: Record<string, unknown> = {}): { path: string; query: Record<string, string | string[]> };
// throws ToolInputError("Invalid parameters: missing <names>", { parameters: ep.parameters }) on a missing required path/query param
```
- `getApiIndex` fetches the spec with plain `fetch(openapiUrl, { headers: { Authorization: "Bearer <token>" } })`. Add `TeableClient.fetchAbsolute(url): Promise<unknown>` to `client.ts` for this; the URL is outside `/api`.
- Path normalization: strip a leading `/api` from spec paths; a spec `servers[0].url` ending in `/api` is also handled.
- Scoring: lower-case tokens of the query; for each token, add 4 if it is in the summary, 2 path, 2 description, 1.5 tags, 0.5 method. Drop endpoints with score 0. Sort by score desc, then url asc.

- [ ] **Step 1: fixture** `server/test/fixtures/openapi-mini.json`: an OpenAPI 3 doc with three paths:
  - `/api/table/{tableId}/view` GET: tag `view`, summary "Get view list", path param `tableId` required.
  - `/api/table/{tableId}/view` POST: summary "Create view", requestBody required with properties `name` and `type`.
  - `/api/base/{baseId}/collaborators` GET: tag `base`, summary "List base collaborators", query param `skip` optional.

  The first path is written with the `/api` prefix and the third without it, so normalization is tested.
- [ ] **Step 2: failing tests**

`server/test/openapi.test.ts`
```ts
import { it, expect } from "vitest";
import spec from "./fixtures/openapi-mini.json" with { type: "json" };
import { ApiIndex, buildRequest } from "../src/openapi/index.js";

it("indexes endpoints with normalized paths and ranks by summary", () => {
  const idx = ApiIndex.fromSpec(spec);
  expect(idx.endpoints.map((e) => e.id).sort()).toEqual(["GET:/base/{baseId}/collaborators", "GET:/table/{tableId}/view", "POST:/table/{tableId}/view"]);
  expect(idx.search("create view")[0].id).toBe("POST:/table/{tableId}/view");
  expect(idx.search("view", { tags: ["base"] })).toEqual([]);
});
it("buildRequest splits path/query, encodes path params, rejects missing required", () => {
  const ep = ApiIndex.fromSpec(spec).lookup("GET", "/table/{tableId}/view")!;
  expect(buildRequest(ep, { tableId: "tbl/../x", extra: ["a", "b"], obj: { k: 1 } }))
    .toEqual({ path: "/table/tbl%2F..%2Fx/view", query: { extra: ["a", "b"], obj: '{"k":1}' } });
  expect(() => buildRequest(ep, {})).toThrow(/missing tableId/);
});
```
`server/test/call-api.test.ts` (S8)
```ts
import { it, expect, afterEach } from "vitest";
import spec from "./fixtures/openapi-mini.json" with { type: "json" };
import { startStubTeable } from "./helpers/stub-teable.js";
import { connectClient, parseText } from "./helpers/mcp-client.js";

let stub: Awaited<ReturnType<typeof startStubTeable>>;
afterEach(() => stub?.close());
const base = { "GET /redocs/swagger.json": () => ({ body: spec }) };

it("rejects unknown endpoint without a request", async () => {
  stub = await startStubTeable(base);
  const c = await connectClient(stub.url);
  const r = await c.callTool({ name: "call-api-read", arguments: { url: "/../admin/settings" } });
  expect(r.isError).toBe(true);
  expect(parseText(r as any).error).toMatch(/Unknown API/);
  expect(stub.calls.filter((x) => x.path !== "/redocs/swagger.json")).toEqual([]);
});
it("call-api-read GETs an indexed endpoint; call-api-write sends method and body", async () => {
  stub = await startStubTeable({ ...base,
    "GET /api/table/tbl1/view": () => ({ body: [{ id: "viw1" }] }),
    "POST /api/table/tbl1/view": (call) => ({ status: 201, body: { id: "viw2", got: call.body } }) });
  const c = await connectClient(stub.url);
  expect(parseText(await c.callTool({ name: "call-api-read", arguments: { url: "/table/{tableId}/view", params: { tableId: "tbl1" } } }) as any))
    .toEqual({ success: true, statusCode: 200, data: [{ id: "viw1" }] });
  const w = parseText(await c.callTool({ name: "call-api-write", arguments: { method: "POST", url: "/table/{tableId}/view",
    params: { tableId: "tbl1" }, data: '{"name":"Grid","type":"grid"}' } }) as any);
  expect(w).toEqual({ success: true, statusCode: 201, data: { id: "viw2", got: { name: "Grid", type: "grid" } } });
});
it("search-api returns ranked results and availableTags on no hit", async () => {
  stub = await startStubTeable(base);
  const c = await connectClient(stub.url);
  const r = parseText(await c.callTool({ name: "search-api", arguments: { query: "collaborators" } }) as any);
  expect(r.results[0]).toMatchObject({ method: "GET", url: "/base/{baseId}/collaborators" });
  const none = parseText(await c.callTool({ name: "search-api", arguments: { query: "zzzz" } }) as any);
  expect(none).toMatchObject({ success: true, results: [], availableTags: ["base", "view"] });
});
```
- [ ] **Step 3: run, expect FAIL** — `make test server/test/openapi.test.ts server/test/call-api.test.ts` → module not found.
- [ ] **Step 4: implement**
  - `openapi/index.ts` per the interface. The parser walks `spec.paths[path][method]` for get/post/put/patch/delete, collects `parameters` (path-level and operation-level) and `requestBody.content["application/json"].schema.properties` (`$ref`s into `components.schemas` resolved up to 3 levels).
  - `search-api.ts`: `inputSchema { query: z.string().min(1), tags: z.array(z.string()).optional(), limit: z.coerce.number().int().min(1).max(10).default(5) }`; result `{success:true, totalApiCount, results}`. No hit: `{success:true, results:[], availableTags: idx.tags(), hint:"try other words or a tag"}`.
  - `call-api-read.ts`: `{ url: z.string().min(1), params: z.record(z.string(), z.unknown()).optional() }`; `lookup("GET", url)`. Missing → `{success:false, error:"Unknown API GET <url> — use search-api to find the endpoint template"}`.
    Otherwise `buildRequest` → `client.request("GET", path, {query})` → `{success:true, statusCode, data}`. A caught `TeableApiError` returns `{success:false, statusCode: e.status, error: e.message}`.
  - `call-api-write.ts`: same, plus `method: z.enum(["POST","PUT","PATCH","DELETE"])` and `data: z.union([z.record(z.string(), z.unknown()), z.string()]).optional()`. A string `data` is JSON-parsed; invalid JSON → `ToolInputError`. A required body that is missing → `ToolInputError`. Annotations `WRITE(true)`.
  - Append all three to `TOOLS`.
- [ ] **Step 5: run, expect PASS** — same command → `5 passed`.
- [ ] **Step 6: mutation S8** — in `call-api-read.ts` replace the lookup miss with a direct `client.request("GET", url)` → "rejects unknown endpoint without a request" FAIL. Revert.
- [ ] **Step 7: commit** `feat(server): add OpenAPI index, search-api and call-api tools`.

### Task A8: create-records, update-records, delete-records

**Files:** Create `server/src/tools/create-records.ts`, `server/src/tools/update-records.ts`, `server/src/tools/delete-records.ts`, `server/src/tools/rows.ts`; Modify `server/src/tools/index.ts`; Test `server/test/create-records.test.ts`, `server/test/update-records.test.ts`, `server/test/delete-records.test.ts`.

**Interfaces:**
- Produces, in `rows.ts`:
  - `resolveHeader(fields, header: string[]): string[]` (ids, via `resolveFieldKey`).
  - `assertRectangular(header: string[], records: unknown[][]): void`. Throws `ToolInputError("Row length does not match header (rows: 2, 5)")`, naming at most 3 row indices.
  - `notWrittenWarnings(sent: Record<string,unknown>[], returned: {fields:Record<string,unknown>}[], fields): string[]`.
- Tools:
  - `create-records`: `{tableId, header: z.array(z.string()).min(1), records: z.array(z.array(z.unknown())).min(1), typecast: z.boolean().default(true)}` → `POST /table/{tableId}/record` body `{fieldKeyType:"id", typecast, records:[{fields}]}`, omitting `null`/`undefined`/`""` cells → `{success, recordsCreated, recordIds, warnings?}`. `WRITE(false)`.
  - `update-records`:
    - Input: `{tableId, filter?, fields?: record, header?: string[], records?: unknown[][], typecast=true}`.
    - The handler enforces exactly one mode: A = `filter` and `fields` both present, B = `header` (must contain `recordId`) and `records` both present. Anything else → `ToolInputError("Use exactly one mode: filter+fields OR header+records")`.
    - A: `POST /v2/tables/updateRecords` body `{tableId, filter: mapFilterFieldIds(filter), fields: {<id>: value}, typecast, fieldKeyType:"id"}` → `{success, updatedCount}`.
    - B: `PATCH /table/{tableId}/record` body `{fieldKeyType:"id", typecast, records:[{id, fields}]}`. In a row, `""` skips the cell and `null` clears it → `{success, updated, warnings?}`.
    - `WRITE(true)`.
  - `delete-records`:
    - Input: `{tableId, recordIds?: z.array(z.string()).min(1).max(1000), filter?}`, exactly one of the two.
    - ids: `DELETE /table/{tableId}/record` with query `recordIds` repeated → `{success, deletedCount: recordIds.length}`.
    - filter: `DELETE /v2/tables/deleteRecords` body `{tableId, filter}` → `{success, deletedCount}` from the response.
    - `WRITE(true)`.
- ANNAHME: the v2 response bodies carry `updatedCount` / `deletedCount`, and the v1 create response is `{records:[{id, fields}]}`. Check: `packages/v2/contract-http/src/contract.ts` (`tablesUpdateRecordsContract`, `tablesDeleteRecordsContract` output schemas) and `packages/openapi/src/record/create.ts`. Adapt the response parsing, not the tool output.
- ANNAHME: the v1 delete expects `recordIds` as repeated query keys (`record/delete-list.ts`). Check the same way.

- [ ] **Step 1: failing tests** (shared fields fixture: `Name`/`fldName0001`, `Count`/`fldCount001`)

`server/test/create-records.test.ts` (S11)
```ts
import { it, expect, afterEach } from "vitest";
import { startStubTeable } from "./helpers/stub-teable.js";
import { connectClient, parseText } from "./helpers/mcp-client.js";

let stub: Awaited<ReturnType<typeof startStubTeable>>;
afterEach(() => stub?.close());
const fields = [{ id: "fldName0001", name: "Name", type: "singleLineText" }, { id: "fldCount001", name: "Count", type: "number" }];

it("maps header names, drops empty cells, returns ids", async () => {
  stub = await startStubTeable({ "GET /api/table/tbl1/field": () => ({ body: fields }),
    "POST /api/table/tbl1/record": (c) => ({ body: { records: (c.body as any).records.map((r: any, i: number) => ({ id: `rec${i}`, fields: r.fields })) } }) });
  const c = await connectClient(stub.url);
  const r = parseText(await c.callTool({ name: "create-records", arguments: { tableId: "tbl1", header: ["Name", "count"], records: [["A", 1], ["B", ""]] } }) as any);
  expect(stub.calls.at(-1)!.body).toEqual({ fieldKeyType: "id", typecast: true,
    records: [{ fields: { fldName0001: "A", fldCount001: 1 } }, { fields: { fldName0001: "B" } }] });
  expect(r).toMatchObject({ success: true, recordsCreated: 2, recordIds: ["rec0", "rec1"] });
});
it("rejects ragged rows without a request", async () => {
  stub = await startStubTeable({ "GET /api/table/tbl1/field": () => ({ body: fields }) });
  const c = await connectClient(stub.url);
  const r = await c.callTool({ name: "create-records", arguments: { tableId: "tbl1", header: ["Name", "Count"], records: [["A", 1], ["B"]] } });
  expect(r.isError).toBe(true);
  expect(stub.calls.some((x) => x.method === "POST")).toBe(false);
});
```
`server/test/update-records.test.ts`
```ts
import { it, expect, afterEach } from "vitest";
import { startStubTeable } from "./helpers/stub-teable.js";
import { connectClient, parseText } from "./helpers/mcp-client.js";

let stub: Awaited<ReturnType<typeof startStubTeable>>;
afterEach(() => stub?.close());
const fields = [{ id: "fldName0001", name: "Name", type: "singleLineText" }, { id: "fldCount001", name: "Count", type: "number" }];

it("mode A maps filter and field names and calls v2 updateRecords", async () => {
  stub = await startStubTeable({ "GET /api/table/tbl1/field": () => ({ body: fields }),
    "POST /api/v2/tables/updateRecords": () => ({ body: { updatedCount: 4 } }) });
  const c = await connectClient(stub.url);
  const r = parseText(await c.callTool({ name: "update-records", arguments: { tableId: "tbl1",
    filter: { conjunction: "and", items: [{ fieldId: "Name", operator: "is", value: "A" }] }, fields: { count: 9 } } }) as any);
  expect(stub.calls.at(-1)!.body).toEqual({ tableId: "tbl1", filter: { conjunction: "and", items: [{ fieldId: "fldName0001", operator: "is", value: "A" }] },
    fields: { fldCount001: 9 }, typecast: true, fieldKeyType: "id" });
  expect(r).toEqual({ success: true, updatedCount: 4 });
});
it("mode B: '' leaves unchanged, null clears", async () => {
  stub = await startStubTeable({ "GET /api/table/tbl1/field": () => ({ body: fields }),
    "PATCH /api/table/tbl1/record": (c) => ({ body: (c.body as any).records }) });
  const c = await connectClient(stub.url);
  await c.callTool({ name: "update-records", arguments: { tableId: "tbl1", header: ["recordId", "Name", "Count"], records: [["rec1", "", null]] } });
  expect(stub.calls.at(-1)!.body).toEqual({ fieldKeyType: "id", typecast: true, records: [{ id: "rec1", fields: { fldCount001: null } }] });
});
it("rejects mixed modes", async () => {
  stub = await startStubTeable({ "GET /api/table/tbl1/field": () => ({ body: fields }) });
  const c = await connectClient(stub.url);
  const r = await c.callTool({ name: "update-records", arguments: { tableId: "tbl1", filter: { fieldId: "Name", operator: "is", value: "A" },
    fields: { Count: 1 }, header: ["recordId", "Count"], records: [["rec1", 2]] } });
  expect(r.isError).toBe(true);
});
```
`server/test/delete-records.test.ts` (S12)
```ts
import { it, expect, afterEach } from "vitest";
import { startStubTeable } from "./helpers/stub-teable.js";
import { connectClient, parseText } from "./helpers/mcp-client.js";

let stub: Awaited<ReturnType<typeof startStubTeable>>;
afterEach(() => stub?.close());
const fields = [{ id: "fldName0001", name: "Name", type: "singleLineText" }];

it("rejects filter plus recordIds", async () => {
  stub = await startStubTeable({ "GET /api/table/tbl1/field": () => ({ body: fields }) });
  const c = await connectClient(stub.url);
  const r = await c.callTool({ name: "delete-records", arguments: { tableId: "tbl1", recordIds: ["rec1"], filter: { fieldId: "Name", operator: "is", value: "A" } } });
  expect(r.isError).toBe(true);
  expect(stub.calls.some((x) => x.method === "DELETE")).toBe(false);
});
it("deletes by ids and by mapped filter", async () => {
  stub = await startStubTeable({ "GET /api/table/tbl1/field": () => ({ body: fields }),
    "DELETE /api/table/tbl1/record": () => ({ body: {} }),
    "DELETE /api/v2/tables/deleteRecords": () => ({ body: { deletedCount: 3 } }) });
  const c = await connectClient(stub.url);
  expect(parseText(await c.callTool({ name: "delete-records", arguments: { tableId: "tbl1", recordIds: ["rec1", "rec2"] } }) as any))
    .toEqual({ success: true, deletedCount: 2 });
  expect(stub.calls.find((x) => x.path === "/api/table/tbl1/record")!.query.getAll("recordIds")).toEqual(["rec1", "rec2"]);
  expect(parseText(await c.callTool({ name: "delete-records", arguments: { tableId: "tbl1", filter: { fieldId: "name", operator: "is", value: "A" } } }) as any))
    .toEqual({ success: true, deletedCount: 3 });
  expect(stub.calls.at(-1)!.body).toEqual({ tableId: "tbl1", filter: { fieldId: "fldName0001", operator: "is", value: "A" } });
});
```
- [ ] **Step 2: run, expect FAIL** — `make test server/test/create-records.test.ts server/test/update-records.test.ts server/test/delete-records.test.ts` → `Tool … not found`.
- [ ] **Step 3: implement** `rows.ts` and the three tools per the interface; append them to `TOOLS`.
- [ ] **Step 4: run, expect PASS** — same command → `7 passed`.
- [ ] **Step 5: mutations** — S11: remove the `assertRectangular` call → "rejects ragged rows without a request" FAIL. S12: drop the both-given check in delete-records → "rejects filter plus recordIds" FAIL. Revert both.
- [ ] **Step 6: commit** `feat(server): add create, update and delete record tools`.

### Task A9: Full tool list and annotations

**Files:** Test `server/test/tools-list.test.ts`, `server/test/annotations.test.ts`; Modify `server/src/tools/index.ts` only if the order or the count is wrong.

**Interfaces:** Consumes all tools (A4–A8). Produces the final `TOOLS`, in the order of decision 2.

- [ ] **Step 1: tests**

`server/test/tools-list.test.ts` (S1)
```ts
import { it, expect, afterEach } from "vitest";
import { startStubTeable } from "./helpers/stub-teable.js";
import { connectClient } from "./helpers/mcp-client.js";

export const TWELVE = ["list-bases","get-tables-meta","get-fields","get-records","sql-query","get-doc","search-api",
  "call-api-read","create-records","update-records","delete-records","call-api-write"];
let stub: Awaited<ReturnType<typeof startStubTeable>>;
afterEach(() => stub?.close());

it("lists exactly the 12 tools", async () => {
  stub = await startStubTeable({});
  const c = await connectClient(stub.url, "read-only-token");
  const { tools } = await c.listTools();
  expect(tools.map((t) => t.name)).toEqual(TWELVE);
});
```
`server/test/annotations.test.ts` (S2)
```ts
import { it, expect, afterEach } from "vitest";
import { startStubTeable } from "./helpers/stub-teable.js";
import { connectClient } from "./helpers/mcp-client.js";

let stub: Awaited<ReturnType<typeof startStubTeable>>;
afterEach(() => stub?.close());
const READS = ["list-bases","get-tables-meta","get-fields","get-records","sql-query","get-doc","search-api","call-api-read"];
const DESTRUCTIVE = ["update-records","delete-records","call-api-write"];

it("write tools carry destructive/readOnly hints", async () => {
  stub = await startStubTeable({});
  const c = await connectClient(stub.url);
  const byName = Object.fromEntries((await c.listTools()).tools.map((t) => [t.name, t]));
  for (const n of READS) expect(byName[n].annotations, n).toMatchObject({ readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false });
  for (const n of DESTRUCTIVE) expect(byName[n].annotations, n).toMatchObject({ readOnlyHint: false, destructiveHint: true });
  expect(byName["create-records"].annotations).toMatchObject({ readOnlyHint: false, destructiveHint: false });
  for (const t of Object.values(byName)) expect((t as any).annotations.title, t.name).toBeTruthy();
});
```
- [ ] **Step 2: run** — `make test server/test/tools-list.test.ts server/test/annotations.test.ts`. If the order differs, reorder `TOOLS` to `TWELVE`. Expected after the fix: `2 passed`.
- [ ] **Step 3: mutations** — S1: remove `call-api-write` from `TOOLS` → "lists exactly the 12 tools" FAIL. S2: set delete-records to `WRITE(false)` → annotations FAIL. Revert.
- [ ] **Step 4: full chain run** — `make test` → all server test files pass; last line `make test: OK (test-server)`.
- [ ] **Step 5: commit** `test(server): pin the 12-tool list and annotations`.

### Task A10: Stateless Streamable HTTP transport (port) and CLI wiring

**Files:** Create `server/src/http.ts`; Modify `server/src/index.ts`; Test `server/test/http.test.ts`, extend `server/test/cli.test.ts`.

**Source to port:** `git -C /mnt/HC_Volume_106183673/projekte/teable-mcp show f053f03:src/http/server.ts` and `git -C … show 45f55f4:src/index.ts` (MIT). Keep the header line from Global Constraints. Changes against the original:
- (1) `listen(port, host)`, with host from `config.http.host` (default `127.0.0.1`).
- (2) The client is built from the request bearer only; there is no env fallback.
- (3) It uses `createMcpServer(client, config)` from A4.
- (4) Env names are as in spec §4.3.

**Interfaces:**
- Produces: `interface HttpServerOptions { host: string; port: number; teableUrl: string; allowedOrigins: string[]; config: Config }`; `createHttpRequestListener(o): http.RequestListener`; `startHttpServer(o): Promise<http.Server>`. CLI: `main()` runs stdio or http per `loadConfig`. In http mode it logs `open-table-agent: listening on http://<host>:<port>/mcp` to stderr.

- [ ] **Step 1: failing tests** `server/test/http.test.ts` (S4, S5). The structure follows teable-mcp `tests/http-server.test.ts` (MIT); assertions are extended.
```ts
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import type { Server } from "node:http";
import type { AddressInfo } from "node:net";
import { startStubTeable } from "./helpers/stub-teable.js";
import { startHttpServer } from "../src/http.js";
import { loadConfig } from "../src/config.js";

let stub: Awaited<ReturnType<typeof startStubTeable>>;
let srv: Server; let base: string;
const H = { "content-type": "application/json", accept: "application/json, text/event-stream" };
const rpc = (method: string, params: object = {}) => JSON.stringify({ jsonrpc: "2.0", id: 1, method, params });

beforeAll(async () => {
  stub = await startStubTeable({ "GET /api/base/access/all": () => ({ body: [] }) });
  const config = loadConfig(["--http"], { TEABLE_URL: stub.url, TEABLE_TOKEN: "ENV-TOKEN-MUST-NOT-LEAK", OTA_HTTP_PORT: "0" });
  srv = await startHttpServer({ host: "127.0.0.1", port: 0, teableUrl: stub.url, allowedOrigins: ["https://ok.example"], config });
  base = `http://127.0.0.1:${(srv.address() as AddressInfo).port}`;
});
afterAll(async () => { srv.close(); await stub.close(); });

describe("http transport", () => {
  it("health is open", async () => { expect((await fetch(`${base}/health`)).status).toBe(200); });
  it("rejects missing bearer with 401", async () => {
    expect((await fetch(`${base}/mcp`, { method: "POST", headers: H, body: rpc("tools/list") })).status).toBe(401);
  });
  it("GET is 405 with Allow: POST", async () => {
    const r = await fetch(`${base}/mcp`, { headers: { authorization: "Bearer x" } });
    expect(r.status).toBe(405); expect(r.headers.get("allow")).toBe("POST");
  });
  it("foreign Origin is 403", async () => {
    expect((await fetch(`${base}/mcp`, { method: "POST", headers: { ...H, authorization: "Bearer x", origin: "https://evil.example" }, body: rpc("tools/list") })).status).toBe(403);
  });
  it("forwards caller bearer to Teable", async () => {
    const r = await fetch(`${base}/mcp`, { method: "POST", headers: { ...H, authorization: "Bearer caller-secret" },
      body: rpc("tools/call", { name: "list-bases", arguments: {} }) });
    expect(r.status).toBe(200);
    expect(stub.calls.map((c) => c.authorization)).toEqual(["Bearer caller-secret"]);
  });
  it("tools/list over HTTP returns 12 tools", async () => {
    const r = await fetch(`${base}/mcp`, { method: "POST", headers: { ...H, authorization: "Bearer x" }, body: rpc("tools/list") });
    expect((await r.json()).result.tools).toHaveLength(12);
  });
});
```
Add to `cli.test.ts`: `it("binds to 127.0.0.1 by default")`. Spawn `src/index.ts --http` with `TEABLE_URL=http://127.0.0.1:9` and `OTA_HTTP_PORT=0`, wait for the stderr line `listening on http://127.0.0.1:`, then kill the process.
ANNAHME: a stateless server answers `tools/list` without a prior `initialize` (teable-mcp's test 3 did so with SDK 1.24.3). If SDK 1.32 requires `initialize` first, send `initialize` in the same test before `tools/list`.
- [ ] **Step 2: run, expect FAIL** — `make test server/test/http.test.ts server/test/cli.test.ts` → module not found / timeout.
- [ ] **Step 3: implement** the port with changes (1)–(4). `index.ts`: stdio → `createMcpServer(new TeableClient(config.token!, config.teableUrl), config).connect(new StdioServerTransport())`; http → `startHttpServer`.
- [ ] **Step 4: run, expect PASS** — same command → all pass.
- [ ] **Step 5: mutations** — S4: in `http.ts` construct the client with `options.config.token ?? token` and set `TEABLE_TOKEN` → "forwards caller bearer to Teable" FAIL (the stub sees `Bearer ENV-TOKEN-MUST-NOT-LEAK`). S5: delete the 401 branch → "rejects missing bearer with 401" FAIL. Revert.
- [ ] **Step 6: build check** — `npm run build --prefix server` → exit 0, `server/dist/index.js` exists. Then `make test` → `make test: OK (test-server)`.
- [ ] **Step 7: commit** `feat(server): port stateless Streamable HTTP transport with per-request bearer`.

### Task A11: Documentation (server README, Hermes wiring)

**Files:** Create `server/README.md`, `docs/hermes.md`.

- [ ] **Step 1:** `server/README.md`: install (`npm ci --prefix server`, `npm run build --prefix server`), env table (spec §4.3), stdio and http run commands, the tool table (spec §4.6), licence notes (MIT; ported code; bundled docs). The HTTP section is ported from teable-mcp `a015834` README text (MIT) and adapted to our env names.
- [ ] **Step 2:** `docs/hermes.md` with the content of spec §9: the agent user + token setup with the exact scope list including `base|query_data`, both YAML blocks, where the token lives (`.env` `OTA_TEABLE_TOKEN`), and a "check it" section.
  ANNAHME check: `grep -n "def _interpolate\|\${" /home/birk/.hermes/hermes-agent/tools/mcp_tool_config.py` to confirm that stdio `env` values are interpolated. If they are not, document `env: {TEABLE_TOKEN: …}` as needing the literal value via a profile-specific mechanism, and say so.
- [ ] **Step 3: verify** — `grep -c "mcp_servers:" docs/hermes.md` → `2`; `grep -c "base|query_data" docs/hermes.md` → ≥ `1`; `make test` still `OK (test-server)`.
- [ ] **Step 4: commit** `docs: add server README and Hermes wiring guide`.

---

## Chain B — upstream patch

**Owned files:** `patches/**`, `mk/patches.mk`. **Base:** `main` after this plan's commit. **Test command:** `make test` (targeted `make test patches`). **Size:** S. **Depends on:** the local upstream object store `/mnt/HC_Volume_106183673/projekte/teable-fork/.git` containing `fc4126e945a212aa637c4134c373416df69bb982` (verified 2026-11-12).

Shared facts (spec §5.1): `NNNN-<slug>.patch`, `git format-patch` mbox, base sha in `patches/BASE`, applied with `git am --3way`.

### Task B1: Patch-series tests, BASE, README, make fragment

**Files:** Create `patches/BASE`, `patches/README.md`, `patches/tests/test_patch_series.py`, `mk/patches.mk`.

**Interfaces:**
- Produces: `patches/BASE` = `fc4126e945a212aa637c4134c373416df69bb982\n`. Env `OTA_UPSTREAM_GIT_DIR` (default `/mnt/HC_Volume_106183673/projekte/teable-fork/.git`).
- `mk/patches.mk`:
```make
ifneq ($(call ota_selected,patches),)
TEST_TARGETS += test-patches
endif
.PHONY: test-patches
test-patches:
	python3 -m unittest discover -s patches/tests -t . -v
```
- [ ] **Step 1: write tests** `patches/tests/test_patch_series.py`
```python
"""Static checks of the AGPL patch series (spec §5, MUSTs P1-P4). No network, no checkout."""
import os, re, subprocess, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATCH_DIR = ROOT / "patches"
UPSTREAM = os.environ.get("OTA_UPSTREAM_GIT_DIR", "/mnt/HC_Volume_106183673/projekte/teable-fork/.git")
ALLOWED = {
    "apps/nestjs-backend/src/features/base-sql-executor/base-sql-query.controller.ts",
    "apps/nestjs-backend/src/features/base-sql-executor/base-sql-executor.module.ts",
    "apps/nestjs-backend/src/features/base/base.module.ts",
    "apps/nestjs-backend/test/admin/table-route-ledger.ts",
}

def series():
    files = sorted(PATCH_DIR.glob("[0-9][0-9][0-9][0-9]-*.patch"))
    if not files:
        raise AssertionError("no patches/NNNN-*.patch found")
    return files

class PatchSeries(unittest.TestCase):
    def test_base_is_a_full_sha(self):
        self.assertRegex((PATCH_DIR / "BASE").read_text().strip(), r"^[0-9a-f]{40}$")

    def test_touches_only_allowlisted_paths(self):
        touched = set()
        for p in series():
            touched |= set(re.findall(r"^diff --git a/(\S+) b/", p.read_text(), re.M))
        self.assertEqual(touched - ALLOWED, set())

    def test_route_permission(self):
        text = (PATCH_DIR / "0001-sql-query-route.patch").read_text()
        self.assertIn("+  @Post(':baseId/sql-query')", text)
        self.assertIn("+  @Permissions('base|query_data')", text)
        self.assertRegex(text, r"(?m)^-\s*'POST /api/base/:baseId/sql-query': 'EE',$")

    def test_readme_states_agpl(self):
        self.assertIn("AGPL-3.0", (PATCH_DIR / "README.md").read_text())

    def test_applies_to_base(self):
        base = (PATCH_DIR / "BASE").read_text().strip()
        if not Path(UPSTREAM).exists():
            self.fail(f"upstream git dir {UPSTREAM} missing; set OTA_UPSTREAM_GIT_DIR")
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "GIT_DIR": UPSTREAM, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
            r = subprocess.run(["git", "read-tree", base], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"BASE {base} not in {UPSTREAM}: {r.stderr}")
            for p in series():
                r = subprocess.run(["git", "apply", "--cached", "--check", "-v", str(p)], env=env, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, f"{p.name} does not apply to {base}:\n{r.stderr}")
                subprocess.run(["git", "apply", "--cached", str(p)], env=env, check=True, capture_output=True)

if __name__ == "__main__":
    unittest.main()
```
Note: `git apply --cached` with `GIT_INDEX_FILE` writes only the temporary index. The upstream repo's own index and working tree are not touched. ANNAHME: `git apply --cached` accepts an mbox (format-patch) file. It does: it skips the mail header. Step 4 of B2 confirms this.
- [ ] **Step 2: write** `patches/BASE` and `patches/README.md`. The README states: the AGPL-3.0 sentence from spec §5.2; the base; how to regenerate (clone `--shared` into `.work/`, `git checkout <BASE>`, `git am patches/*.patch`, edit, `git format-patch -o patches/ <BASE>`); and that FRAGE-1 decides the permission.
- [ ] **Step 3: run, expect FAIL** — `make test patches` → `test_touches_only_allowlisted_paths … ERROR: no patches/NNNN-*.patch found` (and the same for apply/route); exit 2.
- [ ] **Step 4: commit** `test(patches): add patch-series checks, BASE and AGPL README`.

### Task B2: Write `0001-sql-query-route.patch`

**Files:** Create `patches/0001-sql-query-route.patch`. Scratch (not committed): `.work/b-upstream/`.

**Interfaces:**
- Consumes: CE `BaseSqlExecutorService.executeQuerySql(baseId: string, sql: string, opts?: { parameters?: ReadonlyArray<unknown>; structuredCoverage?: boolean; … })` (`base-sql-executor.service.ts:349`), `Permissions` (`../auth/decorators/permissions.decorator`), `ZodValidationPipe` (`../../zod.validation.pipe`).
- Produces: HTTP contract `POST /api/base/:baseId/sql-query`, body `{sql: string (min 1), parameters?: unknown[]}`, response `200 {rows: object[]}`. Guard `base|query_data`. Used by server A6 and e2e D3.

- [ ] **Step 1: scratch tree** — `git clone --shared --no-checkout /mnt/HC_Volume_106183673/projekte/teable-fork .work/b-upstream`, then `git -C .work/b-upstream checkout --detach fc4126e945a212aa637c4134c373416df69bb982`. Make sure `.work/` is never staged: `git status --porcelain` must not list it; it is ignored after Chain C merges. Until then, add files only by explicit path.
- [ ] **Step 2: write the controller** `.work/b-upstream/apps/nestjs-backend/src/features/base-sql-executor/base-sql-query.controller.ts` (AGPL file inside the patch):
```ts
import { Body, Controller, Param, Post } from '@nestjs/common';
import { z } from 'zod';
import { ZodValidationPipe } from '../../zod.validation.pipe';
import { Permissions } from '../auth/decorators/permissions.decorator';
import { BaseSqlExecutorService } from './base-sql-executor.service';

const baseSqlQueryRoSchema = z.object({
  sql: z.string().min(1),
  parameters: z.array(z.unknown()).optional(),
});
type IBaseSqlQueryRo = z.infer<typeof baseSqlQueryRoSchema>;

const toJsonSafe = (value: unknown): unknown => {
  if (typeof value === 'bigint') {
    return Number.isSafeInteger(Number(value)) ? Number(value) : value.toString();
  }
  if (Array.isArray(value)) return value.map(toJsonSafe);
  if (value && typeof value === 'object') {
    if (typeof (value as { toJSON?: unknown }).toJSON === 'function') return value;
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, toJsonSafe(v)]));
  }
  return value;
};

@Controller('api/base/')
export class BaseSqlQueryController {
  constructor(private readonly baseSqlExecutorService: BaseSqlExecutorService) {}

  @Post(':baseId/sql-query')
  @Permissions('base|query_data')
  async sqlQuery(
    @Param('baseId') baseId: string,
    @Body(new ZodValidationPipe(baseSqlQueryRoSchema)) ro: IBaseSqlQueryRo
  ): Promise<{ rows: unknown[] }> {
    const rows = await this.baseSqlExecutorService.executeQuerySql<unknown[]>(baseId, ro.sql, {
      parameters: ro.parameters,
      structuredCoverage: true,
    });
    return { rows: toJsonSafe(rows) as unknown[] };
  }
}
```
ANNAHME: the backend imports `zod` directly (`import { z } from 'zod'`) the way other controllers or schemas do. Check: `grep -rn "from 'zod'" apps/nestjs-backend/src --include=*.controller.ts | head -3` in `.work/b-upstream`. If controllers import from `@teable/core` instead, use that.
ANNAHME: `executeQuerySql`'s generic parameter and the `parameters` option name match `service.ts:349-360`. Read those lines before writing.
- [ ] **Step 3: wire + ledger** in `.work/b-upstream`:
  - `base-sql-executor.module.ts`: add `import { BaseSqlQueryController } from './base-sql-query.controller';` and `controllers: [BaseSqlQueryController],`.
  - `features/base/base.module.ts`: add `import { BaseSqlExecutorModule } from '../base-sql-executor/base-sql-executor.module';` and append `BaseSqlExecutorModule` to `imports`.
  - `test/admin/table-route-ledger.ts`: delete line 72 `'POST /api/base/:baseId/sql-query': 'EE',`.
- [ ] **Step 4: commit in scratch and export** — `git -C .work/b-upstream add -A`, then `git -C .work/b-upstream -c user.name=open-table-agent -c user.email=patches@open-table-agent.invalid commit -m "feat(base): expose read-only SQL query route for the community build"`. Then `git -C .work/b-upstream format-patch -1 --zero-commit --no-signature --start-number 1 -o /mnt/HC_Volume_106183673/projekte/open-table-agent/patches HEAD`, and rename the output to `0001-sql-query-route.patch` if format-patch derived a different slug (`mv`).
- [ ] **Step 5: run, expect PASS** — `make test patches` → `Ran 5 tests … OK`; `make test: OK (test-patches)`.
- [ ] **Step 6: mutations** — P1: in the patch, change one context line (leading space) of the `base.module.ts` hunk → `test_applies_to_base` FAIL (`does not apply`). P2: change the permission to `base|read` → `test_route_permission` FAIL. P3: add an empty `diff --git a/apps/nestjs-backend/src/app.module.ts b/…` header block → `test_touches_only_allowlisted_paths` FAIL. P4: delete the AGPL sentence → `test_readme_states_agpl` FAIL. Revert each (`git checkout -- patches/`).
- [ ] **Step 7: commit** `feat(patches): add 0001-sql-query-route (AGPL)`.

### Task B3: Type-check the patched backend (best effort, reported)

**Files:** none committed (the result goes into the commit message of B2's follow-up or into the chain's handoff note).

- [ ] **Step 1:** `pnpm --dir .work/b-upstream install --frozen-lockfile --ignore-scripts` (registry.npmjs.org reachable; `--ignore-scripts` avoids the prisma engine download, FRAGE-2).
- [ ] **Step 2:** `pnpm --dir .work/b-upstream -F @teable/backend exec tsc --noEmit -p tsconfig.json`. Expected: no error in `base-sql-query.controller.ts`, `base-sql-executor.module.ts` or `base.module.ts`. Pre-existing errors elsewhere (e.g. a missing generated prisma client) are listed but not fixed. If the generated prisma client is missing, the command reports `Cannot find module '@prisma/client'`-type errors in unrelated files. In that case filter: `grep -E "base-sql-query|base-sql-executor.module|base/base.module"` on the output must print nothing.
  ANNAHME: the backend package name is `@teable/backend` (check `apps/nestjs-backend/package.json` `name`).
- [ ] **Step 3:** if Step 1 or 2 cannot run, report the reason in the chain's final message. Chain D's image build is then the first compile of the patch.

---

## Chain C — sync script

**Owned files:** `scripts/sync-upstream.py`, `scripts/tests/**`, `mk/sync.mk`, `.gitignore`. **Base:** `main` after this plan's commit. **Test command:** `make test` (targeted `make test scripts`). **Size:** M. **Depends on:** nothing (tests build synthetic repos; real patches are exercised in D4).

**CLI contract (spec §6):**
```
scripts/sync-upstream.py [--upstream-url URL] [--ref REF | --tag TAG] [--dry-run] [--build]
                         [--work-dir .work] [--lock upstream.lock.json] [--patches patches]
```
- `REF` without a `refs/` prefix means `refs/heads/REF`. `--tag T` means `refs/tags/T`.
- stdout lines (machine-greppable):
  - `UPSTREAM <sha>`
  - `PATCHED <sha>`
  - `IMAGE <tag>`
  - `BUILD <command>` (printed without `--build`)
  - `UP-TO-DATE <sha>`
  - `DRY-RUN ok`
  - `CONFLICT patch=<file> path=<path> hunk=<@@ … @@>`
- Exit codes: 0 / 1 conflict / 2 usage-env / 3 build.

### Task C1: Fixtures, clean apply, lock file

**Files:** Create `scripts/sync-upstream.py`, `scripts/tests/__init__.py` (empty), `scripts/tests/fixtures.py`, `scripts/tests/test_sync_upstream.py`, `mk/sync.mk`, `.gitignore`.

**Interfaces:**
- Produces, in `scripts/tests/fixtures.py`:
  - `make_upstream(tmp: Path) -> tuple[Path, str]`: `git init -b develop`, a non-bare repo with `app/module.ts` (10 lines) and `README`, one commit on `develop`; returns (path, sha).
  - `make_patch(upstream: Path, out_dir: Path, name="0001-demo.patch") -> Path`: clones, edits line 5 of `app/module.ts`, adds `app/new.ts`, commits, and `git format-patch`es into `out_dir/name`.
  - `run_sync(tmp: Path, *args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess`: runs `python3 <ROOT>/scripts/sync-upstream.py --work-dir <tmp>/.work --lock <tmp>/upstream.lock.json *args` with `cwd=tmp` and `text=True`, capturing output. The tests pass `--upstream-url` and `--patches` themselves.
- Produces, in the script: `main(argv) -> int`; the lock schema exactly as in spec §6.

`mk/sync.mk`
```make
ifneq ($(call ota_selected,scripts),)
TEST_TARGETS += test-sync
endif
.PHONY: test-sync
test-sync:
	python3 -m unittest discover -s scripts/tests -t . -v
```
`.gitignore`: `.work/` and `.scratch/`.

- [ ] **Step 1: failing test** (C1)
```python
# scripts/tests/test_sync_upstream.py
import json, tempfile, unittest
from pathlib import Path
from scripts.tests.fixtures import make_upstream, make_patch, run_sync

class SyncUpstream(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.upstream, self.sha = make_upstream(self.tmp / "up")
        self.patches = self.tmp / "patches"
        make_patch(self.upstream, self.patches)

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_apply_writes_lock(self):
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"UPSTREAM {self.sha}", r.stdout)
        lock = json.loads((self.tmp / "upstream.lock.json").read_text())
        self.assertEqual(lock["schema"], 1)
        self.assertEqual(lock["upstream"], {"url": str(self.upstream), "ref": "refs/heads/develop", "sha": self.sha})
        self.assertEqual([p["file"] for p in lock["patches"]], ["0001-demo.patch"])
        self.assertRegex(lock["patches"][0]["sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(lock["patched_commit"], r"^[0-9a-f]{40}$")
        self.assertTrue(lock["image"]["tag"].startswith(f"localhost/ota-teable:{self.sha[:12]}-"))
        self.assertIn("BUILD podman build -f dockers/teable/Dockerfile", r.stdout)
        wt = self.tmp / ".work" / f"teable-{self.sha[:12]}"
        self.assertTrue((wt / "app" / "new.ts").exists())
```
- [ ] **Step 2: run, expect FAIL** — `make test scripts` → `can't open file … sync-upstream.py` → assertion error, exit 2.
- [ ] **Step 3: implement** `scripts/sync-upstream.py`. Core structure (complete these functions; stdlib only):
```python
#!/usr/bin/env python3
"""Fetch upstream Teable, apply patches/*.patch in a fresh worktree, record upstream.lock.json (spec §6)."""
from __future__ import annotations
import argparse, datetime, hashlib, json, re, subprocess, sys
from pathlib import Path

DEFAULT_URL = "https://github.com/teableio/teable.git"
IDENT = ["-c", "user.name=open-table-agent-sync", "-c", "user.email=sync@open-table-agent.invalid"]

class EnvError(Exception): pass

def git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise EnvError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r

def full_ref(ref: str | None, tag: str | None) -> str:
    if tag: return f"refs/tags/{tag}"
    ref = ref or "develop"
    return ref if ref.startswith("refs/") else f"refs/heads/{ref}"

def fetch(cache: Path, url: str, ref: str) -> str:
    if not cache.exists():
        git("init", "--bare", "--quiet", str(cache))
    git("fetch", "--no-tags", "--quiet", url, f"+{ref}:refs/ota/upstream", cwd=cache)
    return git("rev-parse", "refs/ota/upstream^{commit}", cwd=cache).stdout.strip()

def patch_files(d: Path) -> list[Path]:
    files = sorted(d.glob("[0-9][0-9][0-9][0-9]-*.patch"))
    if not files: raise EnvError(f"no NNNN-*.patch in {d}")
    return files

def sha256(p: Path) -> str: return hashlib.sha256(p.read_bytes()).hexdigest()

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
        if m: cur = m.group(1)
        h = re.match(r"(@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@)", l)
        if h and cur == path and int(h.group(2)) == old_start: return h.group(1)
    return f"@@ -{old_start} @@"

def apply_series(wt: Path, patches: list[Path]) -> list[str]:
    """Apply one patch per `git am` session; return CONFLICT lines (empty = success)."""
    for p in patches:
        r = git(*IDENT, "am", "--3way", "--quiet", str(p.resolve()), cwd=wt, check=False)
        if r.returncode != 0:
            git("am", "--abort", cwd=wt, check=False)
            return [f"CONFLICT patch={p.name} {h}" for h in hunk_report(wt, p)]
    return []
```
`main` wires these together:
1. Parse args. Check `git --version` (missing → `EnvError`, exit 2).
2. `ref = full_ref(...)`, `cache = work/"upstream.git"`, `sha = fetch(...)`, print `UPSTREAM sha`.
3. `files = patch_files(...)`, `hashes = [sha256(f) …]`, `tag = image_tag(...)`.
4. Up-to-date check (Task C3).
5. `wt = work/("dry-run-" if dry else "teable-") + sha[:12]`, `fresh_worktree`.
6. `conflicts = apply_series(...)`. If any: print each, `git worktree remove --force` the worktree (dry run or not), exit 1.
7. `patched = git rev-parse HEAD`. Print `PATCHED`, `IMAGE`.
8. Dry run: remove the worktree, print `DRY-RUN ok`, exit 0.
9. Otherwise write the lock `{"schema":1, "upstream":{"url","ref","sha"}, "patches":[{"file","sha256"}], "patched_commit", "image":{"tag","built":False}, "generated_at": UTC ISO}` with `indent=2` and a trailing newline.
10. `--build` → run `podman build -f dockers/teable/Dockerfile -t <tag> <wt>` (exit 3 on failure; set `image.built=True` and rewrite the lock on success). Otherwise print `BUILD podman build -f dockers/teable/Dockerfile -t <tag> <wt>`.

Catch `EnvError` → stderr `sync-upstream: <msg>`, exit 2.
- [ ] **Step 4: run, expect PASS** — `make test scripts` → `test_clean_apply_writes_lock … ok`; `make test: OK (test-sync)`.
- [ ] **Step 5: mutation C1** — write `"patches": []` into the lock → the test FAILs. Revert.
- [ ] **Step 6: commit** `feat(sync): fetch upstream, apply patch series and write lock file`.

### Task C2: Conflict report (mutation: broken hunk context)

**Files:** Modify `scripts/tests/test_sync_upstream.py`, `scripts/tests/fixtures.py` (add `break_context(patch: Path) -> None`: rewrites the first context line, i.e. the first line starting with a single space after the first `@@` line, to ` BROKEN CONTEXT`).

- [ ] **Step 1: failing test** (C2)
```python
    def test_broken_context_reports_conflict(self):
        from scripts.tests.fixtures import break_context
        break_context(self.patches / "0001-demo.patch")
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"CONFLICT patch=0001-demo\.patch path=app/module\.ts hunk=@@ -\d+,\d+ \+\d+,\d+ @@")
        self.assertIn(f"UPSTREAM {self.sha}", r.stdout)
        self.assertFalse((self.tmp / "upstream.lock.json").exists())
```
- [ ] **Step 2: run** — `make test scripts`. If C1's implementation already handles it, the test passes immediately. Then run the mutation (Step 3) to prove that the test bites.
- [ ] **Step 3: mutation C2** — in `apply_series` ignore the return code (`if False and r.returncode != 0`) → `test_broken_context_reports_conflict` FAIL (exit 0 or lock written). Revert.
- [ ] **Step 4: commit** `test(sync): report the failing patch and hunk on conflict`.

### Task C3: Fetched ref wins over local branches; idempotence; dry run

**Files:** Modify `scripts/sync-upstream.py`, `scripts/tests/test_sync_upstream.py`.

- [ ] **Step 1: failing tests** (C3, C4, C5)
```python
    def test_ignores_local_branch_with_extra_commit(self):
        import subprocess
        cache = self.tmp / ".work" / "upstream.git"
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches), "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        # plant a local 'develop' in the cache that carries an extra commit (the teable-fork trap)
        wt = self.tmp / "plant"
        subprocess.run(["git", "clone", "-q", str(self.upstream), str(wt)], check=True)
        (wt / "extra.txt").write_text("x")
        subprocess.run(["git", "-C", str(wt), "add", "."], check=True)
        subprocess.run(["git", "-C", str(wt), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "local"], check=True)
        subprocess.run(["git", "-C", str(wt), "push", "-q", str(cache), "HEAD:refs/heads/develop"], check=True)
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches))
        self.assertIn(f"UPSTREAM {self.sha}", r.stdout)

    def test_second_run_is_up_to_date(self):
        a = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches))
        lock1 = (self.tmp / "upstream.lock.json").read_text()
        b = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches))
        self.assertEqual((a.returncode, b.returncode), (0, 0))
        self.assertIn(f"UP-TO-DATE {self.sha}", b.stdout)
        self.assertEqual((self.tmp / "upstream.lock.json").read_text(), lock1)

    def test_dry_run_leaves_no_trace(self):
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches), "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("DRY-RUN ok", r.stdout)
        self.assertFalse((self.tmp / "upstream.lock.json").exists())
        self.assertEqual([p.name for p in (self.tmp / ".work").iterdir()], ["upstream.git"])
```
- [ ] **Step 2: run, expect FAIL** — `make test scripts` → `test_second_run_is_up_to_date` fails (no `UP-TO-DATE`). The others may already pass.
- [ ] **Step 3: implement** the up-to-date check in `main`. Load the existing lock. If its `upstream` equals `{url, ref, sha}`, its `[sha256]` equals `hashes`, and the worktree `teable-<sha12>` exists with `git rev-parse HEAD == patched_commit`: print `UP-TO-DATE <sha>` and return 0, but still run the build if `--build` is set and `image.built` is false. A dry run skips this check.
- [ ] **Step 4: run, expect PASS** — `make test scripts` → `Ran 5 tests … OK`.
- [ ] **Step 5: mutations** — C3: in `fetch` return `git rev-parse develop` (the cache-local branch) → `test_ignores_local_branch_with_extra_commit` FAIL. C4: skip the up-to-date check → `test_second_run_is_up_to_date` FAIL. C5: write the lock also in dry run → `test_dry_run_leaves_no_trace` FAIL. Revert each.
- [ ] **Step 6: commit** `feat(sync): idempotent re-runs, dry-run mode, fetched ref is authoritative`.

### Task C4: `--tag`, usage errors, `--build` command path

**Files:** Modify `scripts/sync-upstream.py`, `scripts/tests/test_sync_upstream.py`.

- [ ] **Step 1: tests**
```python
    def test_tag_and_usage_errors(self):
        import subprocess
        subprocess.run(["git", "-C", str(self.upstream), "tag", "release.test.1"], check=True)
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches), "--tag", "release.test.1", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.tmp / "empty"), "--dry-run")
        self.assertEqual(r.returncode, 2)
        self.assertIn("sync-upstream: no NNNN-*.patch", r.stderr)
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches), "--ref", "develop", "--tag", "x")
        self.assertEqual(r.returncode, 2)

    def test_build_failure_exit_3(self):
        r = run_sync(self.tmp, "--upstream-url", str(self.upstream), "--patches", str(self.patches), "--build",
                     env_extra={"OTA_PODMAN": "false"})
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertFalse(json.loads((self.tmp / "upstream.lock.json").read_text())["image"]["built"])
```
Implementation notes:
- `--ref` and `--tag` go in an argparse mutually exclusive group.
- The podman binary comes from env `OTA_PODMAN` (default `podman`), so the test needs neither containers nor podman.
- `run_sync` gains `env_extra`.
- `(self.tmp / "empty")` is created empty in the test (`mkdir`).
- [ ] **Step 2: run, expect FAIL → implement → PASS** — `make test scripts` → `Ran 7 tests … OK`; `make test: OK (test-sync)`.
- [ ] **Step 3: commit** `feat(sync): support pinned tags, usage errors and build exit code`.

---

## Chain D — end-to-end (after A, B, C are merged into `main`)

**Owned files:** `e2e/**`, `mk/e2e.mk`, `upstream.lock.json`, `README.md`. **Base:** `main` after A, B, C are merged. **Test command:** `make test` (must stay green; D adds nothing to `TEST_TARGETS`) and `make e2e`. **Size:** M–L (long image build). **External gates:** admin steps 1–3 (below) and FRAGE-2.

`mk/e2e.mk`
```make
E2E_TARGETS += e2e-sync e2e-run
.PHONY: e2e-run e2e-sync
e2e-run: e2e/node_modules/.ota-stamp
	python3 e2e/stack.py up || { python3 e2e/stack.py down; exit 1; }
	python3 e2e/bootstrap.py > e2e/.env.e2e ; status=$$?; \
	if [ $$status -eq 0 ]; then npm run build --prefix server && (cd e2e && npx vitest run); status=$$?; fi; \
	python3 e2e/stack.py down; exit $$status
e2e-sync:
	python3 -m unittest -v e2e.tests.test_sync_real
e2e/node_modules/.ota-stamp: e2e/package-lock.json
	cd e2e && npm ci --no-audit --no-fund
	touch $@
```

### Task D1: Real sync + image build probe (E4)

**Preconditions:** admin steps 1–2 done (the 5 images are loaded: `podman images` lists node 24.22.2 bookworm and bookworm-slim, `tianon/gosu:1.19`, `postgres:15.4`, `redis:7.2.4`); FRAGE-2 resolved.

**Files:** Create `e2e/__init__.py`, `e2e/tests/__init__.py`, `e2e/tests/test_sync_real.py`, `mk/e2e.mk`; commit `upstream.lock.json`.

- [ ] **Step 1: test** `e2e/tests/test_sync_real.py`
```python
"""E4: real upstream develop (network: github.com). Not part of `make test`."""
import re, shutil, subprocess, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def sync(*args):
    return subprocess.run(["python3", str(ROOT / "scripts/sync-upstream.py"), *args], cwd=ROOT, capture_output=True, text=True)

class RealSync(unittest.TestCase):
    def test_real_develop_applies(self):
        r = sync("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"(?m)^UPSTREAM [0-9a-f]{40}$")

    def test_real_develop_broken_copy_conflicts(self):
        with tempfile.TemporaryDirectory() as d:
            for p in (ROOT / "patches").glob("*.patch"): shutil.copy(p, d)
            p = Path(d) / "0001-sql-query-route.patch"
            text = p.read_text()
            i = text.index("base.module.ts\n")
            j = text.index("\n ", text.index("@@", i))  # first context line of that file's hunk
            p.write_text(text[:j + 1] + " BROKEN" + text[j + 1:])
            r = sync("--dry-run", "--patches", d)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertRegex(r.stdout, r"CONFLICT patch=0001-sql-query-route\.patch path=apps/nestjs-backend/src/features/base/base\.module\.ts")
```
- [ ] **Step 2: run** — `make e2e-sync` → `Ran 2 tests … OK` (needs github.com; first fetch can take minutes; Bash timeout 900000).
- [ ] **Step 3: build probe** — `python3 scripts/sync-upstream.py --build` (Bash timeout 900000; if it runs longer, rerun it — it is idempotent and only rebuilds). Expected: `UPSTREAM <sha>`, `PATCHED <sha>`, `IMAGE localhost/ota-teable:<sha12>-<8>`, exit 0, and `podman images` shows the tag. On failure, record the failing stage and the unreachable host or unsupported instruction. Expected suspects: `prisma generate` → FRAGE-2; `COPY --link` unsupported by buildah 1.28. Do not edit the upstream Dockerfile to work around it, because that would be a second patch. End the run with a `FRAGE:` line naming the failure.
- [ ] **Step 4: commit** `upstream.lock.json` (now `image.built: true`) and the files above: `test(e2e): real upstream sync and patched image build`.

### Task D2: Stack lifecycle and bootstrap

**Files:** Create `e2e/stack.py`, `e2e/bootstrap.py`, `e2e/.gitignore` (`node_modules/`, `.env.e2e`).

**Interfaces:**
- `e2e/stack.py up|down|status`:
  - `up`: reads `image.tag` from `upstream.lock.json`, then:
    - `podman pod create --name ota-e2e -p 127.0.0.1:3010:3000`
    - `podman run -d --pod ota-e2e --name ota-e2e-db -e POSTGRES_USER=teable -e POSTGRES_PASSWORD=<random> -e POSTGRES_DB=teable docker.io/library/postgres:15.4`
    - `podman run -d --pod ota-e2e --name ota-e2e-cache docker.io/library/redis:7.2.4 redis-server --requirepass <random>`
    - `podman run -d --pod ota-e2e --name ota-e2e-teable -e PRISMA_DATABASE_URL=postgresql://teable:<pw>@127.0.0.1:5432/teable -e BACKEND_CACHE_REDIS_URI=redis://default:<pw>@127.0.0.1:6379/0 -e PUBLIC_ORIGIN=http://127.0.0.1:3010 -e SECRET_KEY=<random> <tag>`
    - Then it polls `GET http://127.0.0.1:3010/health` (ANNAHME: CE health path; check `apps/nestjs-backend/src/features/health/`) for up to 300 s.
  - `down`: `podman pod rm -f ota-e2e`.
  - Exit 0 / 1 with the last 50 log lines of the teable container on timeout.
- `e2e/bootstrap.py` → prints `KEY=VALUE` lines: `TEABLE_URL`, `TOKEN_A`, `TOKEN_B`, `BASE_ID`, `TABLE_ID`. It runs over REST:
  - sign up A and B;
  - A creates a space, a base, and a table with fields `Name` (singleLineText) and `Count` (number);
  - A creates a personal access token with scopes `base|read base|query_data table|read field|read record|read record|create record|update record|delete space|read` for that base/space;
  - B creates its own token with the same scopes (B has no access to A's base).
  - ANNAHME: endpoints and bodies. Check in the merged-main checkout of upstream (`.work/teable-<sha12>/packages/openapi/src/auth/signup.ts`, `access-token/create.ts`, `space/create.ts`, `base/create.ts`, `table/create.ts`) before writing; also check whether sign-up needs email verification on CE.
- [ ] **Step 1:** write `stack.py`; run `python3 e2e/stack.py up` (timeout 900000) → exit 0, prints `ready http://127.0.0.1:3010`; `python3 e2e/stack.py down` → exit 0.
- [ ] **Step 2:** write `bootstrap.py`; with the stack up: `python3 e2e/bootstrap.py` → 5 `KEY=VALUE` lines, `TOKEN_A` non-empty.
- [ ] **Step 3: commit** `test(e2e): podman stack and REST bootstrap for a real CE instance`.

### Task D3: Acceptance tests (E1–E3)

**Files:** Create `e2e/package.json` (deps: `@modelcontextprotocol/sdk` ^1.32.2, `vitest` ^5.1.0, `typescript`), `e2e/package-lock.json`, `e2e/tsconfig.json`, `e2e/vitest.config.ts`, `e2e/tests/acceptance.e2e.test.ts`.

- [ ] **Step 1: test** `e2e/tests/acceptance.e2e.test.ts`
```ts
import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "node:fs";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { spawn } from "node:child_process";

const env = Object.fromEntries(readFileSync(new URL("../.env.e2e", import.meta.url), "utf8").trim().split("\n").map((l) => l.split(/=(.*)/s).slice(0, 2)));
const SERVER = new URL("../../server/dist/index.js", import.meta.url).pathname;
const TWELVE = ["list-bases","get-tables-meta","get-fields","get-records","sql-query","get-doc","search-api",
  "call-api-read","create-records","update-records","delete-records","call-api-write"];
const parse = (r: any) => JSON.parse(r.content[0].text);

async function stdioClient(token: string) {
  const c = new Client({ name: "e2e", version: "0" });
  await c.connect(new StdioClientTransport({ command: process.execPath, args: [SERVER],
    env: { PATH: process.env.PATH!, TEABLE_URL: env.TEABLE_URL, TEABLE_TOKEN: token } }));
  return c;
}

describe("real CE", () => {
  let a: Client;
  beforeAll(async () => { a = await stdioClient(env.TOKEN_A); });

  it("lists 12 tools (stdio and HTTP)", async () => {
    expect((await a.listTools()).tools.map((t) => t.name)).toEqual(TWELVE);
    const proc = spawn(process.execPath, [SERVER, "--http"], { env: { PATH: process.env.PATH!, TEABLE_URL: env.TEABLE_URL, OTA_HTTP_PORT: "3199" } });
    try {
      await new Promise((r) => proc.stderr.on("data", (d) => String(d).includes("listening") && r(null)));
      const h = new Client({ name: "e2e-http", version: "0" });
      await h.connect(new StreamableHTTPClientTransport(new URL("http://127.0.0.1:3199/mcp"),
        { requestInit: { headers: { Authorization: `Bearer ${env.TOKEN_A}` } } }));
      expect((await h.listTools()).tools).toHaveLength(12);
    } finally { proc.kill(); }
  });

  it("create then read back by field name filter", async () => {
    const created = parse(await a.callTool({ name: "create-records", arguments: { tableId: env.TABLE_ID, header: ["Name", "Count"], records: [["e2e-a", 7], ["e2e-b", 1]] } }));
    expect(created).toMatchObject({ success: true, recordsCreated: 2 });
    const got = parse(await a.callTool({ name: "get-records", arguments: { tableId: env.TABLE_ID, projection: ["Name", "Count"],
      filter: { conjunction: "and", filterSet: [{ fieldId: "Count", operator: "isGreater", value: 5 }] } } }));
    expect(got.rows.map((r: unknown[]) => r[1])).toEqual(["e2e-a"]);
  });

  it("sql-query returns rows", async () => {
    const t = parse(await a.callTool({ name: "get-tables-meta", arguments: { baseId: env.BASE_ID, tableId: env.TABLE_ID } })).tables[0];
    const from = t.dbTableName.includes(".") ? t.dbTableName.split(".").map((s: string) => `"${s}"`).join(".") : `"${env.BASE_ID}"."${t.dbTableName}"`;
    const r = await a.callTool({ name: "sql-query", arguments: { baseId: env.BASE_ID, sql: `SELECT count(*) AS n FROM ${from}` } });
    expect(r.isError, JSON.stringify(r)).toBeFalsy();
    expect(Number(parse(r).rows[0].n)).toBeGreaterThanOrEqual(2);
  });

  it("sql-query refused without base access", async () => {
    const b = await stdioClient(env.TOKEN_B);
    const r = await b.callTool({ name: "sql-query", arguments: { baseId: env.BASE_ID, sql: "SELECT 1" } });
    expect(r.isError).toBe(true);
    expect(parse(r).status).toBe(403);
  });
});
```
Spec §4.6 item 4 ANNAHME (the `dbTableName` form): the test handles both forms. Afterwards, fix the `sql-query` tool description to the form actually observed. That is a one-line change in `server/src/tools/sql-query.ts`, made in D's branch in agreement with chain A's owner (or as a follow-up card if A is closed).
- [ ] **Step 2: run** — `make e2e` (Bash timeout 900000). Expected: vitest `4 passed`, then `make e2e: OK (e2e-run)`, and the pod is removed (`podman pod ls` empty).
- [ ] **Step 3: mutations**
  - E3: on a scratch branch, rebuild the image from a series without the controller hunk: delete `patches/0001-*.patch`, then `python3 scripts/sync-upstream.py --build` with a temporary patches dir containing only the module/ledger hunks. "sql-query returns rows" then fails with 404.
  - E1: build the server with `get-doc` removed from `TOOLS` → "lists 12 tools" FAIL.
  - E2: apply the S3 mutation → "create then read back by field name filter" FAIL (wrong rows).
  - Revert each mutation and record the observed failures in the commit message.
- [ ] **Step 4:** set the README status line to `Status: implemented; see docs/hermes.md` and commit: `test(e2e): acceptance run against patched CE`.

---

## Critical path

```
this run ──► A (L) ─┐
         ──► B (S) ─┼─► merge into main ──► D1 (needs admin 1–3) ──► D2 ──► D3
         ──► C (M) ─┘
```
- A, B and C run in parallel and share no files. A is the longest (11 tasks) and gates D. B is small, but its `test_applies_to_base` depends on the local teable-fork object store.
- Relative sizes: A ≈ 50 %, C ≈ 20 %, D ≈ 20 %, B ≈ 10 % of the total effort. D's wall-clock is dominated by the first image build (monorepo `pnpm -r run build`; ANNAHME: 20–60 min on 16 cores).
- External gates on D, none of them agent work:
  1. Birk reviews, merges and installs the `image-holen` admin job (chain t_ba874608).
  2. Birk approves 5 image fetches (taps).
  3. FRAGE-2 is decided (prisma engine host).

  D1 cannot start before these. An agent can prepare D's code (D2/D3 files) earlier, but cannot run it.
- D3's sql-query description fix may touch `server/` (A-owned). If chain A is still open, it goes there; otherwise it becomes a one-line follow-up card.

## Preconditions / admin steps for Birk

1. Review, merge and install the `image-holen` admin job (chain t_ba874608), so `/var/lib/admin-jobs-images/` exists.
2. Approve 5 image fetches, each submitted by an agent with `~/.hermes/profiles/birk/scripts/admin-job-submit.py image-holen <ref> --key <key>` (FRAGE-3: exact syntax after install):
   - `docker.io/library/node:24.22.2-bookworm`
   - `docker.io/library/node:24.22.2-bookworm-slim`
   - `docker.io/tianon/gosu:1.19`
   - `docker.io/library/postgres:15.4`
   - `docker.io/library/redis:7.2.4`

   After each tap, `podman load -i /var/lib/admin-jobs-images/<file>`.
3. Decide FRAGE-2: allow egress to `binaries.prisma.sh` for uid birk, or approve the engine-injection route.
4. Optionally answer FRAGE-1 (`base|query_data` vs `base|read`); the default is `base|query_data`.
