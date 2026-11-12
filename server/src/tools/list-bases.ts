import { z } from "zod";
import { READ, type ToolDef } from "./types.js";
import type { TeableBase } from "../teable/types.js";

const PAGE_CHAR_BUDGET = 59000;
export const tool: ToolDef = {
  name: "list-bases", title: "List bases", annotations: READ,
  description: "List the bases (projects) the token can access. Optional case-insensitive search on name or id, optional spaceId, paging via limit/offset.",
  inputSchema: { search: z.string().optional(), spaceId: z.string().optional(),
    limit: z.number().int().min(1).max(100).default(50), offset: z.number().int().min(0).default(0) },
  async handler({ search, spaceId, limit, offset }, { client }) {
    const all = (await client.request<TeableBase[]>("GET", "/base/access/all")).data;
    const q = search?.toLowerCase();
    const nameOf = (b: TeableBase) => b.name ?? "";
    const matched = all.filter((b) => (!spaceId || b.spaceId === spaceId) &&
      (!q || nameOf(b).toLowerCase().includes(q) || b.id.toLowerCase().includes(q)));
    const page: object[] = [];
    let chars = 0;
    for (const b of matched.slice(offset, offset + limit)) {
      const name = nameOf(b);
      const item = { id: b.id, name: name.length > 200 ? name.slice(0, 199) + "…" : name, spaceId: b.spaceId, role: b.role };
      chars += JSON.stringify(item).length;
      if (page.length > 0 && chars > PAGE_CHAR_BUDGET) break;
      page.push(item);
    }
    const next = offset + page.length;
    const hasMore = next < matched.length;
    return { success: true, offset, hasMore, ...(hasMore ? { nextOffset: next } : {}), bases: page };
  },
};
