export class ConfigError extends Error {}
export interface Config {
  transport: "stdio" | "http"; teableUrl: string; token?: string;
  http: { host: string; port: number; allowedOrigins: string[] }; openapiUrl: string;
}
type Env = Record<string, string | undefined>;

export function loadConfig(argv: string[], env: Env): Config {
  const transport = argv.includes("--http") || env.OTA_TRANSPORT === "http" ? "http" : "stdio";
  const rawUrl = env.TEABLE_URL?.trim();
  if (!rawUrl) throw new ConfigError("TEABLE_URL is required (Teable origin, e.g. http://127.0.0.1:3000)");
  let teableUrl: string;
  try { teableUrl = new URL(rawUrl).toString().replace(/\/+$/, ""); }
  catch { throw new ConfigError(`TEABLE_URL is not a valid URL: ${rawUrl}`); }
  const token = transport === "stdio" ? env.TEABLE_TOKEN?.trim() : undefined;
  if (transport === "stdio" && !token) throw new ConfigError("TEABLE_TOKEN is required in stdio mode");
  const port = env.OTA_HTTP_PORT ? Number(env.OTA_HTTP_PORT) : 3100;
  if (!Number.isInteger(port) || port < 0 || port > 65535) throw new ConfigError(`OTA_HTTP_PORT invalid: ${env.OTA_HTTP_PORT}`);
  const allowedOrigins = (env.OTA_ALLOWED_ORIGINS ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  return { transport, teableUrl, token, http: { host: env.OTA_HTTP_HOST?.trim() || "127.0.0.1", port, allowedOrigins },
    openapiUrl: env.OTA_OPENAPI_URL?.trim() || `${teableUrl}/redocs/swagger.json` };
}
