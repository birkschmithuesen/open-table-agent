import { describe, it, expect, afterEach } from "vitest";
import { startStubTeable } from "./helpers/stub-teable.js";
import { TeableClient, TeableApiError } from "../src/teable/client.js";

let stub: Awaited<ReturnType<typeof startStubTeable>>;
afterEach(() => stub?.close());

describe("TeableClient", () => {
  it("sends bearer, JSON body and encoded query to /api + path", async () => {
    stub = await startStubTeable({ "POST /api/table/tbl1/record": () => ({ body: { ok: 1 } }) });
    const c = new TeableClient("tok-1", stub.url);
    const r = await c.request("POST", "/table/tbl1/record", { query: { fieldKeyType: "id", recordIds: ["a", "b"] }, body: { x: 1 } });
    expect(r).toEqual({ status: 200, data: { ok: 1 } });
    expect(stub.calls[0].authorization).toBe("Bearer tok-1");
    expect(stub.calls[0].query.getAll("recordIds")).toEqual(["a", "b"]);
    expect(stub.calls[0].body).toEqual({ x: 1 });
  });
  it("throws TeableApiError with status and Teable message", async () => {
    stub = await startStubTeable({ "GET /api/base/b1/table": () => ({ status: 403, body: { message: "not allowed to base" } }) });
    const err = await new TeableClient("t", stub.url).request("GET", "/base/b1/table").catch((e) => e);
    expect(err).toBeInstanceOf(TeableApiError);
    expect(err).toMatchObject({ status: 403, message: "not allowed to base" });
  });
});
