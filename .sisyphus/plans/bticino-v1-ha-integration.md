# BTicino Door Entry v1 — Home Assistant Integration

## TL;DR

> **Quick Summary**: Home Assistant HACS custom integration for BTicino CLASSE100X v1 firmware devices (old "Door Entry CLASSE100X" Android app). Email+password auth, door lock control, staircase light, gateway diagnostics. Ring events deferred to v1.1.0 pending FCM client research.
>
> **Deliverables**:
> - `custom_components/bticino_v1/` — complete HA integration
> - `tests/` — full TDD test suite (≥85% coverage on auth/api, ≥70% overall)
> - `hacs.json` + `README.md` — HACS-publishable repository
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES — 4 waves
> **Critical Path**: auth.py → api.py → coordinator.py → entity.py → lock.py → config_flow.py → __init__.py → HACS

---

## Context

### Original Request
Build a HACS HA custom integration for BTicino CLASSE100X v1 firmware, structured like `k-the-hidden-hero/bticino_intercom`, with email+password config and door open + ring event support.

### Interview Summary

**Key Discussions**:
- Auth: Azure B2C PKCE headless form-scraping (ROPC disabled). 4-step flow confirmed working via PoC.
- Door open: `POST /devicemanagement/api/v2.0/modules/{gatewayId}/commands` → `{"command":{"name":"open","moduleId":"{lockId}"}}` — physically confirmed working on A-Door, Gate, B-Door.
- Ring events: polling confirmed useless (zero API field changes on live doorbell ring). FCM is the only mechanism but firebase-admin cannot receive — deferred to v1.1.0.
- Scope: v1.0.0 = locks + light + gateway sensors. Ring detection = v1.1.0 separate cycle.

**Research Findings**:
- Reference integration (`bticino_intercom`) uses WebSocket + dispatcher pattern; we mirror structure but use polling coordinator only (no WebSocket in v1 system).
- Module types identified: `gateway`, `lock`, `audioVideoTerminal/EU`, `audioVideoTerminal/IU`, `light`.
- Required header on all API calls: `Ocp-Apim-Subscription-Key: f36968e522bf4ec3877fa491109d3d14`.

### Metis Review — Identified Gaps (addressed)

- **FCM architecture** (CRITICAL): firebase-admin is send-only. Deferred entirely to v1.1.0. → binary_sensor.py and event.py excluded from v1.0.0.
- **Fixed PKCE vectors**: Changed to generate fresh PKCE per scrape (no fixed test vectors).
- **Stale PoC auth.py**: Discard — it uses ROPC (failed). Rewrite from scratch using confirmed 4-step B2C flow.
- **Subscription key portability**: Validate with 2nd account before plan execution.
- **Diagnostics redaction**: Added explicit task for redacting password/tokens/key.
- **`iot_class`**: `cloud_polling` in v1.0.0 (not `cloud_push` — we have no push).

---

## Work Objectives

### Core Objective
A HACS-publishable HA integration that authenticates with Legrand Eliot (Azure B2C), discovers door locks and lights, and allows opening doors and controlling lights from HA — with full TDD test coverage and zero dependency on SIP/video/FCM.

### Concrete Deliverables
- `custom_components/bticino_v1/__init__.py` — entry lifecycle
- `custom_components/bticino_v1/auth.py` — B2C PKCE headless scrape + token persistence
- `custom_components/bticino_v1/api.py` — Legrand v1 REST client
- `custom_components/bticino_v1/coordinator.py` — 5-min polling DataUpdateCoordinator
- `custom_components/bticino_v1/config_flow.py` — email+pw+home-select+options
- `custom_components/bticino_v1/entity.py` — BticinoV1Entity base
- `custom_components/bticino_v1/lock.py` — BticinoV1Lock
- `custom_components/bticino_v1/light.py` — BticinoV1Light + BticinoV1LightAsLock
- `custom_components/bticino_v1/sensor.py` — gateway diagnostics sensors
- `custom_components/bticino_v1/diagnostics.py` — redacted config export
- `custom_components/bticino_v1/const.py`, `strings.json`, `translations/en.json`, `manifest.json`
- `tests/` — full test suite with golden fixtures
- `hacs.json`, `README.md`, `info.md`

### Definition of Done
- [ ] `pytest tests/ -x` passes, coverage ≥70% overall, ≥85% on auth.py and api.py
- [ ] `python -m script.hassfest --integration-path custom_components/bticino_v1` exits 0
- [ ] HACS validation action passes
- [ ] Integration loads in HA dev container without exceptions
- [ ] Lock entity `lock.unlock` → door physically opens (one-time human smoke test)

### Must Have
- B2C auth with fresh PKCE per scrape + asyncio.Lock + Store token persistence
- `Ocp-Apim-Subscription-Key` on every API call, overridable via advanced options
- One lock entity per `device: lock` module, optimistic relock after 5s
- One light entity per `device: light` module + `light_as_lock` option
- Gateway sensor (firmware, IP, connectionState)
- Config flow: email+pw → home selection (multi-plant) → init options
- Reauth flow
- Diagnostics with password/token/key redaction

### Must NOT Have (Guardrails)
- ❌ SIP client, RTP, camera entity, video/audio
- ❌ binary_sensor.py, event.py (ring detection deferred to v1.1.0)
- ❌ firebase-admin or any FCM listener code
- ❌ IU (audioVideoTerminal type IU) entities
- ❌ Multi-language translations (en.json only)
- ❌ Device pairing, firmware updates
- ❌ APK files committed to repo
- ❌ Fixed PKCE verifier/challenge pair (must be freshly generated)
- ❌ pybticino or pybticino_v1 as PyPI dependency (vendor everything)
- ❌ Translations beyond en.json
- ❌ `iot_class: cloud_push` (use `cloud_polling` — we have no push)

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: NO — set up in task 1
- **Automated tests**: YES (TDD — RED before GREEN on every task)
- **Framework**: pytest + pytest-homeassistant-custom-component + aioresponses
- **TDD**: Each task follows RED (failing test) → GREEN (minimal impl) → REFACTOR

### QA Policy
Every task includes agent-executed QA: exact `pytest` command + test ID + expected output. No "user verifies" ever.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 — Foundation (all parallel, no dependencies):
├── Task 1:  Scaffold + const.py + manifest.json + .gitignore [quick]
├── Task 2:  hacs.json + README.md + info.md [writing]
├── Task 3:  tests/ structure + conftest.py + HA harness [quick]
└── Task 4:  Golden fixtures (B2C HTML + API JSON captures) [quick]

Wave 2 — Core library (auth first, then api parallel):
├── Task 5:  auth.py — B2C PKCE scrape (TDD, 8 test pairs) [deep]
└── Task 6:  api.py — Legrand REST client (TDD, 6 test pairs) [unspecified-high]
    (Task 6 can start after task 5 AuthHandler interface is defined in task 5)

Wave 3 — Integration layer (all depend on tasks 5+6):
├── Task 7:  coordinator.py — BticinoV1Coordinator (TDD) [unspecified-high]
├── Task 8:  entity.py — BticinoV1Entity base (TDD) [quick]
├── Task 9:  config_flow.py — full config+options+reauth (TDD) [deep]
└── Task 10: __init__.py — entry lifecycle (TDD) [unspecified-high]
    (Tasks 7,8 can run parallel. Task 9 needs api.py. Task 10 needs 7,8,9.)

Wave 4 — Entity platforms + polish (all parallel after wave 3):
├── Task 11: lock.py — BticinoV1Lock (TDD) [quick]
├── Task 12: light.py — BticinoV1Light + LightAsLock (TDD) [quick]
├── Task 13: sensor.py — gateway sensors (TDD) [quick]
├── Task 14: diagnostics.py — redacted config export (TDD) [quick]
├── Task 15: strings.json + translations/en.json [writing]
└── Task 16: Final verification + HACS check + README polish [unspecified-high]

Critical Path: T1→T3→T4→T5→T6→T7→T8→T9→T10→T11→T16
```

### Dependency Matrix

| Task | Depends on | Blocks |
|------|-----------|--------|
| 1 | — | 3,5,6,7,8,9,10,11,12,13,14 |
| 2 | — | 16 |
| 3 | 1 | 5,6,7,8,9,10,11,12,13,14 |
| 4 | 1 | 5,6 |
| 5 | 3,4 | 6,7,9,10 |
| 6 | 3,4,5(interface) | 7,9,10 |
| 7 | 5,6,3 | 10,11,12,13 |
| 8 | 1,3 | 10,11,12,13 |
| 9 | 5,6,3 | 10 |
| 10 | 7,8,9 | 16 |
| 11 | 7,8,3 | 16 |
| 12 | 7,8,3 | 16 |
| 13 | 7,8,3 | 16 |
| 14 | 7,8,3 | 16 |
| 15 | 1 | 16 |
| 16 | all | — |

---

## TODOs

- [x] 1. Scaffold: project skeleton, const.py, manifest.json, .gitignore

  **What to do**:
  - Create `custom_components/bticino_v1/` directory with `__init__.py` (empty stub)
  - `const.py`: DOMAIN="bticino_v1", PLATFORMS=[LOCK, LIGHT, SENSOR], all string constants (signal names, data keys, timing constants matching bticino_intercom pattern), module type strings (DEVICE_TYPE_GATEWAY="gateway", DEVICE_TYPE_LOCK="lock", DEVICE_TYPE_LIGHT="light", DEVICE_TYPE_EU="audioVideoTerminal", MODULE_SUBTYPE_EU="EU"), UPDATE_INTERVAL=5, LOCK_RELOCK_DELAY=5, APIM_SUBSCRIPTION_KEY="f36968e522bf4ec3877fa491109d3d14"
  - `manifest.json`: domain, name="BTicino Door Entry v1", version="1.0.0", config_flow=true, iot_class="cloud_polling", requirements=[], codeowners=["@adaofeliz"], documentation, issue_tracker
  - `.gitignore` at repo root: apk/, *.xapk, *.apk, .env, __pycache__, *.pyc, .sisyphus/evidence/

  **Must NOT do**:
  - No binary_sensor, event, camera platforms in PLATFORMS list
  - No pybticino requirement
  - No iot_class: cloud_push
  - No APIM key hardcoded in manifest (only in const.py)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 1)
  - **Parallel Group**: Wave 1 with Tasks 2, 3, 4
  - **Blocks**: Tasks 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
  - **Blocked By**: None

  **References**:
  - `k-the-hidden-hero/bticino_intercom/custom_components/bticino_intercom/const.py` — exact constant naming pattern to mirror
  - `k-the-hidden-hero/bticino_intercom/custom_components/bticino_intercom/manifest.json` — manifest structure

  **Acceptance Criteria**:
  - [ ] `python -c "from custom_components.bticino_v1.const import DOMAIN; assert DOMAIN == 'bticino_v1'"` passes
  - [ ] `python -c "import json; m=json.load(open('custom_components/bticino_v1/manifest.json')); assert m['iot_class']=='cloud_polling'"` passes
  - [ ] `grep -r 'binary_sensor\|camera\|cloud_push\|pybticino' custom_components/bticino_v1/manifest.json` returns nothing
  - [ ] `.gitignore` contains `apk/` entry

  **Commit**: `chore(scaffold): create bticino_v1 skeleton, const.py, manifest.json, .gitignore`

- [x] 2. HACS packaging: hacs.json, README.md, info.md

  **What to do**:
  - `hacs.json`: name, render_readme=true, homeassistant minimum version
  - `README.md`: what it is, what it does, prerequisites (v1 firmware only — NOT Home+Security app), installation (HACS), configuration steps, known limitations (ring events v1.1.0), troubleshooting table
  - `info.md`: short HACS description card

  **Must NOT do**:
  - Don't promise ring detection or FCM in v1.0.0 README
  - Don't mention SIP, video, audio

  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 1)
  - **Parallel Group**: Wave 1 with Tasks 1, 3, 4
  - **Blocks**: Task 16
  - **Blocked By**: None

  **Acceptance Criteria**:
  - [ ] `python -c "import json; json.load(open('hacs.json'))"` passes (valid JSON)
  - [ ] `wc -l README.md | awk '{print $1}'` > 50 (non-trivial README)
  - [ ] `grep -i 'ring\|doorbell\|fcm\|sip\|video\|audio' README.md` — only appears in "Known Limitations" or "Roadmap" sections

  **Commit**: `chore(hacs): add hacs.json, README.md, info.md`

- [x] 3. Test infrastructure: tests/ structure, conftest.py, HA harness

  **What to do**:
  - `tests/__init__.py`, `tests/conftest.py` with HA harness fixtures (hass, config_entry, mock_coordinator)
  - `pyproject.toml` or `setup.cfg`: pytest config, aioresponses, pytest-homeassistant-custom-component
  - `tests/fixtures/` directory (empty, populated in task 4)
  - Confirm pytest runs: `pytest tests/ -x` → "no tests ran" exit 0

  **Must NOT do**:
  - No real API calls in conftest
  - Don't add actual test files yet (task 5+ does that)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 1)
  - **Parallel Group**: Wave 1 with Tasks 1, 2, 4
  - **Blocks**: Tasks 5–14
  - **Blocked By**: Task 1 (needs const.py DOMAIN)

  **References**:
  - `k-the-hidden-hero/bticino_intercom/tests/` — pytest-homeassistant-custom-component pattern

  **Acceptance Criteria**:
  - [ ] `pytest tests/ -x` exits 0 (0 collected is fine)
  - [ ] `python -c "import pytest_homeassistant_custom_component"` passes

  **Commit**: `chore(tests): add test infrastructure, conftest.py, HA harness`

- [x] 4. Golden test fixtures: real B2C HTML + API JSON responses

  **What to do**:
  - `tests/fixtures/b2c_authorize.html` — real authorize page HTML with SETTINGS JS block (csrf, transId, tenant, api values — use values from PoC session, anonymise if needed)
  - `tests/fixtures/b2c_authorize_no_csrf.html` — same but with csrf field removed (for error path testing)
  - `tests/fixtures/b2c_selfasserted_success.json` — `{"status":"200"}`
  - `tests/fixtures/b2c_selfasserted_failure.json` — `{"status":"400","message":"Missing required element..."}`
  - `tests/fixtures/b2c_tokens.json` — real token response shape (access_token, refresh_token, expires_in — anonymized values ok, shape must match)
  - `tests/fixtures/plants.json` — real plants response (can use anonymized plant name, keep structure)
  - `tests/fixtures/modules.json` — real modules response with all module types (gateway, lock×3, light, audioVideoTerminal/EU×2, audioVideoTerminal/IU)
  - `tests/fixtures/open_lock_200.json` — `{}` (empty body 200)

  **Must NOT do**:
  - Don't use fabricated HTML — use real captured B2C page structure
  - Don't include real passwords or tokens in fixtures (anonymize)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 1)
  - **Parallel Group**: Wave 1 with Tasks 1, 2, 3
  - **Blocks**: Tasks 5, 6
  - **Blocked By**: Task 1

  **Acceptance Criteria**:
  - [ ] `python -c "import json; json.load(open('tests/fixtures/plants.json'))"` passes
  - [ ] `python -c "import json; json.load(open('tests/fixtures/modules.json'))"` passes
  - [ ] `python -c "from bs4 import BeautifulSoup; html=open('tests/fixtures/b2c_authorize.html').read(); import re; assert re.search(r'\"csrf\":\"', html)"` passes
  - [ ] `grep -r 'real_password\|real_token\|adaofeliz\|Viana Pinto' tests/fixtures/` returns nothing (anonymized)

  **Commit**: `chore(fixtures): add golden test fixtures for B2C and API responses`

- [x] 5. auth.py — B2C PKCE headless scrape with full TDD

  **What to do**:
  - Write `tests/test_auth.py` FIRST (RED), then implement `custom_components/bticino_v1/auth.py` (GREEN)
  - `AuthHandler(username, password, session=None, token_callback=None)`
  - Methods: `authenticate()`, `get_access_token()`, `close()`, `set_tokens(access_token, refresh_token, expires_at)`
  - Internal: `_scrape_authorize()` → GET B2C page, extract csrf+transId+tenant using regex on embedded `SETTINGS = {...}` JS block
  - `_post_selfasserted(csrf, trans_id, tenant)` → POST logonIdentifier+password with X-CSRF-TOKEN header
  - `_get_auth_code(csrf, trans_id, tenant)` → GET confirmed, extract code from Location header
  - `_exchange_code(code)` → POST token endpoint with fresh PKCE verifier+challenge
  - `_refresh_token()` → use refresh_token if available, else re-scrape
  - PKCE: generate fresh `secrets.token_urlsafe(32)` as verifier, SHA256 base64url as challenge — NEVER hardcoded
  - `asyncio.Lock` around full scrape to prevent concurrent scrapes
  - On parse failure: raise `AuthError` with `last_html` attribute containing raw HTML
  - Android User-Agent: `NetatmoApp(DoorEntry/v1.8.2) Android(13/Google/sdk_gphone64_arm64)`
  - All requests async via aiohttp
  - Tests to write (all against golden fixtures, all mocked):
    - `test_authenticate_success_returns_access_token`
    - `test_authenticate_extracts_csrf_from_settings_block`
    - `test_authenticate_posts_logon_identifier_and_password`
    - `test_authenticate_includes_x_csrf_token_header`
    - `test_authenticate_invalid_credentials_raises_auth_error`
    - `test_authenticate_missing_csrf_raises_auth_error_with_last_html`
    - `test_get_access_token_returns_cached_if_not_expired`
    - `test_get_access_token_refreshes_on_expiry`
    - `test_get_access_token_rescapes_if_no_refresh_token`
    - `test_pkce_verifier_freshly_generated_per_call`
    - `test_concurrent_calls_share_single_scrape_via_lock`
    - `test_token_callback_called_on_authenticate`
    - `test_set_tokens_restores_session`
    - `test_android_user_agent_in_requests`

  **Must NOT do**:
  - No ROPC (`grant_type=password`) — that failed
  - No hardcoded PKCE verifier
  - No `requests` library (aiohttp only)
  - No retry on 4xx auth errors

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO — must complete before task 6 (api.py needs AuthHandler interface)
  - **Parallel Group**: Sequential after Wave 1
  - **Blocks**: Tasks 6, 7, 9, 10
  - **Blocked By**: Tasks 1, 3, 4

  **References**:
  - PoC session curl commands (4-step B2C flow) — confirmed working:
    1. GET `https://eliotclouduamprd.b2clogin.com/EliotClouduamprd.onmicrosoft.com/oauth2/v2.0/authorize?p=B2C_1_DoorEliot-C100X-SignUporSignIn&client_id=7d11af71-ab98-4832-aa62-6b00bff3bcc8&response_type=code&scope=openid%20offline_access%20https%3A%2F%2FEliotClouduamprd.onmicrosoft.com%2Fsecurity%2Faccess.full&redirect_uri=com.legrandgroup.c100x%3A%2F%2Foauth2redirect&code_challenge=<fresh>&code_challenge_method=S256&state=<random>`
    2. POST `https://eliotclouduamprd.b2clogin.com{tenant}/SelfAsserted?tx={transId}&p=B2C_1_DoorEliot-C100X-SignUporSignIn` with `X-CSRF-TOKEN: {csrf}`, body: `request_type=RESPONSE&logonIdentifier={email}&password={password}`
    3. GET `https://eliotclouduamprd.b2clogin.com{tenant}/api/CombinedSigninAndSignup/confirmed?csrf_token={csrf}&tx={transId}&p=B2C_1_DoorEliot-C100X-SignUporSignIn` — don't follow redirect, extract `code` from Location header
    4. POST `https://eliotclouduamprd.b2clogin.com/EliotClouduamprd.onmicrosoft.com/oauth2/v2.0/token?p=B2C_1_DoorEliot-C100X-SignUporSignIn` with code + code_verifier + redirect_uri
  - `k-the-hidden-hero/pybticino/auth.py` — token lifecycle patterns to mirror
  - `tests/fixtures/b2c_authorize.html` — golden fixture for parsing tests

  **QA Scenarios**:
  ```
  Scenario: Happy path auth
    Tool: pytest
    Command: pytest tests/test_auth.py::test_authenticate_success_returns_access_token -v
    Expected: PASSED, access_token matches pattern ^eyJ
    Evidence: .sisyphus/evidence/task-5-auth-happy.txt

  Scenario: Missing CSRF field
    Tool: pytest
    Command: pytest tests/test_auth.py::test_authenticate_missing_csrf_raises_auth_error_with_last_html -v
    Expected: PASSED, AuthError raised with non-empty last_html attribute
    Evidence: .sisyphus/evidence/task-5-auth-no-csrf.txt
  ```

  **Commit**: `feat(auth): implement B2C PKCE headless scrape with full test suite`

- [x] 6. api.py — LegrandApiClientV1 with full TDD

  **What to do**:
  - Write `tests/test_api.py` FIRST (RED), then implement `custom_components/bticino_v1/api.py` (GREEN)
  - `LegrandApiClientV1(auth: AuthHandler, session=None)`
  - `async get_plants()` → `GET /servicecatalog/api/v3.0/plants`
  - `async get_modules(plant_id: str)` → `GET /servicecatalog/api/v3.0/plants/{plantId}/modules`
  - `async open_lock(gateway_id: str, lock_module_id: str)` → `POST /devicemanagement/api/v2.0/modules/{gatewayId}/commands` with `{"command":{"name":"open","moduleId":lock_module_id}}`
  - `async set_light(gateway_id: str, light_module_id: str, on: bool)` → same commands endpoint, `{"command":{"name":"on" if on else "off","moduleId":light_module_id}}`
  - Every call: `Authorization: Bearer {token}` + `Ocp-Apim-Subscription-Key: {key}` headers
  - On 401: call `auth.authenticate()` once and retry
  - On 5xx: exponential backoff, max 3 retries
  - On 4xx (not 401): raise `ApiError(status, body)`
  - `close()` method
  - Tests to write (all mocked with aioresponses):
    - `test_get_plants_sends_subscription_key_header`
    - `test_get_plants_sends_bearer_token_header`
    - `test_get_plants_returns_list_from_fixture`
    - `test_get_modules_returns_all_module_types`
    - `test_open_lock_posts_correct_payload`
    - `test_open_lock_payload_includes_module_id`
    - `test_set_light_on_posts_on_command`
    - `test_set_light_off_posts_off_command`
    - `test_api_401_triggers_reauth_and_retry`
    - `test_api_5xx_retries_three_times`
    - `test_api_4xx_not_401_raises_api_error`
    - `test_api_uses_base_url_from_const`

  **Must NOT do**:
  - No SIP endpoint calls
  - No vdeproducts ticket endpoint (confirmed 404)
  - No hardcoded gateway ID — always pass as parameter

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: Partial — can start once auth.py interface is defined (after task 5 completes)
  - **Parallel Group**: Sequential after task 5
  - **Blocks**: Tasks 7, 9, 10
  - **Blocked By**: Tasks 1, 3, 4, 5 (needs AuthHandler type)

  **References**:
  - PoC session: confirmed endpoints and payloads
  - `tests/fixtures/plants.json`, `tests/fixtures/modules.json`, `tests/fixtures/open_lock_200.json`
  - `k-the-hidden-hero/pybticino/account.py` — request pattern to mirror

  **QA Scenarios**:
  ```
  Scenario: open_lock sends correct payload
    Tool: pytest
    Command: pytest tests/test_api.py::test_open_lock_posts_correct_payload -v
    Expected: PASSED, captured request body == {"command":{"name":"open","moduleId":"test-module-id"}}
    Evidence: .sisyphus/evidence/task-6-api-open-lock.txt

  Scenario: 401 triggers reauth
    Tool: pytest
    Command: pytest tests/test_api.py::test_api_401_triggers_reauth_and_retry -v
    Expected: PASSED, auth.authenticate() called once, second request succeeds
    Evidence: .sisyphus/evidence/task-6-api-401-retry.txt
  ```

  **Commit**: `feat(api): implement LegrandApiClientV1 with retry logic and full test suite`

- [x] 7. coordinator.py — BticinoV1Coordinator with TDD

  **What to do**:
  - Write `tests/test_coordinator.py` FIRST (RED), then implement
  - `BticinoV1Coordinator(hass, entry, auth, api)` extends `DataUpdateCoordinator`
  - `update_interval = timedelta(minutes=UPDATE_INTERVAL)`  (5 min)
  - `_async_update_data()`: call `api.get_modules(plant_id)`, parse into `{"modules": {id: module_dict}, "gateway_id": str, "plant_id": str}`
  - `gateway_id` property: find module with `device=="gateway"`, return its id
  - `async_open_lock(module_id)`: call `api.open_lock(gateway_id, module_id)`
  - `async_set_light(module_id, on)`: call `api.set_light(gateway_id, module_id, on)`
  - On `AuthError`: raise `ConfigEntryAuthFailed`
  - On transient errors (5xx, timeout): log warning, return `self.data` (last known)
  - Tests:
    - `test_update_interval_is_5_minutes`
    - `test_async_update_data_returns_modules_dict`
    - `test_async_update_data_finds_gateway_id`
    - `test_async_update_data_auth_error_raises_config_entry_auth_failed`
    - `test_async_update_data_transient_error_returns_last_data`
    - `test_async_open_lock_calls_api_with_gateway_and_module_ids`
    - `test_async_set_light_calls_api`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES with tasks 8, 9 (after tasks 5+6 complete)
  - **Parallel Group**: Wave 3 start
  - **Blocks**: Tasks 10, 11, 12, 13, 14
  - **Blocked By**: Tasks 5, 6, 3

  **References**:
  - `k-the-hidden-hero/bticino_intercom/custom_components/bticino_intercom/coordinator.py` — structure to mirror
  - `tests/fixtures/modules.json` — fixture data shapes

  **QA Scenarios**:
  ```
  Scenario: Coordinator finds gateway
    Tool: pytest
    Command: pytest tests/test_coordinator.py::test_async_update_data_finds_gateway_id -v
    Expected: PASSED, coordinator.gateway_id matches gateway module id from fixture

  Scenario: Transient error keeps last data
    Tool: pytest
    Command: pytest tests/test_coordinator.py::test_async_update_data_transient_error_returns_last_data -v
    Expected: PASSED, no UpdateFailed raised, data unchanged
  ```

  **Commit**: `feat(coordinator): implement BticinoV1Coordinator with polling and error handling`

- [x] 8. entity.py — BticinoV1Entity base class with TDD

  **What to do**:
  - Write `tests/test_entity.py` FIRST (RED), then implement
  - `BticinoV1Entity(CoordinatorEntity[BticinoV1Coordinator], module_id: str)`
  - `_attr_has_entity_name = True`
  - `device_info` → `DeviceInfo(identifiers={(DOMAIN, coordinator.gateway_id)}, name=f"BTicino Intercom - {plant_name}", manufacturer="BTicino", model=gateway_device_type, sw_version=gateway_firmware)`
  - `unique_id` base: `f"{entry.entry_id}_{module_id}"` (subclasses add platform prefix)
  - Tests:
    - `test_entity_has_entity_name_true`
    - `test_device_info_anchors_to_gateway`
    - `test_device_info_includes_firmware_version`
    - `test_unique_id_uses_entry_id_and_module_id`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES with tasks 7, 9
  - **Blocks**: Tasks 10, 11, 12, 13, 14
  - **Blocked By**: Tasks 1, 3

  **References**:
  - `k-the-hidden-hero/bticino_intercom/custom_components/bticino_intercom/entity.py`

  **QA Scenarios**:
  ```
  Scenario: Device info anchors to gateway
    Tool: pytest
    Command: pytest tests/test_entity.py::test_device_info_anchors_to_gateway -v
    Expected: PASSED, device_info.identifiers == {("bticino_v1", gateway_id)}
  ```

  **Commit**: `feat(entity): implement BticinoV1Entity base class`

- [x] 9. config_flow.py — full config + options + reauth with TDD

  **What to do**:
  - Write `tests/test_config_flow.py` FIRST (RED), then implement
  - `BticinoV1ConfigFlow(ConfigFlow, domain=DOMAIN)` VERSION=1
  - `async_step_user`: show email+password form → validate (call auth.authenticate() + api.get_plants()) → if 1 plant go to init_options, if multiple go to select_home → abort if 0 plants
  - `async_step_select_home`: dropdown of plant names → store home_id → go to init_options
  - `async_step_init_options`: light_as_lock BooleanSelector → create entry
  - `async_step_reauth` + `async_step_reauth_confirm`: password-only re-entry
  - `BticinoV1OptionsFlowHandler`: update light_as_lock option
  - Store in `config_entry.data`: `{CONF_USERNAME, CONF_PASSWORD, "home_id", "gateway_id"}`
  - `async_set_unique_id(data[CONF_USERNAME])` + `_abort_if_unique_id_configured()`
  - Tests (use HA flow test harness):
    - `test_user_step_single_plant_skips_home_selection`
    - `test_user_step_multiple_plants_shows_select_home`
    - `test_user_step_invalid_auth_shows_error`
    - `test_user_step_cannot_connect_shows_error`
    - `test_user_step_zero_plants_aborts`
    - `test_already_configured_aborts`
    - `test_select_home_stores_home_id`
    - `test_init_options_creates_entry_with_light_as_lock_false`
    - `test_reauth_confirm_updates_password`
    - `test_reauth_confirm_invalid_password_shows_error`
    - `test_options_flow_updates_light_as_lock`

  **Must NOT do**:
  - No FCM token field in options flow (deferred to v1.1.0)
  - No polling_interval option (not needed — no events)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES with tasks 7, 8 (after tasks 5+6)
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 5, 6, 3

  **References**:
  - `k-the-hidden-hero/bticino_intercom/custom_components/bticino_intercom/config_flow.py` — exact pattern
  - `k-the-hidden-hero/bticino_intercom/custom_components/bticino_intercom/strings.json` — error key names

  **QA Scenarios**:
  ```
  Scenario: Single plant — no home selection
    Tool: pytest
    Command: pytest tests/test_config_flow.py::test_user_step_single_plant_skips_home_selection -v
    Expected: PASSED, flow goes directly to init_options step

  Scenario: Already configured aborts
    Tool: pytest
    Command: pytest tests/test_config_flow.py::test_already_configured_aborts -v
    Expected: PASSED, reason="already_configured"
  ```

  **Commit**: `feat(config_flow): implement full config flow with home selection, options, and reauth`

- [x] 10. __init__.py — entry lifecycle: setup, unload, Store token persistence with TDD

  **What to do**:
  - Write `tests/test_init.py` FIRST (RED), then implement
  - `async_setup_entry(hass, entry)`:
    - Create `AuthHandler` with token_callback persisting to `Store(hass, 1, f"{DOMAIN}.tokens.{entry.entry_id}")`
    - Restore saved tokens via `auth.set_tokens()`
    - Validate with `auth.get_access_token()` → raises `ConfigEntryAuthFailed` on `AuthError`
    - Create `LegrandApiClientV1(auth)`
    - Create `BticinoV1Coordinator(hass, entry, auth, api)`
    - `await coordinator.async_config_entry_first_refresh()` → raises `ConfigEntryNotReady` on failure
    - Store in `hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator, "auth": auth, "api": api}`
    - `async_forward_entry_setups(entry, PLATFORMS)`
    - `entry.async_on_unload(entry.add_update_listener(async_reload_entry))`
  - `async_unload_entry`: cancel tasks, close auth session, unload platforms, clean hass.data
  - `async_remove_entry`: delete Store
  - Tests:
    - `test_setup_entry_stores_coordinator_in_hass_data`
    - `test_setup_entry_auth_error_raises_config_entry_auth_failed`
    - `test_setup_entry_api_error_raises_config_entry_not_ready`
    - `test_setup_entry_restores_tokens_from_store`
    - `test_unload_entry_cleans_hass_data`
    - `test_unload_entry_closes_auth_session`
    - `test_remove_entry_deletes_store`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO — depends on all Wave 3
  - **Blocks**: Task 16
  - **Blocked By**: Tasks 7, 8, 9

  **QA Scenarios**:
  ```
  Scenario: Setup stores coordinator
    Tool: pytest
    Command: pytest tests/test_init.py::test_setup_entry_stores_coordinator_in_hass_data -v
    Expected: PASSED, hass.data["bticino_v1"][entry_id]["coordinator"] is BticinoV1Coordinator

  Scenario: Auth failure raises ConfigEntryAuthFailed
    Tool: pytest
    Command: pytest tests/test_init.py::test_setup_entry_auth_error_raises_config_entry_auth_failed -v
    Expected: PASSED, ConfigEntryAuthFailed raised
  ```

  **Commit**: `feat(init): implement entry lifecycle with Store token persistence`

- [x] 11. lock.py — BticinoV1Lock entity with TDD

  **What to do**:
  - Write `tests/test_lock.py` FIRST (RED), then implement
  - `async_setup_entry`: iterate coordinator modules, create `BticinoV1Lock` for each with `device=="lock"`
  - `BticinoV1Lock(BticinoV1Entity, LockEntity)`:
    - `_attr_supported_features = LockEntityFeature.OPEN`
    - `_attr_unique_id = f"{entry.entry_id}_lock_{module_id}"`
    - `_attr_name`: module name from coordinator data
    - `is_locked`: optimistic — True by default, False after unlock, reset after LOCK_RELOCK_DELAY seconds via `async_call_later`
    - `async_unlock(**kwargs)` → `coordinator.async_open_lock(module_id)`, optimistic state, schedule relock
    - `available`: `coordinator.last_update_success`
    - `_handle_coordinator_update`: restore locked state if relock timer not active
  - Tests:
    - `test_lock_created_for_lock_modules_only`
    - `test_lock_unique_id_format`
    - `test_lock_not_created_for_gateway_modules`
    - `test_async_unlock_calls_coordinator_open_lock`
    - `test_async_unlock_sets_optimistic_unlocked_state`
    - `test_async_unlock_schedules_relock`
    - `test_lock_unavailable_when_coordinator_fails`
    - `test_lock_handles_api_error_without_crash`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES with tasks 12, 13, 14, 15
  - **Blocks**: Task 16
  - **Blocked By**: Tasks 7, 8, 3

  **References**:
  - `k-the-hidden-hero/bticino_intercom/custom_components/bticino_intercom/lock.py` — exact pattern
  - `k-the-hidden-hero/bticino_intercom/custom_components/bticino_intercom/const.py` — LOCK_RELOCK_DELAY=5

  **QA Scenarios**:
  ```
  Scenario: Unlock calls coordinator
    Tool: pytest
    Command: pytest tests/test_lock.py::test_async_unlock_calls_coordinator_open_lock -v
    Expected: PASSED, coordinator.async_open_lock called with correct module_id

  Scenario: Only lock modules get lock entities
    Tool: pytest
    Command: pytest tests/test_lock.py::test_lock_created_for_lock_modules_only -v
    Expected: PASSED, 3 entities for 3 lock modules, none for gateway/light/EU
  ```

  **Commit**: `feat(lock): implement BticinoV1Lock with optimistic state and relock timer`

- [x] 12. light.py — BticinoV1Light + LightAsLock option with TDD

  **What to do**:
  - Write `tests/test_light.py` FIRST (RED), then implement
  - `async_setup_entry`: create `BticinoV1Light` for `device=="light"` modules; if `light_as_lock=True` option, also create `BticinoV1LightAsLock` instead
  - `BticinoV1Light(BticinoV1Entity, LightEntity)`:
    - `async_turn_on` → `coordinator.async_set_light(module_id, True)`
    - `async_turn_off` → `coordinator.async_set_light(module_id, False)`
    - `is_on`: from coordinator data `status=="on"`
    - `_attr_unique_id = f"{entry.entry_id}_light_{module_id}"`
  - `BticinoV1LightAsLock(BticinoV1Entity, LockEntity)`:
    - Same as BticinoV1Lock but calls set_light instead of open_lock
    - Used when `light_as_lock=True` in options
  - Tests:
    - `test_light_created_for_light_modules`
    - `test_light_as_lock_created_when_option_true`
    - `test_light_as_lock_not_created_when_option_false`
    - `test_light_turn_on_calls_coordinator`
    - `test_light_turn_off_calls_coordinator`
    - `test_light_as_lock_unlock_calls_set_light_on`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES with tasks 11, 13, 14, 15
  - **Blocks**: Task 16
  - **Blocked By**: Tasks 7, 8, 3

  **References**:
  - `k-the-hidden-hero/bticino_intercom/custom_components/bticino_intercom/light.py`
  - `k-the-hidden-hero/bticino_intercom/custom_components/bticino_intercom/lock.py` — LightAsLock pattern

  **QA Scenarios**:
  ```
  Scenario: Light turn on calls coordinator
    Tool: pytest
    Command: pytest tests/test_light.py::test_light_turn_on_calls_coordinator -v
    Expected: PASSED, coordinator.async_set_light called with (module_id, True)

  Scenario: light_as_lock option creates lock entity
    Tool: pytest
    Command: pytest tests/test_light.py::test_light_as_lock_created_when_option_true -v
    Expected: PASSED, LightAsLock entity created, regular LightEntity not created
  ```

  **Commit**: `feat(light): implement BticinoV1Light and LightAsLock option`

- [x] 13. sensor.py — gateway diagnostics sensors with TDD

  **What to do**:
  - Write `tests/test_sensor.py` FIRST (RED), then implement
  - `async_setup_entry`: create sensors from gateway module data
  - `BticinoV1FirmwareSensor`: state = `gateway_module["firmwareVersion"]`, `entity_category=EntityCategory.DIAGNOSTIC`
  - `BticinoV1IpSensor`: state = `gateway_module["ipAddress"]`, EntityCategory.DIAGNOSTIC
  - `BticinoV1ConnectionSensor`: state = `gateway_module["connectionState"]`, EntityCategory.DIAGNOSTIC
  - `BticinoV1LastPollSensor`: state = `utcnow().isoformat()` updated each coordinator refresh
  - All: `_attr_has_entity_name=True`, unique_id `f"{entry.entry_id}_sensor_{name}_{gateway_id}"`
  - Tests:
    - `test_firmware_sensor_state_from_coordinator`
    - `test_ip_sensor_state_from_coordinator`
    - `test_connection_sensor_state_connected`
    - `test_sensors_are_diagnostic_category`
    - `test_sensors_unavailable_when_no_gateway`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES with tasks 11, 12, 14, 15
  - **Blocks**: Task 16
  - **Blocked By**: Tasks 7, 8, 3

  **QA Scenarios**:
  ```
  Scenario: Firmware sensor reads from coordinator
    Tool: pytest
    Command: pytest tests/test_sensor.py::test_firmware_sensor_state_from_coordinator -v
    Expected: PASSED, sensor state == "1.5.8" (from fixture)
  ```

  **Commit**: `feat(sensor): implement gateway diagnostics sensors`

- [x] 14. diagnostics.py — redacted config export with TDD

  **What to do**:
  - Write `tests/test_diagnostics.py` FIRST (RED), then implement
  - `async_get_config_entry_diagnostics(hass, entry)` function
  - Output: dict with `config_entry` (with sensitive fields redacted) + coordinator data snapshot
  - Redact: `password`, `access_token`, `refresh_token`, `code_verifier`, `csrf` → replaced with `"**REDACTED**"`
  - Keep: `username`, `home_id`, `gateway_id`, module IDs, plant name
  - Subscription key: `"f36968e…" → "f36968e5**REDACTED**"` (partial)
  - Tests:
    - `test_password_redacted_in_diagnostics`
    - `test_access_token_redacted_in_diagnostics`
    - `test_username_preserved_in_diagnostics`
    - `test_home_id_preserved_in_diagnostics`
    - `test_coordinator_data_included_in_diagnostics`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES with tasks 11, 12, 13, 15
  - **Blocks**: Task 16
  - **Blocked By**: Tasks 7, 8, 3

  **QA Scenarios**:
  ```
  Scenario: Password redacted
    Tool: pytest
    Command: pytest tests/test_diagnostics.py::test_password_redacted_in_diagnostics -v
    Expected: PASSED, "password" value == "**REDACTED**" in output
  ```

  **Commit**: `feat(diagnostics): implement diagnostics with sensitive field redaction`

- [x] 15. strings.json + translations/en.json + quality_scale.yaml

  **What to do**:
  - `strings.json`: config steps (user, select_home, init_options, reauth_confirm), errors (invalid_auth, cannot_connect, unknown), aborts (already_configured, no_plants_found, reauth_successful), options step (light_as_lock)
  - `translations/en.json`: identical content (HA uses both)
  - `quality_scale.yaml`: silver tier checklist (has tests, config_flow, unique_id, diagnostics, docs)
  - Mirror `k-the-hidden-hero/bticino_intercom` strings structure exactly, adapting text for v1 specifics

  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES with tasks 11, 12, 13, 14
  - **Blocks**: Task 16
  - **Blocked By**: Task 1

  **QA Scenarios**:
  ```
  Scenario: strings.json valid JSON
    Tool: bash
    Command: python -c "import json; json.load(open('custom_components/bticino_v1/strings.json'))"
    Expected: exits 0

  Scenario: translations/en.json exists and valid
    Tool: bash
    Command: python -c "import json; json.load(open('custom_components/bticino_v1/translations/en.json'))"
    Expected: exits 0
  ```

  **Commit**: `feat(i18n): add strings.json, translations/en.json, quality_scale.yaml`

- [x] 16. Final verification + HACS check + README polish

  **What to do**:
  - Run full test suite: `pytest tests/ -x --tb=short -q`
  - Run coverage: `pytest tests/ --cov=custom_components/bticino_v1 --cov-report=term-missing` — verify auth.py ≥85%, api.py ≥85%, overall ≥70%
  - Run hassfest: `python -m script.hassfest --integration-path custom_components/bticino_v1`
  - Verify no forbidden patterns: `grep -r 'binary_sensor\|camera\|SIP\|firebase_admin\|cloud_push\|fixed.*verifier' custom_components/bticino_v1/`
  - Verify no APK files tracked: `git ls-files | grep -E '\.(apk|xapk)$'` → empty
  - Polish README: add screenshots placeholders, verify known limitations section mentions ring events deferred
  - Bump manifest to v1.0.0, tag commit

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO — depends on all tasks
  - **Blocks**: Final Verification Wave
  - **Blocked By**: Tasks 2, 10, 11, 12, 13, 14, 15

  **QA Scenarios**:
  ```
  Scenario: All tests pass
    Tool: bash
    Command: pytest tests/ -x -q
    Expected: "X passed" with no failures, exit 0
    Evidence: .sisyphus/evidence/task-16-pytest.txt

  Scenario: Coverage gates met
    Tool: bash
    Command: pytest tests/ --cov=custom_components/bticino_v1 --cov-report=term-missing 2>&1 | grep -E "auth|api|TOTAL"
    Expected: auth.py ≥85%, api.py ≥85%, TOTAL ≥70%
    Evidence: .sisyphus/evidence/task-16-coverage.txt

  Scenario: hassfest passes
    Tool: bash
    Command: python -m script.hassfest --integration-path custom_components/bticino_v1; echo "EXIT:$?"
    Expected: EXIT:0
    Evidence: .sisyphus/evidence/task-16-hassfest.txt

  Scenario: No forbidden code
    Tool: bash
    Command: grep -r 'binary_sensor\|camera\|cloud_push\|firebase_admin' custom_components/bticino_v1/ && echo FOUND || echo CLEAN
    Expected: CLEAN
    Evidence: .sisyphus/evidence/task-16-forbidden-check.txt
  ```

  **Commit**: `chore(release): final verification, README polish, v1.0.0`

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE. Get explicit user "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each Must Have: verify implementation exists (read file). For each Must NOT Have: grep for forbidden patterns (SIP, camera, FCM, fixed PKCE vectors, `cloud_push`). Check test count ≥ stated minimums. Check evidence files in .sisyphus/evidence/.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tests [N pass] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `pytest tests/ --tb=short -q`. Check manifest.json keys complete. Check `hassfest` passes. Check no `as any`/`type: ignore`, no `requests` (must use aiohttp), no fixed PKCE vectors, no firebase-admin import, no apk files tracked. Check auth.py coverage ≥85%.
  Output: `Tests [N pass/N fail] | Coverage auth [N%] api [N%] overall [N%] | hassfest [PASS/FAIL] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Install integration in HA dev container. Configure with real credentials. Verify: lock entities appear, `lock.unlock` sends correct API call (check logs), light entity appears, gateway sensor has firmware version, reauth flow works (change password to wrong → expect invalid_auth). Save log to .sisyphus/evidence/final-qa/.
  Output: `Entities [N found] | Lock command [logged correctly Y/N] | Reauth [PASS/FAIL] | VERDICT`

- [x] F4. **Scope Fidelity** — `deep`
  Diff against plan scope. Verify no binary_sensor.py, no event.py, no camera.py, no SIP code, no FCM code. Verify no APK files. Verify hacs.json + README + info.md present. Verify iot_class=cloud_polling in manifest. Verify fresh PKCE generation (no hardcoded verifier).
  Output: `Forbidden files [NONE/list] | Scope violations [NONE/list] | VERDICT`

---

## Commit Strategy

- Every RED test commit: `test(module): add <specific> tests`
- Every GREEN impl commit: `feat(module): implement <specific>`
- One commit per task (squash RED+GREEN pairs into `feat(module): add X with tests`)
- Final: `chore(release): v1.0.0`

---

## Success Criteria

### Verification Commands
```bash
pytest tests/ -x -q                     # Expected: all pass
pytest tests/ --cov=custom_components/bticino_v1 --cov-report=term-missing
# Expected: auth.py ≥85%, api.py ≥85%, overall ≥70%
python -m script.hassfest --integration-path custom_components/bticino_v1
# Expected: exit 0
```

### Final Checklist
- [ ] All Must Have items implemented and tested
- [ ] All Must NOT Have items absent (grep verified)
- [ ] Coverage gates met
- [ ] hassfest passes
- [ ] HACS validation passes
- [ ] One-time human smoke: door opens via HA lock entity
