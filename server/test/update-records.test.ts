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
it("mode A also reads the wrapped { ok, data } v2 response", async () => {
  stub = await startStubTeable({ "GET /api/table/tbl1/field": () => ({ body: fields }),
    "POST /api/v2/tables/updateRecords": () => ({ body: { ok: true, data: { updatedCount: 7 } } }) });
  const c = await connectClient(stub.url);
  const r = parseText(await c.callTool({ name: "update-records", arguments: { tableId: "tbl1",
    filter: { fieldId: "Name", operator: "is", value: "A" }, fields: { Count: 1 } } }) as any);
  expect(r).toEqual({ success: true, updatedCount: 7 });
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
