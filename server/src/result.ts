import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { TeableApiError } from "./teable/client.js";

export const MAX_TEXT = 60000;
export class InputTooLargeError extends Error {}
export class ToolInputError extends Error {
  constructor(message: string, public extra: Record<string, unknown> = {}) { super(message); }
}

export function toToolResult(output: object): CallToolResult {
  let text = JSON.stringify(output);
  if (text.length > MAX_TEXT) {
    const dropped = text.length - MAX_TEXT;
    text = text.slice(0, MAX_TEXT) +
      `\n[truncated: ${dropped} characters dropped. Narrow the request: projection, take/skip, or a tighter filter/query.]`;
  }
  const isError = (output as { success?: unknown }).success === false;
  return { content: [{ type: "text", text }], ...(isError ? { isError: true } : {}) };
}

export function errorResult(err: unknown): CallToolResult {
  if (err instanceof TeableApiError) return toToolResult({ success: false, status: err.status, error: err.message });
  if (err instanceof ToolInputError) return toToolResult({ success: false, error: err.message, ...err.extra });
  return toToolResult({ success: false, error: err instanceof Error ? err.message : String(err) });
}

export function assertInputSize(args: unknown, max = 100000): void {
  let count = 0;
  const stack: unknown[] = [args];
  while (stack.length) {
    const v = stack.pop();
    if (Array.isArray(v)) { count += v.length; stack.push(...v); }
    else if (v && typeof v === "object") { const vals = Object.values(v); count += vals.length; stack.push(...vals); }
    if (count > max) throw new InputTooLargeError(`input too large: more than ${max} array elements + object keys`);
  }
}
