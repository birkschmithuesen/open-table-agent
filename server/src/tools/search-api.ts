import { z } from "zod";
import { READ, type ToolDef } from "./types.js";
import { getApiIndex } from "../openapi/index.js";

export const tool: ToolDef = {
  name: "search-api", title: "Search API", annotations: READ,
  description: "Search the Teable REST API for endpoints not covered by the dedicated tools. Returns method, url template, "
    + "parameters and body properties; pass the url template to call-api-read (GET) or call-api-write.",
  inputSchema: {
    query: z.string().min(1),
    tags: z.array(z.string()).optional(),
    limit: z.coerce.number().int().min(1).max(10).default(5),
  },
  async handler({ query, tags, limit }, { client, config }) {
    const idx = await getApiIndex(client, config.openapiUrl);
    const found = idx.search(query, { tags, limit });
    if (!found.length) return { success: true, results: [], availableTags: idx.tags(), hint: "try other words or a tag" };
    return {
      success: true, totalApiCount: idx.endpoints.length,
      results: found.map((e) => ({ method: e.method, url: e.url, summary: e.summary, description: e.description,
        tags: e.tags, parameters: e.parameters, requestBody: e.requestBody })),
    };
  },
};
