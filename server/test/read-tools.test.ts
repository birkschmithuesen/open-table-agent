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
