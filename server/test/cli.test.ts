import { it, expect } from "vitest";
import { spawnSync } from "node:child_process";

it("fails loudly without TEABLE_URL", () => {
  const r = spawnSync(process.execPath, ["--import", "tsx", "src/index.ts"], {
    cwd: new URL("..", import.meta.url).pathname, env: { PATH: process.env.PATH }, encoding: "utf8" });
  expect(r.status).toBe(2);
  expect(r.stderr).toMatch(/^open-table-agent: .*TEABLE_URL/m);
});
