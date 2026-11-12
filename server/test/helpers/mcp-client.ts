import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { createMcpServer } from "../../src/server.js";
import { TeableClient } from "../../src/teable/client.js";
import { loadConfig } from "../../src/config.js";

/** Real MCP client ↔ server over an in-memory pair, server talking to `teableUrl`. */
export async function connectClient(teableUrl: string, token = "test-token") {
  const config = loadConfig([], { TEABLE_URL: teableUrl, TEABLE_TOKEN: token });
  const server = createMcpServer(new TeableClient(token, teableUrl), config);
  const [clientT, serverT] = InMemoryTransport.createLinkedPair();
  await server.connect(serverT);
  const client = new Client({ name: "test", version: "0" });
  await client.connect(clientT);
  return client;
}

export function parseText(result: { content: Array<{ type: string; text?: string }> }) {
  return JSON.parse(result.content[0].text as string);
}
