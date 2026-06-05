"""
mitmproxy addon — captures BTicino app traffic.

Run with:
  mitmdump -p 8080 -s poc/intercept.py

Captures:
  - All legrand / iotleg / firebase / google traffic
  - Logs FCM tokens, auth tokens, door commands, push registrations
"""
import json
import re
from datetime import datetime
from mitmproxy import http

LOG = "/tmp/bticino_intercept.jsonl"

INTERESTING = (
    "legrand", "iotleg", "b2clogin", "firebase", "fcm",
    "googleapis", "bticino", "eliot", "netatmo",
)

def _ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def _log(entry: dict):
    with open(LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    # Also print highlights to terminal
    kind = entry.get("kind", "")
    print(f"\n{'='*60}")
    print(f"[{entry['ts']}] {kind}")
    print(f"  {entry.get('method','')} {entry.get('url','')}")
    if entry.get("req_body"):
        print(f"  REQ: {entry['req_body'][:300]}")
    if entry.get("status"):
        print(f"  HTTP {entry['status']}")
    if entry.get("resp_body"):
        print(f"  RESP: {entry['resp_body'][:400]}")
    print(f"{'='*60}")


def request(flow: http.HTTPFlow):
    url = flow.request.pretty_url
    if not any(x in url for x in INTERESTING):
        return

    body = flow.request.get_text(strict=False) or ""
    headers = dict(flow.request.headers)

    entry = {
        "ts": _ts(),
        "kind": "REQUEST",
        "method": flow.request.method,
        "url": url,
        "req_body": body[:800],
    }

    # Highlight specific things we're looking for
    if "vde/push" in url:
        entry["kind"] = "🔔 PUSH_REGISTRATION"
    elif "fcmregistration" in url.lower() or "fcm/token" in url.lower():
        entry["kind"] = "🔑 FCM_TOKEN_REQUEST"
    elif "oauth2/token" in url or "SelfAsserted" in url:
        entry["kind"] = "🔐 AUTH"
    elif "commands" in url or "lock" in url or "open" in url:
        entry["kind"] = "🚪 DOOR_COMMAND"
    elif "sipaccounts" in url:
        entry["kind"] = "📞 SIP_ACCOUNTS"
    elif "googleapis.com/fcm" in url:
        entry["kind"] = "📬 FCM_SEND"

    # Extract FCM token from body if present
    if body:
        for pattern in [r'"token"\s*:\s*"([^"]{20,})"',
                        r'"registration_token"\s*:\s*"([^"]{20,})"',
                        r'registration_token=([^&\s]{20,})',
                        r'"fcmToken"\s*:\s*"([^"]{20,})"',
                        r'"gcmToken"\s*:\s*"([^"]{20,})"',
                        r'"pushToken"\s*:\s*"([^"]{20,})"']:
            m = re.search(pattern, body)
            if m:
                entry["FCM_TOKEN"] = m.group(1)
                entry["kind"] += " ⭐ FCM_TOKEN_FOUND"
                break

    _log(entry)


def response(flow: http.HTTPFlow):
    url = flow.request.pretty_url
    if not any(x in url for x in INTERESTING):
        return

    body = flow.response.get_text(strict=False) or ""

    entry = {
        "ts": _ts(),
        "kind": "RESPONSE",
        "method": flow.request.method,
        "url": url,
        "status": flow.response.status_code,
        "resp_body": body[:800],
    }

    if "vde/push" in url:
        entry["kind"] = "🔔 PUSH_REG_RESPONSE"
    elif "sipaccounts" in url:
        entry["kind"] = "📞 SIP_ACCOUNTS_RESP"
    elif "oauth2/token" in url:
        entry["kind"] = "🔐 TOKEN_RESP"
        # Scrub passwords but keep token shape
        try:
            d = json.loads(body)
            entry["resp_body"] = json.dumps({
                k: (v[:20]+"..." if k in ("access_token","refresh_token","id_token") and v else v)
                for k,v in d.items()
            })
        except:
            pass

    # Look for FCM token in response too
    if body:
        for pattern in [r'"token"\s*:\s*"([^"]{20,})"',
                        r'"name"\s*:\s*"projects/[^/]+/registrations/([^"]{20,})"']:
            m = re.search(pattern, body)
            if m:
                entry["FCM_TOKEN"] = m.group(1)
                entry["kind"] += " ⭐ FCM_TOKEN_IN_RESP"
                break

    _log(entry)
