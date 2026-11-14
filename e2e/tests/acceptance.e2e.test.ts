import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "node:fs";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { spawn } from "node:child_process";

const env = Object.fromEntries(readFileSync(new URL("../.env.e2e", import.meta.url), "utf8").trim().split("\n").map((l) => l.split(/=(.*)/s).slice(0, 2)));
const SERVER = new URL("../../server/dist/index.js", import.meta.url).pathname;
const TWELVE = ["list-bases","get-tables-meta","get-fields","get-records","sql-query","get-doc","search-api",
  "call-api-read","create-records","update-records","delete-records","call-api-write"];
const parse = (r: any) => JSON.parse(r.content[0].text);

async function stdioClient(token: string) {
  const c = new Client({ name: "e2e", version: "0" });
  await c.connect(new StdioClientTransport({ command: process.execPath, args: [SERVER],
    env: { PATH: process.env.PATH!, TEABLE_URL: env.TEABLE_URL, TEABLE_TOKEN: token } }));
  return c;
}

describe("real CE", () => {
  let a: Client;
  beforeAll(async () => { a = await stdioClient(env.TOKEN_A); });

  it("lists 12 tools (stdio and HTTP)", async () => {
    expect((await a.listTools()).tools.map((t) => t.name)).toEqual(TWELVE);
    const proc = spawn(process.execPath, [SERVER, "--http"], { env: { PATH: process.env.PATH!, TEABLE_URL: env.TEABLE_URL, OTA_HTTP_PORT: "3199" } });
    try {
      await new Promise((r) => proc.stderr.on("data", (d) => String(d).includes("listening") && r(null)));
      const h = new Client({ name: "e2e-http", version: "0" });
      await h.connect(new StreamableHTTPClientTransport(new URL("http://127.0.0.1:3199/mcp"),
        { requestInit: { headers: { Authorization: `Bearer ${env.TOKEN_A}` } } }));
      expect((await h.listTools()).tools).toHaveLength(12);
    } finally { proc.kill(); }
  });

  it("create then read back by field name filter", async () => {
    const created = parse(await a.callTool({ name: "create-records", arguments: { tableId: env.TABLE_ID, header: ["Name", "Count"], records: [["e2e-a", 7], ["e2e-b", 1]] } }));
    expect(created).toMatchObject({ success: true, recordsCreated: 2 });
    const got = parse(await a.callTool({ name: "get-records", arguments: { tableId: env.TABLE_ID, projection: ["Name", "Count"],
      filter: { conjunction: "and", filterSet: [{ fieldId: "Count", operator: "isGreater", value: 5 }] } } }));
    expect(got.rows.map((r: unknown[]) => r[1])).toEqual(["e2e-a"]);
  });

  it("sql-query returns rows", async () => {
    const t = parse(await a.callTool({ name: "get-tables-meta", arguments: { baseId: env.BASE_ID, tableId: env.TABLE_ID } })).tables[0];
    const from = t.dbTableName.includes(".") ? t.dbTableName.split(".").map((s: string) => `"${s}"`).join(".") : `"${env.BASE_ID}"."${t.dbTableName}"`;
    const r = await a.callTool({ name: "sql-query", arguments: { baseId: env.BASE_ID, sql: `SELECT count(*) AS n FROM ${from}` } });
    expect(r.isError, JSON.stringify(r)).toBeFalsy();
    expect(Number(parse(r).rows[0].n)).toBeGreaterThanOrEqual(2);
  });

  it("sql-query refused without base access", async () => {
    const b = await stdioClient(env.TOKEN_B);
    const r = await b.callTool({ name: "sql-query", arguments: { baseId: env.BASE_ID, sql: "SELECT 1" } });
    expect(r.isError).toBe(true);
    expect(parse(r).status).toBe(403);
  });
});
