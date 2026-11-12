#!/usr/bin/env node
import { loadConfig, ConfigError } from "./config.js";

export async function main(argv = process.argv.slice(2), env = process.env): Promise<void> {
  loadConfig(argv, env);
}
main().catch((err) => {
  process.stderr.write(`open-table-agent: ${err instanceof ConfigError ? err.message : String(err?.stack ?? err)}\n`);
  process.exit(err instanceof ConfigError ? 2 : 1);
});
