import { z } from "zod";
import { WRITE, type ToolDef } from "./types.js";
import { loadFields, mapFilterFieldIds, resolveFieldKey } from "../teable/fields.js";
import { assertRectangular, notWrittenWarnings, resolveHeader } from "./rows.js";
import { ToolInputError } from "../result.js";

type Returned = { id?: string; fields?: Record<string, unknown> };

export const tool: ToolDef = {
  name: "update-records", title: "Update records", annotations: WRITE(true),
  description: "Update records. Mode A: filter + fields (same values on all matching records). Mode B: header (must contain recordId) + records rows; in a row \"\" leaves a cell unchanged and null clears it.",
  inputSchema: {
    tableId: z.string().min(1),
    filter: z.record(z.string(), z.unknown()).optional(),
    fields: z.record(z.string(), z.unknown()).optional(),
    header: z.array(z.string()).optional(),
    records: z.array(z.array(z.unknown())).optional(),
    typecast: z.boolean().default(true),
  },
  async handler({ tableId, filter, fields: setFields, header, records, typecast }, { client }) {
    const modeA = filter !== undefined && setFields !== undefined;
    const modeB = header !== undefined && records !== undefined;
    const anyA = filter !== undefined || setFields !== undefined;
    const anyB = header !== undefined || records !== undefined;
    if (modeA === modeB || (modeA && anyB) || (modeB && anyA)) {
      throw new ToolInputError("Use exactly one mode: filter+fields OR header+records");
    }
    const t = encodeURIComponent(tableId);
    if (modeA) {
      const fields = await loadFields(client, tableId);
      const mapped: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(setFields as Record<string, unknown>)) mapped[resolveFieldKey(fields, k)] = v;
      const res = await client.request<{ updatedCount?: number; data?: { updatedCount?: number } }>(
        "POST", "/v2/tables/updateRecords",
        { body: { tableId, filter: mapFilterFieldIds(filter, fields), fields: mapped, typecast, fieldKeyType: "id" } });
      // Real v2 responses are wrapped as { ok, data: {...} }; tolerate both.
      const count = res.data?.data?.updatedCount ?? res.data?.updatedCount ?? 0;
      return { success: true, updatedCount: count };
    }
    if (!header.includes("recordId")) {
      throw new ToolInputError("header must contain recordId");
    }
    assertRectangular(header, records);
    const fields = await loadFields(client, tableId);
    const idCol = header.indexOf("recordId");
    const fieldIds = header.map((h: string, i: number) => (i === idCol ? "" : resolveHeader(fields, [h])[0]));
    const sent: Record<string, unknown>[] = [];
    const body = records.map((row: unknown[]) => {
      const f: Record<string, unknown> = {};
      fieldIds.forEach((id: string, i: number) => {
        if (i === idCol || row[i] === "" || row[i] === undefined) return;
        f[id] = row[i];
      });
      sent.push(f);
      return { id: String(row[idCol]), fields: f };
    });
    const res = await client.request<Returned[] | { records?: Returned[] }>("PATCH", `/table/${t}/record`,
      { body: { fieldKeyType: "id", typecast, records: body } });
    const returned = (Array.isArray(res.data) ? res.data : res.data?.records ?? []) as Returned[];
    const warnings = notWrittenWarnings(sent, returned.map((r) => ({ fields: r.fields ?? {} })), fields);
    return { success: true, updated: body.length, ...(warnings.length ? { warnings } : {}) };
  },
};
