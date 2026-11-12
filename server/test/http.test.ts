// Portions Copyright (c) 2024 Teable MCP Server Contributors (MIT), ported from teable-mcp
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import type { Server } from "node:http";
import type { AddressInfo } from "node:net";
import { startStubTeable } from "./helpers/stub-teable.js";
import { startHttpServer } from "../src/http.js";
import { loadConfig } from "../src/config.js";

let stub: Awaited<ReturnType<typeof startStubTeable>>;
let srv: Server; let base: string;
const H = { "content-type": "application/json", accept: "application/json, text/event-stream" };
const rpc = (method: string, params: object = {}) => JSON.stringify({ jsonrpc: "2.0", id: 1, method, params });

beforeAll(async () => {
  stub = await startStubTeable({ "GET /api/base/access/all": () => ({ body: [] }) });
  // stdio-mode config on purpose: loadConfig drops the token in http mode, so only this
  // config can prove the transport never falls back to config.token.
  const config = loadConfig([], { TEABLE_URL: stub.url, TEABLE_TOKEN: "ENV-TOKEN-MUST-NOT-LEAK", OTA_HTTP_PORT: "0" });
  srv = await startHttpServer({ host: "127.0.0.1", port: 0, teableUrl: stub.url, allowedOrigins: ["https://ok.example"], config });
  base = `http://127.0.0.1:${(srv.address() as AddressInfo).port}`;
});
afterAll(async () => { srv.close(); await stub.close(); });

describe("http transport", () => {
  it("health is open", async () => { expect((await fetch(`${base}/health`)).status).toBe(200); });
  it("rejects missing bearer with 401", async () => {
    expect((await fetch(`${base}/mcp`, { method: "POST", headers: H, body: rpc("tools/list") })).status).toBe(401);
  });
  it("GET is 405 with Allow: POST", async () => {
    const r = await fetch(`${base}/mcp`, { headers: { authorization: "Bearer x" } });
    expect(r.status).toBe(405); expect(r.headers.get("allow")).toBe("POST");
  });
  it("foreign Origin is 403", async () => {
    expect((await fetch(`${base}/mcp`, { method: "POST", headers: { ...H, authorization: "Bearer x", origin: "https://evil.example" }, body: rpc("tools/list") })).status).toBe(403);
  });
  it("forwards caller bearer to Teable", async () => {
    const r = await fetch(`${base}/mcp`, { method: "POST", headers: { ...H, authorization: "Bearer caller-secret" },
      body: rpc("tools/call", { name: "list-bases", arguments: {} }) });
    expect(r.status).toBe(200);
    expect(stub.calls.map((c) => c.authorization)).toEqual(["Bearer caller-secret"]);
  });
  it("tools/list over HTTP returns 12 tools", async () => {
    const r = await fetch(`${base}/mcp`, { method: "POST", headers: { ...H, authorization: "Bearer x" }, body: rpc("tools/list") });
    expect((await r.json()).result.tools).toHaveLength(12);
  });
});
