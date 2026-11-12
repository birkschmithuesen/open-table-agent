import { z } from "zod";
import { WRITE, type ToolDef } from "./types.js";
import { getApiIndex, buildRequest } from "../openapi/index.js";
import { TeableApiError } from "../teable/client.js";
import { ToolInputError } from "../result.js";

export const tool: ToolDef = {
  name: "call-api-write", title: "Call API (write)", annotations: WRITE(true),
  description: "Call a POST/PUT/PATCH/DELETE endpoint of the Teable REST API. url is the endpoint template from search-api; "
    + "params holds path and query parameters; data is the JSON request body (object or JSON string). Changes data: confirm intent first.",
  inputSchema: {
    method: z.enum(["POST", "PUT", "PATCH", "DELETE"]),
    url: z.string().min(1),
    params: z.record(z.string(), z.unknown()).optional(),
    data: z.union([z.record(z.string(), z.unknown()), z.string()]).optional(),
  },
  async handler({ method, url, params, data }, { client, config }) {
    const idx = await getApiIndex(client, config.openapiUrl);
    const ep = idx.lookup(method, url);
    if (!ep) return { success: false, error: `Unknown API ${method} ${url} — use search-api to find the endpoint template` };
    let body: unknown = data;
    if (typeof data === "string") {
      try { body = JSON.parse(data); }
      catch { throw new ToolInputError("Invalid data: not valid JSON"); }
    }
    if (ep.requestBody?.required && body === undefined) {
      throw new ToolInputError("Invalid data: this endpoint requires a request body", { requestBody: ep.requestBody });
    }
    const { path, query } = buildRequest(ep, params ?? {});
    try {
      const res = await client.request(method, path, { query, body });
      return { success: true, statusCode: res.status, data: res.data };
    } catch (e) {
      if (e instanceof TeableApiError) return { success: false, statusCode: e.status, error: e.message };
      throw e;
    }
  },
};
