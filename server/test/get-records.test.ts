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
