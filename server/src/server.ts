// Portions Copyright (c) 2024 Teable MCP Server Contributors (MIT), ported from teable-mcp
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { Config } from "./config.js";
import type { TeableClient } from "./teable/client.js";
import type { ToolDef } from "./tools/types.js";
import { TOOLS } from "./tools/index.js";
import { assertInputSize, errorResult, toToolResult } from "./result.js";

export const SERVER_INSTRUCTIONS = [
  "Data model: space > base > table; tables have fields, views and records.",
  "Start with list-bases, then get-tables-meta. Call get-fields before writing records.",
  "Field names are accepted wherever a field is referenced (projection, filters, headers); they are mapped to field IDs.",
  "update-records: either filter+fields (same values for all matches) or header+records (per-record values); never both.",
  "delete-records: either recordIds or filter; never both.",
  "sql-query is read-only PostgreSQL over one base; prefer get-records when you need record IDs.",
  "For anything else: search-api, then call-api-read (GET) or call-api-write. Every call runs with your own token's permissions; report 403s instead of working around them.",
].join("\n");

export function createMcpServer(client: TeableClient, config: Config, tools: ToolDef[] = TOOLS): McpServer {
  const server = new McpServer({ name: "open-table-agent", version: "0.1.0" }, { instructions: SERVER_INSTRUCTIONS });
  for (const tool of tools) {
    server.registerTool(tool.name,
      { title: tool.title, description: tool.description, inputSchema: tool.inputSchema, annotations: { title: tool.title, ...tool.annotations } },
      async (args: unknown) => {
        try { assertInputSize(args); return toToolResult(await tool.handler(args, { client, config })); }
        catch (err) { return errorResult(err); }
      });
  }
  return server;
}
