import http from "node:http";
import type { AddressInfo } from "node:net";

export interface StubCall { method: string; path: string; query: URLSearchParams; body: unknown; authorization?: string; }
export type StubHandler = (call: StubCall) => { status?: number; body: unknown };

/** Local fake Teable. Routes are keyed "METHOD /api/path" (no query). Unknown routes → 404. */
export async function startStubTeable(routes: Record<string, StubHandler>) {
  const calls: StubCall[] = [];
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url ?? "/", "http://stub");
    const chunks: Buffer[] = [];
    for await (const c of req) chunks.push(c as Buffer);
    const raw = Buffer.concat(chunks).toString("utf8");
    const call: StubCall = {
      method: req.method ?? "GET", path: url.pathname, query: url.searchParams,
      body: raw ? JSON.parse(raw) : undefined, authorization: req.headers.authorization,
    };
    calls.push(call);
    const handler = routes[`${call.method} ${call.path}`];
    const out = handler ? handler(call) : { status: 404, body: { message: `no stub for ${call.method} ${call.path}` } };
    res.writeHead(out.status ?? 200, { "content-type": "application/json" });
    res.end(JSON.stringify(out.body));
  });
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  const { port } = server.address() as AddressInfo;
  return { url: `http://127.0.0.1:${port}`, calls, close: () => new Promise<void>((r) => server.close(() => r())) };
}
