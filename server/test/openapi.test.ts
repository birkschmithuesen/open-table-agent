import { it, expect } from "vitest";
import spec from "./fixtures/openapi-mini.json" with { type: "json" };
import { ApiIndex, buildRequest } from "../src/openapi/index.js";

it("indexes endpoints with normalized paths and ranks by summary", () => {
  const idx = ApiIndex.fromSpec(spec);
  expect(idx.endpoints.map((e) => e.id).sort()).toEqual(["GET:/base/{baseId}/collaborators", "GET:/table/{tableId}/view", "POST:/table/{tableId}/view"]);
  expect(idx.search("create view")[0].id).toBe("POST:/table/{tableId}/view");
  expect(idx.search("view", { tags: ["base"] })).toEqual([]);
});
it("buildRequest splits path/query, encodes path params, rejects missing required", () => {
  const ep = ApiIndex.fromSpec(spec).lookup("GET", "/table/{tableId}/view")!;
  expect(buildRequest(ep, { tableId: "tbl/../x", extra: ["a", "b"], obj: { k: 1 } }))
    .toEqual({ path: "/table/tbl%2F..%2Fx/view", query: { extra: ["a", "b"], obj: '{"k":1}' } });
  expect(() => buildRequest(ep, {})).toThrow(/missing tableId/);
});
