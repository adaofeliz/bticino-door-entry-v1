# BTicino Door Entry v1

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/adaofeliz/bticino-door-entry-v1)](https://github.com/adaofeliz/bticino-door-entry-v1/releases/latest)
[![GitHub Issues](https://img.shields.io/github/issues/adaofeliz/bticino-door-entry-v1)](https://github.com/adaofeliz/bticino-door-entry-v1/issues)
[![License](https://img.shields.io/github/license/adaofeliz/bticino-door-entry-v1)](LICENSE)

A Home Assistant custom integration for **BTicino CLASSE100X** intercoms running **v1 firmware** — the same devices that pair with the old **"Door Entry CLASSE100X"** Android app.

> [!IMPORTANT]
> This integration targets **v1 firmware only**. If your intercom uses the newer **"Home + Security"** app (Netatmo platform), use [`bticino_intercom`](https://github.com/k-the-hidden-hero/bticino_intercom) instead.

[![Add Repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=adaofeliz&repository=bticino-door-entry-v1&category=integration)
[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=bticino_v1)

---

## What it does

- **Open door locks** through the Legrand Eliot cloud
- **Toggle the staircase light** relay
- **Gateway diagnostics** — firmware version, IP address, connection state

---

## Prerequisites

> **Prerequisites:** Your intercom must already be commissioned and working with the old **"Door Entry CLASSE100X"** Android app. If you can sign into that app and open your door, you're ready.

- Home Assistant `2024.1.0` or newer
- A BTicino CLASSE100X on **v1 firmware**
- A **Legrand Eliot** account (same email + password as the old app)
- `curl` available on the Home Assistant host (used for authentication)

---

## Installation

### HACS (recommended)

Click the **Add Repository** button above to open HACS directly, or add it manually:

1. Open **HACS** in Home Assistant
2. Go to **Integrations** → click the three-dot menu → **Custom repositories**
3. Paste `https://github.com/adaofeliz/bticino-door-entry-v1` as an **Integration**
4. Search for **"BTicino Door Entry v1"** and install
5. **Restart Home Assistant**

### Manual

1. Copy `custom_components/bticino_v1/` into `<config>/custom_components/`
2. Restart Home Assistant

---

## Configuration

Click the **Add Integration** button above, or go to **Settings → Devices & Services → Add Integration** and search for **BTicino Door Entry v1**.

| Field | What it is |
|-------|------------|
| **Email** | Your Legrand Eliot account email |
| **Password** | Your Legrand Eliot password |
| **Home** | If you have multiple homes, pick the right one |
| `light_as_lock` | Optional — exposes the staircase light as a lock entity |

Credentials are stored in the standard Home Assistant config entry store.

---

## Entities created

| Entity | Description |
|--------|-------------|
| `lock.*` | One per door — momentary "unlock" with automatic relock after 5 seconds |
| `light.*` | Staircase light relay (or a lock if `light_as_lock` is enabled) |
| `sensor.*_firmware` | Gateway firmware version |
| `sensor.*_ip_address` | Gateway local IP address |
| `sensor.*_connection_state` | Gateway connection state (CONNECTED / offline) |

---

## Known limitations

- **No ring/doorbell detection in v1.0.0.** Ring events on v1 firmware are delivered via Firebase Cloud Messaging (FCM) to the mobile app. Server-side FCM reception is planned for v1.1.0.
- **No video or audio.** The integration does not tap the SIP stream.
- **Cloud polling only.** Module state refreshes every 5 minutes. Door open commands are immediate REST calls.

If you need ring notifications today, keep the official app installed on a phone for alerts and use this integration for door open and light actions.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| **"Invalid auth"** | Wrong email or password | Sign into the old "Door Entry CLASSE100X" Android app to confirm your credentials work |
| **"Cannot connect"** | Legrand Eliot cloud unreachable, or `curl` missing from HA host | Check `https://api.developer.legrand.com` is reachable; ensure `curl` is installed |
| **No devices show up** | Wrong home selected, or no v1 firmware devices on account | Verify in the old Android app that your device appears |
| **Door entity "Unavailable"** | Gateway is offline | Check the gateway connection-state sensor; power-cycle the intercom |
| **`lock.unlock` fires but door doesn't open** | Token expired or gateway lost cloud link | Reload the integration; check the integration debug log |
| **"Home + Security app works but this doesn't"** | You're on the newer Netatmo firmware | Use [`bticino_intercom`](https://github.com/k-the-hidden-hero/bticino_intercom) instead |

Enable debug logging:

```yaml
logger:
  default: info
  logs:
    custom_components.bticino_v1: debug
```

---

## Roadmap

- **v1.1.0** — Ring event detection via Firebase Cloud Messaging (FCM listener + momentary binary sensor per door station).
- **Future** — Better multi-home support, longer-running session reuse, `button.press` entity for door-open automations.

No promises on video or audio. That's a much larger lift and isn't on the near-term plan.

---

## Credits

- Reverse engineering inspired by [`bticino_intercom`](https://github.com/k-the-hidden-hero/bticino_intercom) by [@k-the-hidden-hero](https://github.com/k-the-hidden-hero), which targets the newer Netatmo platform.
- Legrand Eliot cloud is property of Legrand. This is an unofficial, community-built integration.

---

## License

MIT — see [LICENSE](LICENSE) in this repository.
