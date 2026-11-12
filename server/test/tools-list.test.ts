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
