"""Tiny standard-library HTTP client + check() helper shared by the end-to-end tests."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

BASE = os.getenv("ECOBYTE_URL", "http://127.0.0.1:8000")
counter = {"ok": 0}


class Resp:
    def __init__(self, status, body):
        self.status_code, self.content = status, body

    def json(self):
        return json.loads(self.content)


def req(method, path, headers=None, body=None, params=None):
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps(body).encode() if body is not None and method != "GET" else None
    r = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})}, method=method)
    try:
        with urllib.request.urlopen(r, timeout=120) as x:
            return Resp(x.status, x.read())
    except urllib.error.HTTPError as e:
        return Resp(e.code, e.read())


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    counter["ok"] += 1
    print("  ok -", msg)


def login(ident, pw, portal):
    r = req("POST", "/api/auth/login", body={"email": ident, "password": pw, "portal": portal})
    return {"Authorization": f"Bearer {r.json()['token']}"} if r.status_code == 200 else r
