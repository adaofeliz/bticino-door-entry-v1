# Learnings
- Scaffolded a BTicino Door Entry v1 custom integration with the required azure auth constants, API keys, device types, and update manifest/`__init__.py` stubs.
- Platform list is intentionally limited to LOCK, LIGHT, and SENSOR per instructions, so this component stays compliant with HA expectations.
- Verification requires the `homeassistant` package, so I installed it inside a temporary `.venv` to run the provided python assertions.

- Added pytest/coverage config, requirements_test, and HA fixtures; verified pip install, pytest, and pytest_homeassistant_custom_component import.
## Task 5: auth.py — Azure B2C PKCE headless scrape (2026-06-05)

### PKCE flow confirmed working
4-step flow: GET authorize → POST SelfAsserted → GET confirmed (302 no-follow) → POST token

### SETTINGS block parsing
Regex patterns that work against real B2C HTML:
- csrf: `r'"csrf":"([^"]+)"'`
- transId: `r'"transId":"([^"]+)"'`
- tenant path: `r'"hosts"\s*:\s*\{"tenant"\s*:\s*"([^"]+)"'`

### URL construction
- Authorize: `{B2C_BASE}/{B2C_TENANT}/oauth2/v2.0/authorize?p={B2C_POLICY}&...`
- SelfAsserted: `{B2C_BASE}{tenant_path}/SelfAsserted` (tenant_path from SETTINGS has leading slash)
- Confirmed: `{B2C_BASE}{tenant_path}/api/CombinedSigninAndSignup/confirmed`
- Token: `{B2C_BASE}/{B2C_TENANT}/oauth2/v2.0/token?p={B2C_POLICY}`

### aioresponses compatibility
`aioresponses` 0.7.8 correctly intercepts `allow_redirects=False` GET requests — 302 response headers are accessible.

### Token caching
`_REFRESH_BUFFER = 300` — refresh 5 min before expiry. Double-checked locking with asyncio.Lock.

### b2c_authorize_no_csrf.html fixture
Already existed with `"csrf_REMOVED":"intentionally_absent"` — regex `r'"csrf":"([^"]+)"'` does not match it.

- Added tests/test_entity.py to codify BticinoV1Entity expectations (unique_id base, device_info identifiers, firmware version) before implementation.
- Implemented custom_components/bticino_v1/entity.py so DeviceInfo anchors to the gateway and mirrors gateway firmware sw_version for all subclassed entities.

## Task 9: Config Flow (2026-06-05)

### pytest-homeassistant-custom-component Discovery Fix
`async_test_home_assistant` pre-sets `hass.data[loader.DATA_CUSTOM_COMPONENTS] = {}` which BLOCKS custom integration loading. The `enable_custom_integrations` fixture pops this key to force re-scan. Required pattern for config flow tests:
```python
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    pass
```
Add to each test module (not global conftest, to avoid slowing unrelated tests).

### OptionsFlow.config_entry Property (HA 2024.x)
`config_entries.OptionsFlow` now has `config_entry` as a **read-only property** that retrieves the entry via `self.hass.config_entries.async_get_known_entry(self._config_entry_id)`. Do NOT store it in `__init__`. Use `self.config_entry` directly in step methods.

### Config Flow Data/Options Split
- `data`: credentials + identifiers (`username`, `password`, `home_id`, `gateway_id`)
- `options`: user preferences (`light_as_lock: bool`)
- `async_create_entry(title=..., data={...}, options={...})` sets both simultaneously

### Gateway ID Discovery in `init_options`
Get gateway_id by calling `api.get_modules(home_id)` and finding the module with `device=="gateway"`. Done during `async_step_init_options` (after user submits options), not during `async_step_user` (to avoid extra API calls on error paths).

### Reauth Pattern
- `async_step_reauth` just forwards to `async_step_reauth_confirm`
- `async_step_reauth_confirm` uses `self.context["entry_id"]` to get the entry, updates it with new password, returns `async_abort(reason="reauth_successful")`
- No need to call `async_reload` (avoids `async_setup_entry`/`async_unload_entry` requirements)

## Task 11: Lock entity (2026-06-05)

- Adopted red/green discipline: wrote pytest scenarios for module filtering, unique IDs, optimistic unlock, relock scheduling, availability, and API-error resilience before touching production code.
- Implemented `custom_components/bticino_v1/lock.py`, filtering coordinator modules for `DEVICE_TYPE_LOCK`, exposing `LockEntityFeature.OPEN`, optimistic state changes, relock timer via `async_call_later`, and cleanup hooks.

## Task 12: Light entity (2026-06-05)

- Added `tests/test_light.py` to codify async_setup_entry filtering, the `light_as_lock` option, and that BticinoV1Light/BticinoV1LightAsLock call `coordinator.async_set_light` (and async_unlock relock timer) before writing production code.
- Implemented `custom_components/bticino_v1/light.py` with async_setup_entry, BticinoV1Light, and BticinoV1LightAsLock mirroring the lock relock pattern while using `async_set_light`, keeping attributes consistent with the Coordinator data.
- Task 13 sensors (2026-06-05)

- Wrote red-phase regression tests for firmware, IP, and connection sensors plus async_setup_entry unavailability guard before adding production code.
- Implemented `custom_components/bticino_v1/sensor.py` with `_GatewaySensor` base that reads the configured gateway field, exposes DIAGNOSTIC EntityCategory, and adds `async_setup_entry` guard conditions for missing gateway data.
- Verified `/tmp/ha_verify_venv/bin/pytest tests/test_sensor.py -v` passes despite the repo lacking `homeassistant` in the default env by running against the provided HA virtualenv.

## Code quality review - 2026-06-05
- Verification passed: 79 tests, auth coverage 90%, api coverage 85%, total coverage 90%.
- Integration uses aiohttp in auth.py and api.py; no requests, fixed PKCE vectors, or firebase_admin references found.
- manifest.json includes required HA metadata and iot_class is cloud_polling; APK artifacts are gitignored via apk/ and *.xapk.

- Scope fidelity review: integration files present are HA platforms light/lock/sensor only; manifest iot_class is cloud_polling; auth.py uses secrets.token_urlsafe for fresh PKCE. README grep for ring/doorbell/fcm has semantic matches only in Known limitations/Roadmap, but substring grep also matches words like during/engineering.
