import type { TeableClient } from "../teable/client.js";
import { ToolInputError } from "../result.js";

export interface ApiParam { name: string; in: "path" | "query"; required: boolean; type?: string; description?: string }
export interface ApiEndpoint {
  id: string; method: string; url: string; summary: string; description: string; tags: string[]; parameters: ApiParam[];
  requestBody?: { required: boolean; properties: { name: string; type?: string; required: boolean; description?: string }[] };
}

type Obj = Record<string, any>;
const METHODS = ["get", "post", "put", "patch", "delete"];

function resolveRef(spec: Obj, node: any, depth = 0): any {
  let cur = node;
  for (let i = 0; i < 3 && cur && typeof cur === "object" && typeof cur.$ref === "string"; i++) {
    const parts = cur.$ref.replace(/^#\//, "").split("/");
    let next: any = spec;
    for (const p of parts) next = next?.[p.replace(/~1/g, "/").replace(/~0/g, "~")];
    cur = next;
  }
  return cur;
}

function normalizePath(p: string): string {
  return p.replace(/^\/api(?=\/|$)/, "") || "/";
}

function collectProps(spec: Obj, schema: any, depth = 0): { props: Obj; required: string[] } {
  const s = resolveRef(spec, schema);
  if (!s || typeof s !== "object") return { props: {}, required: [] };
  let props: Obj = { ...(s.properties ?? {}) };
  let required: string[] = Array.isArray(s.required) ? [...s.required] : [];
  if (depth < 3) {
    for (const part of Array.isArray(s.allOf) ? s.allOf : []) {
      const sub = collectProps(spec, part, depth + 1);
      props = { ...props, ...sub.props };
      required = [...required, ...sub.required];
    }
  }
  return { props, required };
}

export class ApiIndex {
  private constructor(readonly endpoints: ApiEndpoint[]) {}

  static fromSpec(spec: unknown): ApiIndex {
    const root = (spec ?? {}) as Obj;
    const endpoints: ApiEndpoint[] = [];
    for (const [rawPath, item] of Object.entries((root.paths ?? {}) as Obj)) {
      const url = normalizePath(rawPath);
      const pathLevel: any[] = Array.isArray(item?.parameters) ? item.parameters : [];
      for (const m of METHODS) {
        const op = item?.[m];
        if (!op || typeof op !== "object") continue;
        const method = m.toUpperCase();
        const byKey = new Map<string, ApiParam>();
        const opParams: any[] = Array.isArray(op.parameters) ? op.parameters : [];
        for (const raw of [...pathLevel, ...opParams]) {
          const p = resolveRef(root, raw);
          if (!p || (p.in !== "path" && p.in !== "query") || typeof p.name !== "string") continue;
          const schema = resolveRef(root, p.schema);
          byKey.set(`${p.in}:${p.name}`, {
            name: p.name, in: p.in, required: p.in === "path" ? true : p.required === true,
            ...(schema?.type ? { type: String(schema.type) } : {}),
            ...(p.description ? { description: String(p.description) } : {}),
          });
        }
        const ep: ApiEndpoint = {
          id: `${method}:${url}`, method, url,
          summary: String(op.summary ?? ""), description: String(op.description ?? ""),
          tags: Array.isArray(op.tags) ? op.tags.map(String) : [],
          parameters: [...byKey.values()],
        };
        const rb = resolveRef(root, op.requestBody);
        const schema = rb?.content?.["application/json"]?.schema;
        if (rb && schema) {
          const { props, required } = collectProps(root, schema);
          ep.requestBody = {
            required: rb.required === true,
            properties: Object.entries(props).map(([name, def]) => {
              const d = resolveRef(root, def);
              return {
                name, required: required.includes(name),
                ...(d?.type ? { type: String(d.type) } : {}),
                ...(d?.description ? { description: String(d.description) } : {}),
              };
            }),
          };
        }
        endpoints.push(ep);
      }
    }
    return new ApiIndex(endpoints);
  }

  search(query: string, o: { tags?: string[]; limit?: number } = {}): ApiEndpoint[] {
    const tokens = query.toLowerCase().split(/\s+/).filter(Boolean);
    const scored: { ep: ApiEndpoint; score: number }[] = [];
    for (const ep of this.endpoints) {
      if (o.tags?.length && !ep.tags.some((t) => o.tags!.includes(t))) continue;
      const summary = ep.summary.toLowerCase(), url = ep.url.toLowerCase(), desc = ep.description.toLowerCase();
      const tags = ep.tags.map((t) => t.toLowerCase()), method = ep.method.toLowerCase();
      let score = 0;
      for (const t of tokens) {
        if (summary.includes(t)) score += 4;
        if (url.includes(t)) score += 2;
        if (desc.includes(t)) score += 2;
        if (tags.some((x) => x.includes(t))) score += 1.5;
        if (method.includes(t)) score += 0.5;
      }
      if (score > 0) scored.push({ ep, score });
    }
    scored.sort((a, b) => b.score - a.score || (a.ep.url < b.ep.url ? -1 : a.ep.url > b.ep.url ? 1 : 0));
    const out = scored.map((s) => s.ep);
    return o.limit ? out.slice(0, o.limit) : out;
  }

  lookup(method: string, url: string): ApiEndpoint | undefined {
    return this.endpoints.find((e) => e.id === `${method.toUpperCase()}:${url}`);
  }

  tags(): string[] {
    return [...new Set(this.endpoints.flatMap((e) => e.tags))].sort();
  }
}

const CACHE_MS = 10 * 60 * 1000;
const cache = new Map<string, { at: number; index: ApiIndex }>();

export async function getApiIndex(client: TeableClient, openapiUrl: string): Promise<ApiIndex> {
  const hit = cache.get(openapiUrl);
  if (hit && Date.now() - hit.at < CACHE_MS) return hit.index;
  const index = ApiIndex.fromSpec(await client.fetchAbsolute(openapiUrl));
  cache.set(openapiUrl, { at: Date.now(), index });
  return index;
}

export function buildRequest(ep: ApiEndpoint, params: Record<string, unknown> = {}):
    { path: string; query: Record<string, string | string[]> } {
  const missing = ep.parameters.filter((p) => p.required && (params[p.name] === undefined || params[p.name] === null)).map((p) => p.name);
  if (missing.length) throw new ToolInputError(`Invalid parameters: missing ${missing.join(", ")}`, { parameters: ep.parameters });
  const pathNames = new Set(ep.parameters.filter((p) => p.in === "path").map((p) => p.name));
  const path = ep.url.replace(/\{([^}]+)\}/g, (_m, name: string) => encodeURIComponent(String(params[name])));
  const query: Record<string, string | string[]> = {};
  for (const [k, v] of Object.entries(params)) {
    if (pathNames.has(k) || v === undefined || v === null) continue;
    const enc = (x: unknown) => (typeof x === "object" && x !== null ? JSON.stringify(x) : String(x));
    query[k] = Array.isArray(v) ? v.map(enc) : enc(v);
  }
  return { path, query };
}
