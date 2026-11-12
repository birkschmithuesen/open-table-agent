import { z } from "zod";
import { READ, type ToolDef } from "./types.js";
import { DOC_TOPICS, readDoc } from "../docs/index.js";

export const tool: ToolDef = {
  name: "get-doc", title: "Get documentation", annotations: READ,
  description: "Return a bundled reference document. Topic groups: automation.* (api, send-email, trigger), "
    + "field.* (basic, colors, formatting, formula, link, lookup, rollup, select, show-as, simple), "
    + "view.* (column, filter, group, sort, statistic), integration.slack, record.value-format, "
    + "reference.url, scrape.* (datasets, guide).",
  inputSchema: { topic: z.enum(DOC_TOPICS as [string, ...string[]]) },
  async handler({ topic }) {
    return { success: true, topic, content: readDoc(topic) };
  },
};
