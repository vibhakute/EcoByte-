"""Automatic WhatsApp messages to NGOs.

Two providers are supported (pick one in Donations -> WhatsApp setup):

Meta WhatsApp Cloud API (official, free test number)
    POST https://graph.facebook.com/<version>/<phone_number_id>/messages  (Bearer <access token>)
    - The free test number can only message up to 5 recipient numbers you add and verify in Meta.
    - Plain text is delivered only if the recipient messaged your number in the last 24 hours. Otherwise
      Meta accepts the request but later reports error 131047, so for "cold" messages use an approved
      template (hello_world works out of the box for testing).
    - Delivery / read receipts arrive on the webhook (/api/public/whatsapp/webhook), which needs a public
      HTTPS address (e.g. a cloudflared / ngrok tunnel) configured in Meta.

Twilio WhatsApp (sandbox, quickest to test)
    POST https://api.twilio.com/2010-04-01/Accounts/<SID>/Messages.json  (basic auth SID:token)
    - Each test phone first sends "join <your-sandbox-word>" to the sandbox number.
    - Delivery status can be fetched from Twilio at any time, so it works without a public address.

Nothing is sent when the provider is "off"; the manual wa.me links keep working either way.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import WhatsAppConfig, WhatsAppMessage

META_VERSION = "v21.0"
FINAL = {"delivered", "read", "failed", "received"}
TWILIO_STATUS = {"accepted": "pending", "queued": "pending", "sending": "pending", "scheduled": "pending", "sent": "sent",
                 "delivered": "delivered", "read": "read", "failed": "failed", "undelivered": "failed", "canceled": "failed"}

META_ERRORS = {
    131030: "This number is not in your Meta test recipient list. In Meta → WhatsApp → API Setup, add it under “To” and verify the code.",
    131047: "More than 24 hours since this number last messaged you, so WhatsApp blocked the plain-text message. "
            "Ask the NGO to send “hi” to your WhatsApp number first, or set an approved message template.",
    131026: "WhatsApp could not deliver to this number (not on WhatsApp, or an old app version).",
    131049: "Meta chose not to deliver this marketing-style message to protect the user experience. Try again later or use a utility template.",
    131056: "Too many messages to this number in a short time. Wait a little and retry.",
    132000: "The template's number of variables does not match. The donation template needs exactly 6 variables.",
    132001: "Template not found (check the name and language, and that it is approved).",
    133010: "Your sending phone number is not registered with the WhatsApp Cloud API.",
    190: "The access token is invalid or expired (temporary tokens from API Setup last 24 hours). Paste a new one.",
    100: "Meta rejected a parameter. Check the Phone number ID and the recipient number.",
    10: "The token does not have WhatsApp messaging permission.",
}
TWILIO_ERRORS = {
    20003: "Twilio rejected the Account SID / Auth Token.",
    21211: "The recipient number is invalid.",
    21608: "Trial account: this number is not verified in Twilio.",
    63007: "The From number is not enabled for WhatsApp. For the sandbox use 14155238886.",
    63015: "This number has not joined your Twilio sandbox. From that phone, send “join <your-sandbox-word>” to +1 415 523 8886.",
    63016: "Outside the 24-hour window: free text is only allowed after the recipient messages you. Ask them to message the sandbox first.",
    63003: "The recipient is not a valid WhatsApp user.",
}


# --- configuration --------------------------------------------------------------------------------

def config(db: Session) -> WhatsAppConfig:
    c = db.query(WhatsAppConfig).first()
    if c is None:
        c = WhatsAppConfig()
        db.add(c)
        db.commit()
        db.refresh(c)
    return c


def _mask(v: str) -> dict:
    return {"set": bool(v), "hint": f"…{v[-4:]}" if v and len(v) > 8 else ("saved" if v else "")}


def config_out(c: WhatsAppConfig, base_url: str = "") -> dict:
    ok, why = ready(c)
    return {
        "provider": c.provider, "auto_send": c.auto_send, "ready": ok, "problem": why,
        "meta_phone_number_id": c.meta_phone_number_id, "meta_token": _mask(c.meta_token),
        "meta_app_secret": _mask(c.meta_app_secret), "meta_verify_token": c.meta_verify_token,
        "meta_template": c.meta_template, "meta_template_lang": c.meta_template_lang,
        "twilio_sid": c.twilio_sid, "twilio_token": _mask(c.twilio_token), "twilio_from": c.twilio_from,
        "webhook_url": f"{base_url.rstrip('/')}/api/public/whatsapp/webhook" if base_url else "/api/public/whatsapp/webhook",
        "updated_at": c.updated_at.isoformat(timespec="minutes") if c.updated_at else None,
    }


def ready(c: WhatsAppConfig) -> tuple[bool, str | None]:
    if c.provider == "meta":
        if not c.meta_phone_number_id or not c.meta_token:
            return False, "Enter the Meta Phone number ID and access token."
        return True, None
    if c.provider == "twilio":
        if not (c.twilio_sid and c.twilio_token and c.twilio_from):
            return False, "Enter the Twilio Account SID, Auth Token and WhatsApp From number."
        return True, None
    return False, "Choose Twilio or Meta below, enter the details and save."


# --- HTTP -----------------------------------------------------------------------------------------

class SendError(Exception):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.message, self.code = message, code


def _http(method: str, url: str, headers: dict, data: bytes | None = None, timeout: int = 15) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=data, method=method, headers={"User-Agent": "EcoByte/2.0", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SendError(f"Could not reach the WhatsApp provider ({getattr(e, 'reason', e)}). Check the internet connection.") from e


def _meta_error(body: dict) -> SendError:
    err = body.get("error") or {}
    code = err.get("code")
    detail = (err.get("error_data") or {}).get("details") or err.get("message") or "Unknown error"
    return SendError(META_ERRORS.get(code, f"Meta error {code}: {detail}"), code)


def _send_meta(c: WhatsAppConfig, to: str, text: str, template: str | None, params: list[str] | None) -> str:
    if template:
        tpl = {"name": template, "language": {"code": c.meta_template_lang or "en_US"}}
        if params:
            tpl["components"] = [{"type": "body", "parameters": [{"type": "text", "text": p[:1000]} for p in params]}]
        payload = {"messaging_product": "whatsapp", "to": to, "type": "template", "template": tpl}
    else:
        payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, "type": "text",
                   "text": {"preview_url": True, "body": text[:4096]}}
    status, body = _http("POST", f"https://graph.facebook.com/{META_VERSION}/{c.meta_phone_number_id}/messages",
                         {"Authorization": f"Bearer {c.meta_token}", "Content-Type": "application/json"},
                         json.dumps(payload).encode())
    if status >= 400 or "error" in body:
        raise _meta_error(body)
    try:
        return body["messages"][0]["id"]
    except (KeyError, IndexError):
        raise SendError("Meta did not return a message id.")


def _twilio_auth(c: WhatsAppConfig) -> dict:
    return {"Authorization": "Basic " + base64.b64encode(f"{c.twilio_sid}:{c.twilio_token}".encode()).decode()}


def _twilio_error(body: dict) -> SendError:
    code = body.get("code") or body.get("error_code")
    return SendError(TWILIO_ERRORS.get(code, f"Twilio error {code}: {body.get('message') or body.get('error_message') or 'unknown'}"), code)


def _send_twilio(c: WhatsAppConfig, to: str, text: str, status_callback: str | None) -> tuple[str, str]:
    form = {"From": f"whatsapp:+{c.twilio_from.lstrip('+')}", "To": f"whatsapp:+{to}", "Body": text[:1600]}
    if status_callback:
        form["StatusCallback"] = status_callback
    status, body = _http("POST", f"https://api.twilio.com/2010-04-01/Accounts/{c.twilio_sid}/Messages.json",
                         {**_twilio_auth(c), "Content-Type": "application/x-www-form-urlencoded"},
                         urllib.parse.urlencode(form).encode())
    if status >= 400:
        raise _twilio_error(body)
    return body["sid"], TWILIO_STATUS.get(body.get("status"), "pending")


# --- sending --------------------------------------------------------------------------------------

def send(db: Session, phone: str, text: str, *, kind: str, ngo_id: int | None = None, ngo_name: str | None = None,
         donation_id: int | None = None, template_params: list[str] | None = None, use_template: str | None = None,
         public_base: str = "") -> WhatsAppMessage:
    """Send one message and log it. Never raises for provider errors: the log row carries the error."""
    c = config(db)
    ok, why = ready(c)
    if not ok:
        raise HTTPException(400, why)
    now = datetime.now()
    m = WhatsAppMessage(direction="out", provider=c.provider, kind=kind, phone=phone, ngo_id=ngo_id, ngo_name=ngo_name,
                        donation_id=donation_id, body=text, status="pending", created_at=now, updated_at=now)
    db.add(m)
    db.flush()
    try:
        if c.provider == "meta":
            template = use_template if use_template is not None else (c.meta_template or None)
            if template and template != "hello_world" and kind == "donation" and not template_params:
                raise SendError("The template needs the 6 donation variables.")
            if template == "hello_world":
                template_params = None
            m.provider_id = _send_meta(c, phone, text, template, template_params if template else None)
            if template:
                m.body = f"[template: {template}]" + (" " + " | ".join(template_params) if template_params else "")
            m.status = "sent"  # accepted by Meta; delivered/read/failed arrive on the webhook
        else:
            cb = f"{public_base.rstrip('/')}/api/public/whatsapp/twilio-status" if public_base.startswith("https://") else None
            m.provider_id, m.status = _send_twilio(c, phone, text, cb)
    except SendError as e:
        m.status, m.error = "failed", e.message
    m.updated_at = datetime.now()
    db.commit()
    db.refresh(m)
    return m


def refresh(db: Session, m: WhatsAppMessage) -> WhatsAppMessage:
    """Twilio: ask Twilio for the current status. Meta: statuses only arrive on the webhook."""
    c = config(db)
    if m.provider != "twilio" or not m.provider_id or m.status in FINAL or c.provider != "twilio" or not ready(c)[0]:
        return m
    try:
        status, body = _http("GET", f"https://api.twilio.com/2010-04-01/Accounts/{c.twilio_sid}/Messages/{m.provider_id}.json",
                             _twilio_auth(c))
    except SendError:
        return m
    if status < 400:
        m.status = TWILIO_STATUS.get(body.get("status"), m.status)
        if body.get("error_code"):
            m.error = TWILIO_ERRORS.get(body["error_code"], f"Twilio error {body['error_code']}: {body.get('error_message') or ''}".strip())
        m.updated_at = datetime.now()
        db.commit()
    return m


def message_out(m: WhatsAppMessage) -> dict:
    return {"id": m.id, "direction": m.direction, "provider": m.provider, "kind": m.kind, "phone": m.phone, "ngo_id": m.ngo_id,
            "ngo_name": m.ngo_name, "donation_id": m.donation_id, "body": m.body, "status": m.status, "error": m.error,
            "provider_id": m.provider_id, "created_at": m.created_at.isoformat(timespec="seconds"),
            "updated_at": m.updated_at.isoformat(timespec="seconds")}


# --- webhooks -------------------------------------------------------------------------------------

def meta_signature_ok(c: WhatsAppConfig, raw: bytes, header: str | None) -> bool:
    if not c.meta_app_secret:
        return True  # no app secret configured: accept (status updates only; documented in the setup screen)
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(c.meta_app_secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[7:])


def handle_meta(db: Session, payload: dict) -> int:
    n = 0
    for entry in payload.get("entry", []):
        for ch in entry.get("changes", []):
            v = ch.get("value", {})
            for st in v.get("statuses", []):
                m = db.query(WhatsAppMessage).filter_by(provider_id=st.get("id")).first()
                if not m:
                    continue
                new = {"sent": "sent", "delivered": "delivered", "read": "read", "failed": "failed"}.get(st.get("status"))
                rank = ["pending", "sent", "delivered", "read"]
                if new == "failed" or (new in rank and (m.status not in rank or rank.index(new) > rank.index(m.status))):
                    m.status = new
                if st.get("errors"):
                    e = st["errors"][0]
                    m.error = META_ERRORS.get(e.get("code"), f"Meta error {e.get('code')}: {e.get('title') or e.get('message')}")
                m.updated_at = datetime.now()
                n += 1
            for msg in v.get("messages", []):  # an NGO replied: the 24-hour window is now open
                if db.query(WhatsAppMessage.id).filter_by(provider_id=msg.get("id")).first():
                    continue
                text = (msg.get("text") or {}).get("body") or f"[{msg.get('type', 'message')}]"
                now = datetime.now()
                db.add(WhatsAppMessage(direction="in", provider="meta", kind="reply", phone=msg.get("from", ""), body=text,
                                       status="received", provider_id=msg.get("id"), created_at=now, updated_at=now))
                n += 1
    db.commit()
    return n


def twilio_signature_ok(c: WhatsAppConfig, url: str, params: dict, header: str | None) -> bool:
    if not c.twilio_token or not header:
        return False
    data = url + "".join(k + params[k] for k in sorted(params))
    expected = base64.b64encode(hmac.new(c.twilio_token.encode(), data.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(expected, header)


def handle_twilio_status(db: Session, params: dict) -> None:
    m = db.query(WhatsAppMessage).filter_by(provider_id=params.get("MessageSid")).first()
    if m:
        m.status = TWILIO_STATUS.get(params.get("MessageStatus"), m.status)
        if params.get("ErrorCode"):
            code = int(params["ErrorCode"]) if params["ErrorCode"].isdigit() else params["ErrorCode"]
            m.error = TWILIO_ERRORS.get(code, f"Twilio error {code}")
        m.updated_at = datetime.now()
        db.commit()
