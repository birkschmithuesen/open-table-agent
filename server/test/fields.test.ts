import { describe, it, expect } from "vitest";
import { resolveFieldKey, mapFilterFieldIds } from "../src/teable/fields.js";
import { ToolInputError } from "../src/result.js";

const fields = [
  { id: "fldName0001", name: "Name", type: "singleLineText" },
  { id: "fldCount001", name: "Count", type: "number" },
  { id: "fldLimit001", name: "Limit", type: "number" },
];

describe("resolveFieldKey", () => {
  it("prefers exact id, then case-insensitive name", () => {
    expect(resolveFieldKey(fields, "fldCount001")).toBe("fldCount001");
    expect(resolveFieldKey(fields, "count")).toBe("fldCount001");
  });
  it("unknown key throws with suggestions", () => {
    try { resolveFieldKey(fields, "Coun"); throw new Error("no throw"); }
    catch (e) {
      expect(e).toBeInstanceOf(ToolInputError);
      expect((e as ToolInputError).extra.suggestions).toEqual(["Count"]);
    }
  });
});

describe("mapFilterFieldIds", () => {
  it("maps names inside nested filter groups", () => {
    const v1 = { conjunction: "and", filterSet: [
      { fieldId: "Name", operator: "is", value: "a" },
      { conjunction: "or", filterSet: [{ fieldId: "count", operator: "isGreater", value: { type: "field", fieldId: "Limit" } }] },
    ] };
    expect(mapFilterFieldIds(v1, fields)).toEqual({ conjunction: "and", filterSet: [
      { fieldId: "fldName0001", operator: "is", value: "a" },
      { conjunction: "or", filterSet: [{ fieldId: "fldCount001", operator: "isGreater", value: { type: "field", fieldId: "fldLimit001" } }] },
    ] });
    const v2 = { not: { conjunction: "and", items: [{ fieldId: "Name", operator: "isEmpty", value: null }] } };
    expect(mapFilterFieldIds(v2, fields)).toEqual({ not: { conjunction: "and", items: [{ fieldId: "fldName0001", operator: "isEmpty", value: null }] } });
  });
  it("throws on an unknown name instead of passing it through", () => {
    expect(() => mapFilterFieldIds({ fieldId: "Nope", operator: "is", value: 1 }, fields)).toThrow(/Unknown field: Nope/);
  });
});
