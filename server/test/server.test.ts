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
