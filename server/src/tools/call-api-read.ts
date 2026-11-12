import { z } from "zod";
import { READ, type ToolDef } from "./types.js";
import { getApiIndex, buildRequest } from "../openapi/index.js";
import { TeableApiError } from "../teable/client.js";

export const tool: ToolDef = {
  name: "call-api-read", title: "Call API (read)", annotations: READ,
  description: "Call a GET endpoint of the Teable REST API. url is the endpoint template from search-api "
    + "(e.g. /table/{tableId}/view); params holds path and query parameters.",
  inputSchema: { url: z.string().min(1), params: z.record(z.string(), z.unknown()).optional() },
  async handler({ url, params }, { client, config }) {
    const idx = await getApiIndex(client, config.openapiUrl);
    const ep = idx.lookup("GET", url);
    if (!ep) return { success: false, error: `Unknown API GET ${url} — use search-api to find the endpoint template` };
    const { path, query } = buildRequest(ep, params ?? {});
    try {
      const res = await client.request("GET", path, { query });
      return { success: true, statusCode: res.status, data: res.data };
    } catch (e) {
      if (e instanceof TeableApiError) return { success: false, statusCode: e.status, error: e.message };
      throw e;
    }
  },
};
