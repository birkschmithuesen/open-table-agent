import { z } from "zod";
import { WRITE, type ToolDef } from "./types.js";
import { loadFields, mapFilterFieldIds } from "../teable/fields.js";
import { ToolInputError } from "../result.js";

export const tool: ToolDef = {
  name: "delete-records", title: "Delete records", annotations: WRITE(true),
  description: "Delete records by recordIds (max 1000) or by filter. Provide exactly one of the two.",
  inputSchema: {
    tableId: z.string().min(1),
    recordIds: z.array(z.string()).min(1).max(1000).optional(),
    filter: z.record(z.string(), z.unknown()).optional(),
  },
  async handler({ tableId, recordIds, filter }, { client }) {
    if ((recordIds !== undefined) === (filter !== undefined)) {
      throw new ToolInputError("Provide exactly one of recordIds or filter");
    }
    if (recordIds) {
      await client.request("DELETE", `/table/${encodeURIComponent(tableId)}/record`, { query: { recordIds } });
      return { success: true, deletedCount: recordIds.length };
    }
    const fields = await loadFields(client, tableId);
    const res = await client.request<{ deletedCount?: number; data?: { deletedCount?: number } }>(
      "DELETE", "/v2/tables/deleteRecords", { body: { tableId, filter: mapFilterFieldIds(filter, fields) } });
    // Real v2 responses are wrapped as { ok, data: {...} }; tolerate both.
    return { success: true, deletedCount: res.data?.data?.deletedCount ?? res.data?.deletedCount ?? 0 };
  },
};
