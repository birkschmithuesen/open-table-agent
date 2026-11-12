import { it, expect } from "vitest";
import { spawnSync, spawn } from "node:child_process";

it("binds to 127.0.0.1 by default", async () => {
  const child = spawn(process.execPath, ["--import", "tsx", "src/index.ts", "--http"], {
    cwd: new URL("..", import.meta.url).pathname,
    env: { PATH: process.env.PATH, TEABLE_URL: "http://127.0.0.1:9", OTA_HTTP_PORT: "0" } });
  try {
    const line = await new Promise<string>((resolve, reject) => {
      let buf = "";
      const t = setTimeout(() => reject(new Error(`no listening line: ${buf}`)), 15000);
      child.stderr.on("data", (d) => {
        buf += d;
        if (buf.includes("listening on http://127.0.0.1:")) { clearTimeout(t); resolve(buf); }
      });
      child.on("exit", () => reject(new Error(`exited early: ${buf}`)));
    });
    expect(line).toContain("open-table-agent: listening on http://127.0.0.1:");
  } finally { child.kill(); }
}, 20000);

it("fails loudly without TEABLE_URL", () => {
  const r = spawnSync(process.execPath, ["--import", "tsx", "src/index.ts"], {
    cwd: new URL("..", import.meta.url).pathname, env: { PATH: process.env.PATH }, encoding: "utf8" });
  expect(r.status).toBe(2);
  expect(r.stderr).toMatch(/^open-table-agent: .*TEABLE_URL/m);
});
