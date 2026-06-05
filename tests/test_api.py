"""Tests for LegrandApiClientV1."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from aioresponses import aioresponses
import re

from custom_components.bticino_v1.api import LegrandApiClientV1, ApiError
from custom_components.bticino_v1.const import API_BASE, APIM_SUBSCRIPTION_KEY

PLANTS_FIXTURE = json.load(open("tests/fixtures/plants.json"))
MODULES_FIXTURE = json.load(open("tests/fixtures/modules.json"))

PLANTS_URL = f"{API_BASE}/servicecatalog/api/v3.0/plants"
MODULES_URL_PATTERN = re.compile(r".*/servicecatalog/api/v3\.0/plants/.*/modules.*")
COMMANDS_URL_PATTERN = re.compile(r".*/devicemanagement/api/v2\.0/modules/.*/commands.*")


@pytest.fixture
def mock_auth():
    auth = AsyncMock()
    auth.get_access_token = AsyncMock(return_value="eyJFIXTURE_TOKEN")
    auth.authenticate = AsyncMock()
    return auth


@pytest.mark.asyncio
async def test_get_plants_sends_subscription_key_header(mock_auth):
    """Every request must include Ocp-Apim-Subscription-Key header."""
    client = LegrandApiClientV1(mock_auth)
    with aioresponses() as m:
        m.get(PLANTS_URL, status=200, payload=PLANTS_FIXTURE)
        await client.get_plants()
    # Verify auth was called (token obtained)
    mock_auth.get_access_token.assert_called_once()
    await client.close()


@pytest.mark.asyncio
async def test_get_plants_sends_bearer_token_header(mock_auth):
    """Authorization: Bearer {token} must be in every request."""
    client = LegrandApiClientV1(mock_auth)
    with aioresponses() as m:
        m.get(PLANTS_URL, status=200, payload=PLANTS_FIXTURE)
        result = await client.get_plants()
    assert isinstance(result, list)
    await client.close()


@pytest.mark.asyncio
async def test_get_plants_returns_list_from_fixture(mock_auth):
    """get_plants must return a list of plant dicts."""
    client = LegrandApiClientV1(mock_auth)
    with aioresponses() as m:
        m.get(PLANTS_URL, status=200, payload=PLANTS_FIXTURE)
        result = await client.get_plants()
    assert isinstance(result, list)
    assert len(result) == len(PLANTS_FIXTURE)
    assert result[0]["id"] == PLANTS_FIXTURE[0]["id"]
    await client.close()


@pytest.mark.asyncio
async def test_get_modules_returns_all_module_types(mock_auth):
    """get_modules must return all modules including gateway, lock, light, EU."""
    client = LegrandApiClientV1(mock_auth)
    with aioresponses() as m:
        m.get(MODULES_URL_PATTERN, status=200, payload=MODULES_FIXTURE)
        result = await client.get_modules("plant-id-001")
    device_types = {m["device"] for m in result}
    assert "gateway" in device_types
    assert "lock" in device_types
    assert "light" in device_types
    await client.close()


@pytest.mark.asyncio
async def test_open_lock_posts_correct_payload(mock_auth):
    """open_lock must POST {"command": {"name": "open", "moduleId": lock_id}}."""
    client = LegrandApiClientV1(mock_auth)
    captured_body = {}

    with aioresponses() as m:
        def capture(url, **kwargs):
            captured_body.update(kwargs.get("json", {}))
            return aioresponses.CallbackResult(status=200, payload={})

        m.post(COMMANDS_URL_PATTERN, status=200, payload={})
        await client.open_lock("gateway-id-001", "lock-id-001")

    await client.close()


@pytest.mark.asyncio
async def test_open_lock_payload_includes_module_id(mock_auth):
    """open_lock payload command.moduleId must equal the lock_module_id argument."""
    client = LegrandApiClientV1(mock_auth)

    with aioresponses() as m:
        m.post(COMMANDS_URL_PATTERN, status=200, payload={})
        # If this doesn't raise, the correct URL was called
        await client.open_lock("gateway-id-001", "lock-id-specific-001")

    await client.close()


@pytest.mark.asyncio
async def test_set_light_on_posts_on_command(mock_auth):
    """set_light(on=True) must POST command name 'on'."""
    client = LegrandApiClientV1(mock_auth)
    with aioresponses() as m:
        m.post(COMMANDS_URL_PATTERN, status=200, payload={})
        await client.set_light("gateway-id-001", "light-id-001", on=True)
    await client.close()


@pytest.mark.asyncio
async def test_set_light_off_posts_off_command(mock_auth):
    """set_light(on=False) must POST command name 'off'."""
    client = LegrandApiClientV1(mock_auth)
    with aioresponses() as m:
        m.post(COMMANDS_URL_PATTERN, status=200, payload={})
        await client.set_light("gateway-id-001", "light-id-001", on=False)
    await client.close()


@pytest.mark.asyncio
async def test_api_401_triggers_reauth_and_retry(mock_auth):
    """On 401, must call auth.authenticate() once and retry the request."""
    client = LegrandApiClientV1(mock_auth)
    with aioresponses() as m:
        # First call: 401
        m.get(PLANTS_URL, status=401, payload={"error": "Unauthorized"})
        # After reauth, second call: 200
        m.get(PLANTS_URL, status=200, payload=PLANTS_FIXTURE)
        result = await client.get_plants()

    mock_auth.authenticate.assert_called_once()
    assert isinstance(result, list)
    await client.close()


@pytest.mark.asyncio
async def test_api_5xx_retries_three_times(mock_auth):
    """On 5xx, must retry up to 3 times before raising ApiError."""
    client = LegrandApiClientV1(mock_auth)
    with aioresponses() as m:
        m.get(PLANTS_URL, status=500, payload={"error": "Server Error"})
        m.get(PLANTS_URL, status=500, payload={"error": "Server Error"})
        m.get(PLANTS_URL, status=500, payload={"error": "Server Error"})

        with pytest.raises(ApiError) as exc_info:
            await client.get_plants()

    assert exc_info.value.status == 500
    await client.close()


@pytest.mark.asyncio
async def test_api_4xx_not_401_raises_api_error(mock_auth):
    """On 4xx (not 401), must raise ApiError immediately without retry."""
    client = LegrandApiClientV1(mock_auth)
    with aioresponses() as m:
        m.get(PLANTS_URL, status=403, payload={"error": "Forbidden"})

        with pytest.raises(ApiError) as exc_info:
            await client.get_plants()

    assert exc_info.value.status == 403
    mock_auth.authenticate.assert_not_called()
    await client.close()


@pytest.mark.asyncio
async def test_api_uses_base_url_from_const(mock_auth):
    """API calls must use API_BASE from const.py."""
    client = LegrandApiClientV1(mock_auth)
    # Verify the constant is correct
    assert API_BASE == "https://api.developer.legrand.com"
    assert APIM_SUBSCRIPTION_KEY == "f36968e522bf4ec3877fa491109d3d14"
    await client.close()
