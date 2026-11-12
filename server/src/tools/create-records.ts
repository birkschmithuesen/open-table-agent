import { z } from "zod";
import { WRITE, type ToolDef } from "./types.js";
import { loadFields } from "../teable/fields.js";
import { assertRectangular, notWrittenWarnings, resolveHeader } from "./rows.js";

export const tool: ToolDef = {
  name: "create-records", title: "Create records", annotations: WRITE(false),
  description: "Create records from a header (field names or IDs) and rows of cells. Empty cells (null, undefined, \"\") are omitted.",
  inputSchema: {
    tableId: z.string().min(1),
    header: z.array(z.string()).min(1),
    records: z.array(z.array(z.unknown())).min(1),
    typecast: z.boolean().default(true),
  },
  async handler({ tableId, header, records, typecast }, { client }) {
    assertRectangular(header, records);
    const fields = await loadFields(client, tableId);
    const ids = resolveHeader(fields, header);
    const sent: Record<string, unknown>[] = records.map((row: unknown[]) => {
      const f: Record<string, unknown> = {};
      ids.forEach((id, i) => {
        const v = row[i];
        if (v === null || v === undefined || v === "") return;
        f[id] = v;
      });
      return f;
    });
    const res = await client.request<{ records?: { id: string; fields: Record<string, unknown> }[] }>(
      "POST", `/table/${encodeURIComponent(tableId)}/record`,
      { body: { fieldKeyType: "id", typecast, records: sent.map((fields) => ({ fields })) } });
    const created = res.data?.records ?? [];
    const warnings = notWrittenWarnings(sent, created.map((r) => ({ fields: r.fields ?? {} })), fields);
    return { success: true, recordsCreated: created.length, recordIds: created.map((r) => r.id),
      ...(warnings.length ? { warnings } : {}) };
  },
};
