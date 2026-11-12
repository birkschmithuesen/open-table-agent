import { z } from "zod";
import { READ, type ToolDef } from "./types.js";
import type { TeableTable } from "../teable/types.js";

export const tool: ToolDef = {
  name: "get-tables-meta", title: "Get tables meta", annotations: READ,
  description: "List tables of a base with id, name, dbTableName (for sql-query), description, icon.",
  inputSchema: { baseId: z.string().min(1), tableId: z.string().optional(), tableName: z.string().optional() },
  async handler({ baseId, tableId, tableName }, { client }) {
    const all = (await client.request<TeableTable[]>("GET", `/base/${encodeURIComponent(baseId)}/table`)).data;
    const filtered = tableId ? all.filter((t) => t.id === tableId)
      : tableName ? all.filter((t) => t.name === tableName) : all;
    const key = tableId ?? tableName;
    if (key && filtered.length === 0) return { success: false, error: `Table not found: ${key}` };
    const tables = filtered.map((t) => ({ id: t.id, name: t.name, dbTableName: t.dbTableName, description: t.description, icon: t.icon }));
    return { success: true, count: tables.length, tables };
  },
};
