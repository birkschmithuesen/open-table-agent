import type { ToolDef } from "./types.js";
import { tool as listBases } from "./list-bases.js";
import { tool as getTablesMeta } from "./get-tables-meta.js";
import { tool as getFields } from "./get-fields.js";
import { tool as getRecords } from "./get-records.js";
import { tool as sqlQuery } from "./sql-query.js";
import { tool as getDoc } from "./get-doc.js";

export const TOOLS: ToolDef[] = [listBases, getTablesMeta, getFields, getRecords, sqlQuery, getDoc];
