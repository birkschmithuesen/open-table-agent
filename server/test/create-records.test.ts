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
const boxFields = [...fields, { id: "fldBox00001", name: "Done", type: "checkbox" }];
it("no 'not written' warning for a sent checkbox false that Teable stores as null", async () => {
  stub = await startStubTeable({ "GET /api/table/tbl1/field": () => ({ body: boxFields }),
    "POST /api/table/tbl1/record": () => ({ body: { records: [{ id: "rec0", fields: { fldName0001: "A" } }] } }) });
  const c = await connectClient(stub.url);
  const r = parseText(await c.callTool({ name: "create-records", arguments: { tableId: "tbl1", header: ["Name", "Done"], records: [["A", false]] } }) as any);
  expect(r).toMatchObject({ success: true, recordsCreated: 1 });
  expect((r as any).warnings).toBeUndefined();
});
it("still warns when a non-false value is dropped", async () => {
  stub = await startStubTeable({ "GET /api/table/tbl1/field": () => ({ body: boxFields }),
    "POST /api/table/tbl1/record": () => ({ body: { records: [{ id: "rec0", fields: {} }] } }) });
  const c = await connectClient(stub.url);
  const r = parseText(await c.callTool({ name: "create-records", arguments: { tableId: "tbl1", header: ["Name", "Done"], records: [["A", false]] } }) as any);
  expect((r as any).warnings).toEqual(["Row 0: not written: Name"]);
});
it("rejects ragged rows without a request", async () => {
  stub = await startStubTeable({ "GET /api/table/tbl1/field": () => ({ body: fields }) });
  const c = await connectClient(stub.url);
  const r = await c.callTool({ name: "create-records", arguments: { tableId: "tbl1", header: ["Name", "Count"], records: [["A", 1], ["B"]] } });
  expect(r.isError).toBe(true);
  expect(stub.calls.some((x) => x.method === "POST")).toBe(false);
});
