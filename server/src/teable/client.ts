export class TeableApiError extends Error {
  constructor(public status: number, message: string, public body: unknown) { super(message); }
}
type QueryValue = string | number | boolean | string[] | undefined;

export class TeableClient {
  private readonly apiBase: string;
  constructor(private readonly token: string, teableUrl: string,
              private readonly opts: { timeoutMs?: number; fetchImpl?: typeof fetch } = {}) {
    this.apiBase = `${teableUrl.replace(/\/+$/, "")}/api`;
  }
  /** GET an absolute URL (outside /api, e.g. the OpenAPI document) with the bearer token. */
  async fetchAbsolute(url: string): Promise<unknown> {
    const res = await (this.opts.fetchImpl ?? fetch)(url, {
      headers: { Authorization: `Bearer ${this.token}`, Accept: "application/json" },
      signal: AbortSignal.timeout(this.opts.timeoutMs ?? 120_000),
    });
    const text = await res.text();
    if (!res.ok) throw new TeableApiError(res.status, `Failed to fetch ${url}: HTTP ${res.status}`, text);
    try { return JSON.parse(text); }
    catch { throw new Error(`Failed to fetch ${url}: response is not JSON`); }
  }
  async request<T = unknown>(method: string, path: string,
      o: { query?: Record<string, QueryValue>; body?: unknown } = {}): Promise<{ status: number; data: T }> {
    if (!path.startsWith("/")) throw new Error(`path must start with /: ${path}`);
    const url = new URL(this.apiBase + path);
    for (const [k, v] of Object.entries(o.query ?? {})) {
      if (v === undefined) continue;
      for (const item of Array.isArray(v) ? v : [v]) url.searchParams.append(k, String(item));
    }
    const res = await (this.opts.fetchImpl ?? fetch)(url, {
      method,
      headers: { Authorization: `Bearer ${this.token}`, Accept: "application/json",
                 ...(o.body !== undefined ? { "Content-Type": "application/json" } : {}) },
      body: o.body !== undefined ? JSON.stringify(o.body) : undefined,
      signal: AbortSignal.timeout(this.opts.timeoutMs ?? 120_000),
    });
    const text = await res.text();
    let data: unknown = text;
    try { data = text ? JSON.parse(text) : null; } catch { /* keep text */ }
    if (!res.ok) {
      const msg = typeof data === "object" && data && "message" in data ? String((data as { message: unknown }).message)
        : typeof data === "string" ? data : JSON.stringify(data);
      throw new TeableApiError(res.status, msg || `HTTP ${res.status}`, data);
    }
    return { status: res.status, data: data as T };
  }
}
