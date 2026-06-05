# BTicino Door Entry v1

A Home Assistant custom integration for **BTicino CLASSE100X** intercoms running **v1 firmware**, the same devices that pair with the old **"Door Entry CLASSE100X"** Android app.

> [!IMPORTANT]
> This integration targets v1 firmware only. If your intercom uses the newer **"Home + Security"** app (Netatmo platform), this is the wrong integration. Use [`bticino_intercom`](https://github.com/k-the-hidden-hero/bticino_intercom) instead.

## What it does

- Opens door locks through the Legrand Eliot cloud
- Toggles the staircase light relay
- Reports gateway diagnostics: firmware version, IP address, connection state

## Prerequisites

- Home Assistant `2024.1.0` or newer
- A BTicino CLASSE100X intercom on **v1 firmware**
- A working **Legrand Eliot** account (the same email and password you use with the old "Door Entry CLASSE100X" app)
- The device must already be commissioned and online in the Eliot cloud

If you can sign into the old Android app and open your door from it, you're ready.

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click the three dots, top right, then **Custom repositories**
4. Add `https://github.com/adaofeliz/bticino-door-entry-v1` as an **Integration**
5. Search for **"BTicino Door Entry v1"** and install
6. Restart Home Assistant

### Manual

1. Copy `custom_components/bticino_v1/` into your `<config>/custom_components/` folder
2. Restart Home Assistant

## Configuration

After install, go to **Settings → Devices & Services → Add Integration** and search for **BTicino Door Entry v1**.

You'll be asked for:

| Field | What it is |
|-------|------------|
| Email | Your Legrand Eliot account email |
| Password | Your Legrand Eliot password |
| Home | If your account has multiple homes, pick the one you want to expose |
| `light_as_lock` | Optional. Exposes the staircase light as a lock entity instead of a light. Handy if you want the same UI affordance as door locks. |

Credentials never leave Home Assistant. They're stored in the standard config entry store.

## Entities created

For each home you configure:

- **Lock**, one per door, one entry per physical door the gateway knows about. Locks are momentary, they "unlock" and auto-relock after the relay pulse.
- **Light**, one entity for the staircase light relay (or a lock, if `light_as_lock` is enabled)
- **Sensors**, gateway diagnostics:
  - Firmware version
  - Local IP address
  - Connection state (online / offline)

## Known limitations

- **No ring/doorbell detection in v1.0.0.** Incoming call events on v1 firmware are delivered via Firebase Cloud Messaging to the mobile app. Catching them server-side needs more work and is planned for v1.1.0.
- **No video.** The integration doesn't tap the SIP stream.
- **No audio.** Same reason.
- **No two-way intercom.** You can't talk through Home Assistant.
- Cloud polling only. Door state and gateway state refresh on a fixed interval. Door open is a direct REST call, so that part is immediate.

If you need ring events today, keep the official app installed on a phone for notifications and use this integration for the door open and light actions.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| "Invalid auth" during setup | Wrong email or password | Sign into the old "Door Entry CLASSE100X" Android app with the same credentials to confirm they work |
| "Cannot connect" during setup | Legrand Eliot cloud unreachable, or your network blocks it | Check `https://api.developer.legrand.com` is reachable from your HA host |
| Setup works but no devices show up | Your account has no v1 firmware devices, or you picked the wrong home | Confirm in the old Android app that you see the device. If you have multiple homes, re-run setup and pick the right one |
| Door entity says "Unavailable" | Gateway is offline | Check the gateway sensor for connection state. Power-cycle the intercom if it stays offline |
| `lock.unlock` fires but the door doesn't open | Token expired, gateway lost cloud link, or relay-side fault | Look at the integration log. Tokens auto-refresh, but a stale entry can cause this. Reload the integration |
| "Home + Security app works but this doesn't" | You're on the newer firmware/platform | This integration won't work for you. Use [`bticino_intercom`](https://github.com/k-the-hidden-hero/bticino_intercom) |

Enable debug logging for deeper diagnostics:

```yaml
logger:
  default: info
  logs:
    custom_components.bticino_v1: debug
```

## Roadmap

- **v1.1.0**, ring event detection via Firebase Cloud Messaging. The plan is to register a FCM listener against the same project the mobile app uses, expose ring as a HA event plus a momentary binary sensor per door station.
- Beyond that: better multi-home support, longer-running session reuse, and possibly a `button.press` entity for the door-open action so it can be wired into automations that don't want a lock.

No promises on video or audio. That's a much bigger lift and isn't on the near-term plan.

## Credits

- Reverse engineering inspired by [`bticino_intercom`](https://github.com/k-the-hidden-hero/bticino_intercom) by [@k-the-hidden-hero](https://github.com/k-the-hidden-hero), even though that integration targets the newer Netatmo-based platform.
- Legrand Eliot cloud is property of Legrand. This is an unofficial, community-built integration.

## License

See [LICENSE](LICENSE) in this repository.
