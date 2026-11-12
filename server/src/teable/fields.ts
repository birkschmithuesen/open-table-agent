import type { TeableClient } from "./client.js";
import type { TeableField } from "./types.js";
import { ToolInputError } from "../result.js";

export async function loadFields(client: TeableClient, tableId: string): Promise<TeableField[]> {
  return (await client.request<TeableField[]>("GET", `/table/${encodeURIComponent(tableId)}/field`)).data;
}

export function resolveFieldKey(fields: TeableField[], key: string): string {
  const byId = fields.find((f) => f.id === key);
  if (byId) return byId.id;
  const lower = key.toLowerCase();
  const byName = fields.find((f) => f.name.toLowerCase() === lower);
  if (byName) return byName.id;
  const suggestions = fields.filter((f) => f.name.toLowerCase().includes(lower) || lower.includes(f.name.toLowerCase()))
    .slice(0, 5).map((f) => f.name);
  throw new ToolInputError(`Unknown field: ${key}`, { suggestions, availableFields: fields.map((f) => f.name) });
}

export function mapFilterFieldIds<T>(filter: T, fields: TeableField[]): T {
  const walk = (node: unknown): unknown => {
    if (Array.isArray(node)) return node.map(walk);
    if (!node || typeof node !== "object") return node;
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(node)) {
      out[k] = k === "fieldId" && typeof v === "string" ? resolveFieldKey(fields, v)
        : k === "filterSet" || k === "items" || k === "not" || k === "value" ? walk(v) : v;
    }
    return out;
  };
  return walk(filter) as T;
}
