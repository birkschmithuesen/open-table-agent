import type { ToolDef } from "./types.js";
import { tool as listBases } from "./list-bases.js";
import { tool as getTablesMeta } from "./get-tables-meta.js";
import { tool as getFields } from "./get-fields.js";

export const TOOLS: ToolDef[] = [listBases, getTablesMeta, getFields];
