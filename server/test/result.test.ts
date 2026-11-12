import { it, expect } from "vitest";
import { toToolResult, errorResult, assertInputSize, MAX_TEXT } from "../src/result.js";
import { TeableApiError } from "../src/teable/client.js";

it("truncates at 60000 chars", () => {
  const r = toToolResult({ success: true, blob: "x".repeat(70000) });
  const text = r.content[0].text as string;
  expect(MAX_TEXT).toBe(60000);
  expect(text.length).toBeLessThan(60400);
  expect(text).toMatch(/truncated: \d+ characters dropped/);
});
it("isError iff success === false", () => {
  expect(toToolResult({ success: true }).isError).toBeFalsy();
  expect(toToolResult({ success: false, error: "x" }).isError).toBe(true);
});
it("errorResult carries Teable status", () => {
  const r = errorResult(new TeableApiError(403, "nope", { message: "nope" }));
  expect(r.isError).toBe(true);
  expect(JSON.parse(r.content[0].text as string)).toEqual({ success: false, status: 403, error: "nope" });
});
it("rejects inputs above the element cap", () => {
  expect(() => assertInputSize({ a: new Array(11).fill(0) }, 10)).toThrow(/too large/);
  expect(() => assertInputSize({ a: [1, 2] }, 10)).not.toThrow();
});
