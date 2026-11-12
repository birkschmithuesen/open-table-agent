import type { TeableField } from "../teable/types.js";
import { resolveFieldKey } from "../teable/fields.js";
import { ToolInputError } from "../result.js";

/** Map header names (or ids) to field ids. */
export function resolveHeader(fields: TeableField[], header: string[]): string[] {
  return header.map((h) => resolveFieldKey(fields, h));
}

/** Every row must have exactly header.length cells. */
export function assertRectangular(header: string[], records: unknown[][]): void {
  const bad: number[] = [];
  records.forEach((r, i) => { if (r.length !== header.length) bad.push(i); });
  if (bad.length === 0) return;
  throw new ToolInputError(`Row length does not match header (rows: ${bad.slice(0, 3).join(", ")})`,
    { headerLength: header.length });
}

/** Compare what was sent with what the server returned; name fields that were silently dropped. */
export function notWrittenWarnings(sent: Record<string, unknown>[],
    returned: { fields: Record<string, unknown> }[], fields: TeableField[]): string[] {
  const names = new Map(fields.map((f) => [f.id, f.name]));
  const warnings: string[] = [];
  sent.forEach((s, i) => {
    const got = returned[i]?.fields ?? {};
    const missing = Object.entries(s)
      .filter(([id, v]) => v !== null && v !== undefined && (got[id] === undefined || got[id] === null))
      .map(([id]) => names.get(id) ?? id);
    if (missing.length) warnings.push(`Row ${i}: not written: ${missing.join(", ")}`);
  });
  return warnings;
}
