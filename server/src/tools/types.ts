import type { ZodRawShape } from "zod";
import type { ToolAnnotations } from "@modelcontextprotocol/sdk/types.js";
import type { TeableClient } from "../teable/client.js";
import type { Config } from "../config.js";

export interface ToolContext { client: TeableClient; config: Config }
export interface ToolDef {
  name: string; title: string; description: string; inputSchema: ZodRawShape;
  annotations: ToolAnnotations; handler(args: any, ctx: ToolContext): Promise<object>;
}
export const READ: ToolAnnotations = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
export const WRITE = (destructive: boolean): ToolAnnotations =>
  ({ readOnlyHint: false, destructiveHint: destructive, idempotentHint: false, openWorldHint: false });
