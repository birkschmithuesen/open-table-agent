import { z } from "zod";
import { READ, type ToolDef } from "./types.js";
import { loadFields } from "../teable/fields.js";

export const tool: ToolDef = {
  name: "get-fields", title: "Get fields", annotations: READ,
  description: "Field definitions of a table: id, name, type, dbFieldName (for sql-query), options.",
  inputSchema: { tableId: z.string().min(1), fieldId: z.string().optional(), fieldName: z.string().optional() },
  async handler({ tableId, fieldId, fieldName }, { client }) {
    const all = await loadFields(client, tableId);
    const fields = fieldId ? all.filter((f) => f.id === fieldId)
      : fieldName ? all.filter((f) => f.name === fieldName) : all;
    const key = fieldId ?? fieldName;
    if (key && fields.length === 0) return { success: false, error: `Field not found: ${key}` };
    return { success: true, count: fields.length, fields };
  },
};
