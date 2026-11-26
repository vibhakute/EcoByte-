"""Automatic WhatsApp, end to end, WITHOUT contacting Meta or Twilio.

Runs its own server on port 8012 against a throw-away database and replaces the provider HTTP call
with a fake that behaves like the real APIs (ids, statuses, error codes). Run from backend/:

    python -m tests.whatsapp_test
"""
import base64
import hashlib
import hmac
import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="ecobyte_wa_"))
os.environ["DATABASE_URL"] = f"sqlite:///{(TMP / 'wa.db').as_posix()}"
os.environ["ECOBYTE_URL"] = "http://127.0.0.1:8012"

from datetime import datetime, timedelta  # noqa: E402

import uvicorn  # noqa: E402

from app import seed  # noqa: E402
from app.services import whatsapp as W  # noqa: E402
from tests.client import check, counter, login, req  # noqa: E402

CALLS = []
FAIL_NEXT = {}


def fake_http(method, url, headers, data=None, timeout=15):
    CALLS.append((method, url, headers, data))
    if "graph.facebook.com" in url:
        p = json.loads(data)
        if "error" in FAIL_NEXT:
            return 400, {"error": {"code": FAIL_NEXT.pop("error"), "message": "x"}}
        return 200, {"messaging_product": "whatsapp", "contacts": [{"wa_id": p["to"]}], "messages": [{"id": f"wamid.{len(CALLS)}"}]}
    if "api.twilio.com" in url and method == "POST":
        if "twilio" in FAIL_NEXT:
            return 400, {"code": FAIL_NEXT.pop("twilio"), "message": "x"}
        return 201, {"sid": f"SM{len(CALLS):032d}", "status": "queued"}
    if "api.twilio.com" in url and method == "GET":
        return 200, {"sid": url.rsplit("/", 1)[1][:-5], "status": "delivered", "error_code": None}
    raise AssertionError(f"unexpected call {url}")


W._http = fake_http


def main():
    seed.run(reset=True)
    from app.main import app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8012, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.2)
    A = login("admin@ecobyte.app", "Admin@123", "admin")
    S = login("student@ecobyte.app", "Student@123", "student")

    print("Setup")
    c = req("GET", "/api/admin/whatsapp/config", A).json()
    check(c["provider"] == "off" and not c["ready"], "starts switched off (nothing is sent)")
    check(req("GET", "/api/admin/whatsapp/config", S).status_code == 403, "students cannot see WhatsApp settings")
    check(req("POST", "/api/admin/whatsapp/test", A, {"phone": "+91 90000 00001"}).status_code == 400, "test refused until a provider is set")
    sid, tok = "AC" + "a" * 32, "twilio-secret-token-1234"
    r = req("PUT", "/api/admin/whatsapp/config", A, {"provider": "twilio", "twilio_sid": sid, "twilio_token": tok, "twilio_from": "+1 415 523 8886"})
    c = r.json()
    check(r.status_code == 200 and c["ready"] and c["twilio_from"] == "14155238886", "Twilio configured")
    check(tok not in r.content.decode() and c["twilio_token"]["hint"] == "…1234", "secret token never returned, only a hint")
    r = req("PUT", "/api/admin/whatsapp/config", A, {"provider": "twilio", "twilio_sid": sid, "twilio_token": "", "twilio_from": "14155238886"})
    check(r.json()["ready"], "blank token on save keeps the saved one")

    print("Twilio sending + status")
    m = req("POST", "/api/admin/whatsapp/test", A, {"phone": "+91 90000 00001"}).json()
    check(m["status"] == "pending" and m["phone"] == "919000000001" and m["provider_id"].startswith("SM"), "test message handed to Twilio")
    post = CALLS[-1]
    form = urllib.parse.parse_qs(post[3].decode())
    check(form["To"] == ["whatsapp:+919000000001"] and form["From"] == ["whatsapp:+14155238886"], "correct whatsapp: To/From")
    log = req("GET", "/api/admin/whatsapp/messages", A).json()
    check(log[0]["status"] == "delivered", "status polled from Twilio: delivered")
    FAIL_NEXT["twilio"] = 63015
    m = req("POST", "/api/admin/whatsapp/test", A, {"phone": "9000000002"}).json()
    check(m["status"] == "failed" and "join" in m["error"], "sandbox not joined → clear failure reason")

    print("Twilio status webhook signature")
    params = {"MessageSid": log[0]["provider_id"], "MessageStatus": "read"}
    url = "http://127.0.0.1:8012/api/public/whatsapp/twilio-status"
    sig = base64.b64encode(hmac.new(tok.encode(), (url + "".join(k + params[k] for k in sorted(params))).encode(), hashlib.sha1).digest()).decode()
    body = urllib.parse.urlencode(params)
    def raw_post(path, data, headers):
        rq = urllib.request.Request("http://127.0.0.1:8012" + path, data=data, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(rq) as x:
                return x.status
        except urllib.error.HTTPError as e:
            return e.code
    form_h = {"Content-Type": "application/x-www-form-urlencoded"}
    check(raw_post("/api/public/whatsapp/twilio-status", body.encode(), {**form_h, "X-Twilio-Signature": "bad"}) == 403, "forged Twilio callback rejected")
    check(raw_post("/api/public/whatsapp/twilio-status", body.encode(), {**form_h, "X-Twilio-Signature": sig}) == 200, "signed Twilio callback accepted")

    print("Donations: manual send + auto-send")
    ngos = req("GET", "/api/admin/ngos", A).json()
    for name, phone in [("Test NGO One", "+91 90000 00011"), ("Test NGO Two", "+91 90000 00012")]:
        ngos.append(req("POST", "/api/admin/ngos", A, {"name": name, "phone": phone}).json())
    now = datetime.now()
    don = {"food_name": "Veg Pulao", "category": "Cooked meal", "is_veg": True, "quantity": 20, "unit": "portions",
           "prepared_at": (now - timedelta(minutes=30)).isoformat(timespec="minutes"),
           "safe_until": (now + timedelta(hours=4)).isoformat(timespec="minutes"),
           "pickup_deadline": (now + timedelta(hours=2)).isoformat(timespec="minutes"),
           "pickup_location": "Main canteen", "food_safety_confirmed": True}
    d = req("POST", "/api/admin/donations", A, don).json()
    check(d["whatsapp_auto"] == 0, "no auto-send while auto-send is off")
    r = req("POST", f"/api/admin/donations/{d['id']}/whatsapp", A, {"ngo_ids": [n["id"] for n in ngos], "base_url": "http://127.0.0.1:8012"}).json()
    check(r["sent"] == len(ngos) and r["failed"] == 0, f"donation sent to {len(ngos)} NGOs")
    text = urllib.parse.parse_qs(CALLS[-1][3].decode())["Body"][0]
    check("Veg Pulao" in text and "/d/" in text, "message has the food and a secure accept link")
    check(r["donation"]["invites_sent"] == len(ngos) and r["donation"]["status"] == "request_sent", "one secure link per NGO; status request sent")
    req("PUT", "/api/admin/whatsapp/config", A, {"provider": "twilio", "auto_send": True, "twilio_sid": sid, "twilio_from": "14155238886"})
    before = len(CALLS)
    d2 = req("POST", "/api/admin/donations", A, {**don, "food_name": "Dal Rice"}).json()
    check(d2["whatsapp_auto"] == len(ngos), "auto-send queued for every active NGO")
    for _ in range(30):
        if len([x for x in CALLS[before:] if x[0] == "POST"]) >= len(ngos):
            break
        time.sleep(0.2)
    msgs = req("GET", "/api/admin/whatsapp/messages", A, params={"donation_id": d2["id"]}).json()
    check(len(msgs) == len(ngos) and all(x["kind"] == "donation" for x in msgs), "auto-sent messages logged per NGO")

    print("Meta Cloud API")
    r = req("PUT", "/api/admin/whatsapp/config", A, {"provider": "meta", "meta_phone_number_id": "123456", "meta_token": "EAAG-secret-abcd",
                                                     "meta_verify_token": "verify-me", "meta_app_secret": "appsecret-9876"})
    check(r.json()["ready"] and "EAAG-secret" not in r.content.decode() and "appsecret" not in r.content.decode(), "Meta configured, secrets hidden")
    m = req("POST", "/api/admin/whatsapp/test", A, {"phone": "+91 90000 00001", "mode": "hello_world"}).json()
    sent = json.loads(CALLS[-1][3])
    check(m["status"] == "sent" and sent["type"] == "template" and sent["template"]["name"] == "hello_world", "hello_world template sent")
    check(CALLS[-1][2]["Authorization"] == "Bearer EAAG-secret-abcd" and "/123456/messages" in CALLS[-1][1], "uses the phone number id + token")
    m2 = req("POST", "/api/admin/whatsapp/test", A, {"phone": "+91 90000 00001"}).json()
    check(json.loads(CALLS[-1][3])["type"] == "text", "plain text test")
    FAIL_NEXT["error"] = 131030
    m3 = req("POST", "/api/admin/whatsapp/test", A, {"phone": "+91 90000 00009"}).json()
    check(m3["status"] == "failed" and "recipient list" in m3["error"], "number not in Meta test list → clear reason")

    print("Meta webhook")
    check(req("GET", "/api/public/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"}).content == b"42",
          "webhook verification echoes the challenge")
    check(req("GET", "/api/public/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "42"}).status_code == 403,
          "wrong verify token rejected")
    payload = json.dumps({"entry": [{"changes": [{"value": {
        "statuses": [{"id": m["provider_id"], "status": "delivered"}, {"id": m2["provider_id"], "status": "failed", "errors": [{"code": 131047}]}],
        "messages": [{"id": "wamid.in1", "from": "919000000001", "type": "text", "text": {"body": "We can collect"}}]}}]}]}).encode()
    good = "sha256=" + hmac.new(b"appsecret-9876", payload, hashlib.sha256).hexdigest()
    json_h = {"Content-Type": "application/json"}
    check(raw_post("/api/public/whatsapp/webhook", payload, {**json_h, "X-Hub-Signature-256": "sha256=00"}) == 403, "unsigned webhook rejected")
    check(raw_post("/api/public/whatsapp/webhook", payload, {**json_h, "X-Hub-Signature-256": good}) == 200, "signed webhook accepted")
    log = {x["provider_id"]: x for x in req("GET", "/api/admin/whatsapp/messages", A).json()}
    check(log[m["provider_id"]]["status"] == "delivered", "delivery receipt recorded")
    check(log[m2["provider_id"]]["status"] == "failed" and "24 hours" in log[m2["provider_id"]]["error"], "24-hour-window failure explained")
    check(log["wamid.in1"]["direction"] == "in" and log["wamid.in1"]["body"] == "We can collect", "NGO reply logged")

    print("Removing an NGO")
    gone = ngos[-1]
    inv = next(i for i in req("GET", f"/api/admin/donations/{d['id']}", A).json()["invites"] if i["ngo_id"] == gone["id"])
    r = req("DELETE", f"/api/admin/ngos/{gone['id']}", A).json()
    check(r["deleted"] == "Test NGO Two" and r["links_revoked"] >= 1, "NGO removed and its unanswered links revoked")
    check(all(n["id"] != gone["id"] for n in req("GET", "/api/admin/ngos", A).json()), "removed NGO no longer listed")
    check(all(i["id"] != inv["id"] for i in req("GET", f"/api/admin/donations/{d['id']}", A).json()["invites"]), "its secure link no longer exists")
    check(any(x["ngo_name"] == "Test NGO Two" for x in req("GET", "/api/admin/whatsapp/messages", A).json()), "message history kept")
    check(req("DELETE", f"/api/admin/ngos/{gone['id']}", S).status_code == 403, "students cannot remove NGOs")

    server.should_exit = True
    print(f"\nAll {counter['ok']} WhatsApp checks passed (no real messages were sent).")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print("FAILED:", e)
        sys.exit(1)
