import type { ToolDef } from "./types.js";
import { tool as listBases } from "./list-bases.js";
import { tool as getTablesMeta } from "./get-tables-meta.js";
import { tool as getFields } from "./get-fields.js";
import { tool as getRecords } from "./get-records.js";
import { tool as sqlQuery } from "./sql-query.js";
import { tool as getDoc } from "./get-doc.js";
import { tool as searchApi } from "./search-api.js";
import { tool as callApiRead } from "./call-api-read.js";
import { tool as callApiWrite } from "./call-api-write.js";
import { tool as createRecords } from "./create-records.js";
import { tool as updateRecords } from "./update-records.js";
import { tool as deleteRecords } from "./delete-records.js";

export const TOOLS: ToolDef[] = [listBases, getTablesMeta, getFields, getRecords, sqlQuery, getDoc, searchApi, callApiRead,
  createRecords, updateRecords, deleteRecords, callApiWrite];
