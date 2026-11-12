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
