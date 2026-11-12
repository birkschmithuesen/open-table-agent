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
