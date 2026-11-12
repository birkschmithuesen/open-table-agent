import { describe, it, expect } from "vitest";
import { loadConfig, ConfigError } from "../src/config.js";

describe("loadConfig", () => {
  it("defaults to stdio, needs TEABLE_URL and TEABLE_TOKEN", () => {
    const c = loadConfig([], { TEABLE_URL: "http://t:3000/", TEABLE_TOKEN: "tok" });
    expect(c).toMatchObject({ transport: "stdio", teableUrl: "http://t:3000", token: "tok",
      http: { host: "127.0.0.1", port: 3100, allowedOrigins: [] }, openapiUrl: "http://t:3000/redocs/swagger.json" });
  });
  it("http mode via --http ignores TEABLE_TOKEN", () => {
    const c = loadConfig(["--http"], { TEABLE_URL: "http://t", TEABLE_TOKEN: "env-secret", OTA_HTTP_PORT: "4000",
      OTA_ALLOWED_ORIGINS: " https://a , ,https://b" });
    expect(c.transport).toBe("http");
    expect(c.token).toBeUndefined();
    expect(c.http).toEqual({ host: "127.0.0.1", port: 4000, allowedOrigins: ["https://a", "https://b"] });
  });
  it("rejects missing TEABLE_URL, missing stdio token, bad port", () => {
    expect(() => loadConfig([], { TEABLE_TOKEN: "x" })).toThrow(ConfigError);
    expect(() => loadConfig([], { TEABLE_URL: "http://t" })).toThrow(/TEABLE_TOKEN/);
    expect(() => loadConfig(["--http"], { TEABLE_URL: "http://t", OTA_HTTP_PORT: "70000" })).toThrow(/OTA_HTTP_PORT/);
  });
});
