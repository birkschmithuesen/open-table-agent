// Portions Copyright (c) 2024 Teable MCP Server Contributors (MIT), ported from teable-mcp
import * as http from "node:http";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { TeableClient } from "./teable/client.js";
import { createMcpServer } from "./server.js";
import type { Config } from "./config.js";

export interface HttpServerOptions {
  host: string;
  port: number;
  teableUrl: string;
  // Allow-list of Origin header values. Empty = only same-origin requests
  // (Origin host matching the Host header) pass; requests without Origin always pass.
  allowedOrigins: string[];
  config: Config;
}

function isOriginAllowed(origin: string | undefined, host: string | undefined, allowedOrigins: string[]): boolean {
  if (!origin) return true;
  if (allowedOrigins.length > 0) return allowedOrigins.includes(origin);
  if (!host) return false;
  try { return new URL(origin).host === host; } catch { return false; }
}

function extractBearerToken(header: string | undefined): string | undefined {
  if (!header) return undefined;
  const match = /^Bearer\s+(.+)$/i.exec(header);
  return match ? match[1].trim() : undefined;
}

function sendJson(res: http.ServerResponse, status: number, body: unknown): void {
  res.writeHead(status, { "Content-Type": "application/json" }).end(JSON.stringify(body));
}

export function createHttpRequestListener(options: HttpServerOptions): http.RequestListener {
  return async (req, res) => {
    const url = new URL(req.url || "/", "http://localhost");

    if (url.pathname === "/health") return sendJson(res, 200, { ok: true });
    if (url.pathname !== "/mcp") return sendJson(res, 404, { error: "Not found" });

    if (!isOriginAllowed(req.headers.origin, req.headers.host, options.allowedOrigins)) {
      return sendJson(res, 403, { error: "Origin not allowed" });
    }
    if (req.method !== "POST") {
      res.writeHead(405, { Allow: "POST" }).end();
      return;
    }

    const token = extractBearerToken(req.headers.authorization);

    if (!token) return sendJson(res, 401, { error: "Missing bearer token" });

    // Per-request client and server: the client carries the caller's bearer and
    // must never be shared; the transport is stateless (no session pinning).
    const client = new TeableClient(token, options.teableUrl);
    const server = createMcpServer(client, options.config);
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined, enableJsonResponse: true });

    res.on("close", () => { void transport.close(); void server.close(); });

    try {
      await server.connect(transport);
      await transport.handleRequest(req, res);
    } catch {
      if (!res.headersSent) sendJson(res, 500, { error: "Internal server error" });
    }
  };
}

export function startHttpServer(options: HttpServerOptions): Promise<http.Server> {
  return new Promise((resolve, reject) => {
    const server = http.createServer(createHttpRequestListener(options));
    server.once("error", reject);
    server.listen(options.port, options.host, () => resolve(server));
  });
}
