#!/usr/bin/env python3
"""Bootstrap a running e2e stack over REST and print KEY=VALUE lines.

Prints TEABLE_URL, TOKEN_A, TOKEN_B, BASE_ID, TABLE_ID. Needs only the published URL (env TEABLE_URL,
default http://127.0.0.1:3010), no state from stack.py: user passwords are random per run.

Endpoints and bodies verified against upstream packages/openapi/src (auth/signup.ts, space/create.ts,
base/create.ts, table/create.ts, access-token/create.ts). On CE, sign-up needs no email verification
unless the `enableEmailVerification` setting row exists (local-auth.service.ts verifySignup); a fresh DB
has none.
"""
import datetime
import http.cookiejar
import json
import os
import secrets
import sys
import urllib.error
import urllib.request

URL = os.environ.get("TEABLE_URL", "http://127.0.0.1:3010").rstrip("/")
SCOPES = ["base|read", "base|query_data", "table|read", "field|read", "record|read", "record|create",
          "record|update", "record|delete", "space|read"]


class Session:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method, path, body=None, token=None):
        """Returns (status, parsed json or None)."""
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{URL}/api{path}", data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with self.opener.open(req, timeout=60) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, raw.decode(errors="replace")

    def ok(self, method, path, body=None):
        status, out = self.call(method, path, body)
        if status >= 300:
            raise RuntimeError(f"{method} {path} -> {status}: {out}")
        return out


def user(label):
    s = Session()
    email = f"{label}-{secrets.token_hex(4)}@e2e.example.com"
    s.ok("POST", "/auth/signup", {"email": email, "password": "Pw1" + secrets.token_hex(10)})
    return s


def make_token(s, name, space_id, base_id):
    expires = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    out = s.ok("POST", "/access-token", {"name": name, "scopes": SCOPES, "spaceIds": [space_id],
                                         "baseIds": [base_id], "expiredTime": expires})
    return out["token"]


def space_and_base(s, label):
    space = s.ok("POST", "/space", {"name": f"e2e-{label}"})
    base = s.ok("POST", "/base", {"spaceId": space["id"], "name": f"e2e-{label}"})
    return space["id"], base["id"]


def main():
    a, b = user("agent-a"), user("agent-b")
    space_a, base_a = space_and_base(a, "a")
    table = a.ok("POST", f"/base/{base_a}/table/", {
        "name": "e2e",
        "fields": [{"name": "Name", "type": "singleLineText"}, {"name": "Count", "type": "number"}],
    })
    token_a = make_token(a, "e2e-a", space_a, base_a)
    space_b, base_b = space_and_base(b, "b")
    token_b = make_token(b, "e2e-b", space_b, base_b)
    # B must not see A's base.
    status, _ = Session().call("GET", f"/base/{base_a}", token=token_b)
    if status not in (403, 404):
        raise RuntimeError(f"isolation check failed: TOKEN_B read A's base (HTTP {status})")
    for k, v in (("TEABLE_URL", URL), ("TOKEN_A", token_a), ("TOKEN_B", token_b),
                 ("BASE_ID", base_a), ("TABLE_ID", table["id"])):
        print(f"{k}={v}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"bootstrap failed: {e}", file=sys.stderr)
        sys.exit(1)
