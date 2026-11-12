import { z } from "zod";
import { READ, type ToolDef } from "./types.js";

export const tool: ToolDef = {
  name: "sql-query", title: "SQL query", annotations: READ,
  description: "Run a read-only PostgreSQL query against a base. Address tables as \"<baseId>\".\"<dbTableName>\" "
    + "(dbTableName comes from get-tables-meta); columns are the quoted dbFieldName values from get-fields. "
    + "System columns: __id, __auto_number, __created_time, __last_modified_time, __created_by, __last_modified_by. "
    + "Always add a LIMIT. Timestamps are UTC. Use get-records when you need record IDs for writes.",
  inputSchema: { baseId: z.string().min(1), sql: z.string().min(1) },
  async handler({ baseId, sql }, { client }) {
    const res = await client.request<{ rows: Record<string, unknown>[] }>(
      "POST", `/base/${encodeURIComponent(baseId)}/sql-query`, { body: { sql } });
    const rows = res.data.rows ?? [];
    const columns = Object.keys(rows[0] ?? {});
    return { success: true, rowCount: rows.length, columnCount: columns.length, columns, rows };
  },
};
