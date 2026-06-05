# BTicino CLASSE100X PoC

Proof-of-concept for authenticating and opening a door on legacy **Door Entry CLASSE100X v1**
devices (old "Door Entry CLASSE100X" Android app, **not** the newer "Home + Security" / Netatmo app).

## How it works

```
Email + Password
      │
      ▼  Azure B2C ROPC
      │  POST eliotclouduamprd.b2clogin.com/.../token?p=B2C_1_DoorEliot-C100X-SignUporSignIn
      │
      ▼  access_token
      │
      ├─ GET /servicecatalog/api/v3.0/plants              → list homes
      ├─ GET /servicecatalog/api/v3.0/plants/{id}/modules → list devices
      ├─ GET /vde/sip/v1.0/devices/{id}/sipaccounts       → SIP credentials
      │
      ├─ (REST path)  POST /vdeproducts/v1.0/lock/.../ticket  → open door
      └─ (SIP path)   REGISTER + MESSAGE lock.setStatus=open  → open door
```

All constants (Azure B2C client ID, tenant, API base, SIP host) were extracted
from the decompiled APK `com.legrandgroup.c100x v1.8.2`.

## Setup

```bash
cd bticinio-door-entry/
pip install -r poc/requirements.txt
```

## Run

```bash
# Interactive (prompts for email + password)
python poc/poc.py

# List plants and modules only, no door open
python poc/poc.py --list

# Use SIP MESSAGE path instead of REST
python poc/poc.py --sip

# Non-interactive
BTI_EMAIL=you@example.com BTI_PASSWORD=secret python poc/poc.py

# Verbose debug
python poc/poc.py --debug --list
```

## Files

| File | Purpose |
|------|---------|
| `auth.py` | Azure B2C ROPC auth, token refresh |
| `legrand_api.py` | Legrand REST API (plants, modules, SIP accounts, open lock) |
| `sip_client.py` | Minimal SIP/TLS client (REGISTER + MESSAGE + INVITE detection) |
| `poc.py` | CLI entry point |

## What to expect

1. **Auth succeeds** — `Authenticated as you@example.com ✓`
2. **Plants listed** — your home name and ID
3. **Modules listed** — your intercom device and its raw data
4. **SIP accounts** — `sipUri` and (masked) `sipPassword` for your device
5. **Door open** — REST attempt first; use `--sip` for the SIP MESSAGE path

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| `invalid_grant` on auth | Wrong password, or account not linked to v1 firmware app |
| `get_plants` 404 | Token scope mismatch — the v2 API may be fully removed |
| `open_lock` 404 | REST lock endpoint deprecated; use `--sip` instead |
| SIP registration timeout | Port 5228 blocked outbound, or `sipUri` domain incorrect |
