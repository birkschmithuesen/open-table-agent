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
