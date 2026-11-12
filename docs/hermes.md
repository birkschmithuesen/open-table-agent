# Wiring open-table-agent into Hermes

## 1. Agent identity and token

Give the agent its own Teable identity so that safety comes from the token, not from the tool list.

1. Create a dedicated Teable user, for example `agent@<your-domain>`.
2. Invite it only to the spaces and bases it may touch, with the lowest sufficient role.
3. As that user, create a personal access token with exactly the scopes it needs:
   - read access: `base|read`, `base|query_data`, `table|read`, `field|read`, `record|read`
   - write access additionally: `record|create`, `record|update`, `record|delete`
4. Put the token in the Hermes profile `.env` as `OTA_TEABLE_TOKEN`. Never write it into `config.yaml`.

```
OTA_TEABLE_TOKEN=<personal access token>
```

## 2. stdio entry (Hermes on the same host)

Build the server first (`npm ci --prefix server`, `npm run build --prefix server`), then add to the
profile `config.yaml`:

```yaml
mcp_servers:
  open-table-agent:
    command: node
    args: [/mnt/HC_Volume_106183673/projekte/open-table-agent/server/dist/index.js]
    env: {TEABLE_URL: "http://127.0.0.1:3000", TEABLE_TOKEN: "${OTA_TEABLE_TOKEN}"}
    connect_timeout: 30.0
    enabled: true
```

## 3. HTTP entry

Start the server with `--http` (bound to `127.0.0.1` by default; set `OTA_HTTP_HOST` for a Tailscale
address). The server does not read `TEABLE_TOKEN` in this mode; Hermes sends the token as a bearer header.

```
TEABLE_URL=http://127.0.0.1:3000 node /mnt/HC_Volume_106183673/projekte/open-table-agent/server/dist/index.js --http
```

```yaml
mcp_servers:
  open-table-agent-http:
    url: "http://127.0.0.1:3100/mcp"
    headers: {Authorization: "Bearer ${OTA_TEABLE_TOKEN}"}
    enabled: true
```

## Placeholder interpolation

Checked in the Hermes source (`tools/mcp_tool_config.py`, `_interpolate_env_vars`): `${VAR}` placeholders are
resolved recursively over the whole server config, including stdio `env` values, not only `url` and
`headers`. Two caveats from the same code: an unset or empty variable keeps the literal `${OTA_TEABLE_TOKEN}`
text, and remote servers whose `url` or `headers` still contain an unresolved placeholder fail closed.
For a stdio server an unresolved `env` value would be passed to the server as the literal string, which
Teable rejects as an invalid token, so confirm `OTA_TEABLE_TOKEN` is set in the profile `.env`.

## Check it

1. Start Hermes with the profile and confirm the MCP server connects (no timeout within `connect_timeout`).
2. `tools/list` shows 12 tools: `list-bases`, `get-tables-meta`, `get-fields`, `get-records`, `sql-query`,
   `get-doc`, `search-api`, `call-api-read`, `create-records`, `update-records`, `delete-records`,
   `call-api-write`.
3. Ask the agent to run `list-bases`; it should return the bases the agent user can see.
4. Ask it to create or delete a record: Hermes should ask for confirmation, because the write tools carry
   `readOnlyHint: false` annotations (`destructiveHint: true` for update, delete and `call-api-write`).
5. For HTTP, `curl http://127.0.0.1:3100/health` returns `{"ok":true}`.
6. A write with a read-only token returns Teable's 403 as an error result; that is the intended safety net.
