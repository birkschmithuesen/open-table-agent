import { z } from "zod";
import { READ, type ToolDef } from "./types.js";
import { loadFields, resolveFieldKey, mapFilterFieldIds } from "../teable/fields.js";

const MAX_DEFAULT_FIELDS = 50;

function clean(v: unknown): unknown {
  if (Array.isArray(v)) return v.map(clean);
  if (!v || typeof v !== "object") return v;
  const out: Record<string, unknown> = {};
  for (const [k, x] of Object.entries(v)) {
    if (k === "smThumbnailUrl" || k === "lgThumbnailUrl") continue;
    out[k] = clean(x);
  }
  return out;
}

interface RawRecord { id: string; fields?: Record<string, unknown> }

export const tool: ToolDef = {
  name: "get-records", title: "Get records", annotations: READ,
  description: "Read records of a table as a compact table (header + rows). Field names or IDs are accepted in projection, filter, orderBy and search.",
  inputSchema: {
    tableId: z.string().min(1),
    viewId: z.string().optional(),
    recordId: z.string().optional(),
    take: z.coerce.number().int().min(1).max(1000).default(100),
    skip: z.coerce.number().int().min(0).optional(),
    projection: z.union([z.literal("all"), z.array(z.string()).max(50)]).optional(),
    filter: z.record(z.string(), z.unknown()).optional(),
    search: z.object({ value: z.string(), field: z.string().optional() }).optional(),
    orderBy: z.array(z.object({ field: z.string(), order: z.enum(["asc", "desc"]) })).optional(),
  },
  async handler({ tableId, viewId, recordId, take, skip, projection, filter, search, orderBy }, { client }) {
    const fields = await loadFields(client, tableId);
    let hint: string | undefined;
    let ids: string[];
    if (Array.isArray(projection)) {
      ids = projection.map((k: string) => resolveFieldKey(fields, k));
    } else {
      ids = fields.slice(0, MAX_DEFAULT_FIELDS).map((f) => f.id);
      if (fields.length > MAX_DEFAULT_FIELDS) {
        hint = `showing the first ${MAX_DEFAULT_FIELDS} of ${fields.length} fields; pass projection`;
      }
    }
    let searchFieldId: string | undefined;
    if (search?.field) {
      searchFieldId = resolveFieldKey(fields, search.field);
      if (!ids.includes(searchFieldId)) ids.push(searchFieldId);
    }
    const t = encodeURIComponent(tableId);
    let records: RawRecord[];
    if (recordId) {
      const res = await client.request<RawRecord>("GET", `/table/${t}/record/${encodeURIComponent(recordId)}`,
        { query: { fieldKeyType: "id", projection: ids } });
      records = [res.data];
    } else {
      const query: Record<string, string | number | string[] | undefined> = {
        fieldKeyType: "id", take, skip, viewId, projection: ids,
        filter: filter ? JSON.stringify(mapFilterFieldIds(filter, fields)) : undefined,
        orderBy: orderBy
          ? JSON.stringify(orderBy.map((o: { field: string; order: string }) =>
              ({ fieldId: resolveFieldKey(fields, o.field), order: o.order })))
          : undefined,
        // CE parses search as a tuple of repeated query keys, not a JSON string.
        search: search ? [search.value, searchFieldId ?? "", "true"] : undefined,
      };
      const res = await client.request<{ records: RawRecord[] }>("GET", `/table/${t}/record`, { query });
      records = res.data.records ?? [];
    }
    const byId = new Map(fields.map((f) => [f.id, f]));
    const names = ids.map((id) => byId.get(id)!.name);
    const rows = records.map((r) => [r.id, ...ids.map((id) => clean(r.fields?.[id] ?? null))]);
    const meta: Record<string, { id: string; type: string }> = {};
    for (const id of ids) meta[byId.get(id)!.name] = { id, type: byId.get(id)!.type };
    return { success: true, total: rows.length, ...(hint ? { hint } : {}), format: "tabular",
      header: ["id", ...names], rows, meta: { fields: meta } };
  },
};
