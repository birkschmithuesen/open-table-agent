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
