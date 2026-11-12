#!/usr/bin/env node
// Portions Copyright (c) 2024 Teable MCP Server Contributors (MIT), ported from teable-mcp
import type { AddressInfo } from "node:net";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { loadConfig, ConfigError } from "./config.js";
import { TeableClient } from "./teable/client.js";
import { createMcpServer } from "./server.js";
import { startHttpServer } from "./http.js";

export async function main(argv = process.argv.slice(2), env = process.env): Promise<void> {
  const config = loadConfig(argv, env);
  if (config.transport === "http") {
    const srv = await startHttpServer({ host: config.http.host, port: config.http.port, teableUrl: config.teableUrl,
      allowedOrigins: config.http.allowedOrigins, config });
    const { port } = srv.address() as AddressInfo;
    process.stderr.write(`open-table-agent: listening on http://${config.http.host}:${port}/mcp\n`);
    return;
  }
  const server = createMcpServer(new TeableClient(config.token!, config.teableUrl), config);
  await server.connect(new StdioServerTransport());
}
main().catch((err) => {
  process.stderr.write(`open-table-agent: ${err instanceof ConfigError ? err.message : String(err?.stack ?? err)}\n`);
  process.exit(err instanceof ConfigError ? 2 : 1);
});
