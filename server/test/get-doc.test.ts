import { it, expect, afterEach } from "vitest";
import { startStubTeable } from "./helpers/stub-teable.js";
import { connectClient, parseText } from "./helpers/mcp-client.js";
import { DOC_TOPICS } from "../src/docs/index.js";

const EXPECTED = ["automation.api","automation.send-email","automation.trigger","field.basic","field.colors","field.formatting",
  "field.formula","field.link","field.lookup","field.rollup","field.select","field.show-as","field.simple","integration.slack",
  "record.value-format","reference.url","scrape.datasets","scrape.guide","view.column","view.filter","view.group","view.sort","view.statistic"];
let stub: Awaited<ReturnType<typeof startStubTeable>>;
afterEach(() => stub?.close());

it("every topic resolves", async () => {
  expect([...DOC_TOPICS]).toEqual(EXPECTED);
  stub = await startStubTeable({});
  const c = await connectClient(stub.url);
  for (const topic of EXPECTED) {
    const r = parseText(await c.callTool({ name: "get-doc", arguments: { topic } }) as any);
    expect(r.success, topic).toBe(true);
    expect(r.content).toMatch(/^#+ /); // automation.api.md upstream starts with "## "
  }
});
it("rejects unknown topics", async () => {
  stub = await startStubTeable({});
  const c = await connectClient(stub.url);
  const r = await c.callTool({ name: "get-doc", arguments: { topic: "app.ai" } });
  expect(r.isError).toBe(true);
});
