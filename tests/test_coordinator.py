"""Tests for BticinoV1Coordinator."""
import pytest
import json
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.bticino_v1.coordinator import BticinoV1Coordinator
from custom_components.bticino_v1.auth import AuthError
from custom_components.bticino_v1.api import ApiError
from custom_components.bticino_v1.const import UPDATE_INTERVAL, DEVICE_TYPE_GATEWAY

MODULES_FIXTURE = json.load(open("tests/fixtures/modules.json"))


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.loop = MagicMock()
    return hass


@pytest.fixture
def mock_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        "username": "fixture@example.com",
        "home_id": "plant-id-001",
        "gateway_id": "gateway-id-001",
    }
    return entry


@pytest.fixture
def mock_auth():
    auth = AsyncMock()
    auth.get_access_token = AsyncMock(return_value="eyJFIXTURE")
    return auth


@pytest.fixture
def mock_api():
    api = AsyncMock()
    api.get_modules = AsyncMock(return_value=MODULES_FIXTURE)
    api.open_lock = AsyncMock(return_value={})
    api.set_light = AsyncMock(return_value={})
    return api


@pytest.mark.asyncio
async def test_update_interval_is_5_minutes(mock_hass, mock_entry, mock_auth, mock_api):
    """Coordinator update_interval must be 5 minutes."""
    coordinator = BticinoV1Coordinator(mock_hass, mock_entry, mock_auth, mock_api)
    assert coordinator.update_interval == timedelta(minutes=UPDATE_INTERVAL)
    assert coordinator.update_interval == timedelta(minutes=5)


@pytest.mark.asyncio
async def test_async_update_data_returns_modules_dict(mock_hass, mock_entry, mock_auth, mock_api):
    """_async_update_data must return dict with 'modules' key mapping id→module."""
    coordinator = BticinoV1Coordinator(mock_hass, mock_entry, mock_auth, mock_api)
    data = await coordinator._async_update_data()
    assert "modules" in data
    assert isinstance(data["modules"], dict)
    # All modules from fixture should be in the dict
    for module in MODULES_FIXTURE:
        assert module["id"] in data["modules"]


@pytest.mark.asyncio
async def test_async_update_data_finds_gateway_id(mock_hass, mock_entry, mock_auth, mock_api):
    """_async_update_data must identify the gateway module and store its id."""
    coordinator = BticinoV1Coordinator(mock_hass, mock_entry, mock_auth, mock_api)
    data = await coordinator._async_update_data()
    # gateway_id must be set to the module with device=="gateway"
    gateway_modules = [m for m in MODULES_FIXTURE if m["device"] == DEVICE_TYPE_GATEWAY]
    assert len(gateway_modules) == 1
    assert data["gateway_id"] == gateway_modules[0]["id"]
    assert coordinator.gateway_id == gateway_modules[0]["id"]


@pytest.mark.asyncio
async def test_async_update_data_auth_error_raises_config_entry_auth_failed(
    mock_hass, mock_entry, mock_auth, mock_api
):
    """AuthError from API must be re-raised as ConfigEntryAuthFailed."""
    mock_api.get_modules = AsyncMock(side_effect=AuthError("token expired"))
    coordinator = BticinoV1Coordinator(mock_hass, mock_entry, mock_auth, mock_api)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_async_update_data_transient_error_returns_last_data(
    mock_hass, mock_entry, mock_auth, mock_api
):
    """Transient API errors must return last known data, not raise UpdateFailed."""
    coordinator = BticinoV1Coordinator(mock_hass, mock_entry, mock_auth, mock_api)
    # First successful update
    first_data = await coordinator._async_update_data()
    coordinator.data = first_data

    # Now simulate transient error
    mock_api.get_modules = AsyncMock(side_effect=ApiError(503, "Service Unavailable"))
    result = await coordinator._async_update_data()

    # Must return last known data, not raise
    assert result == first_data


@pytest.mark.asyncio
async def test_async_open_lock_calls_api_with_gateway_and_module_ids(
    mock_hass, mock_entry, mock_auth, mock_api
):
    """async_open_lock must call api.open_lock(gateway_id, module_id)."""
    coordinator = BticinoV1Coordinator(mock_hass, mock_entry, mock_auth, mock_api)
    coordinator.data = {
        "modules": {},
        "gateway_id": "gateway-id-001",
        "plant_id": "plant-id-001",
    }
    await coordinator.async_open_lock("lock-id-001")
    mock_api.open_lock.assert_called_once_with("gateway-id-001", "lock-id-001")


@pytest.mark.asyncio
async def test_async_set_light_calls_api(mock_hass, mock_entry, mock_auth, mock_api):
    """async_set_light must call api.set_light(gateway_id, module_id, on)."""
    coordinator = BticinoV1Coordinator(mock_hass, mock_entry, mock_auth, mock_api)
    coordinator.data = {
        "modules": {},
        "gateway_id": "gateway-id-001",
        "plant_id": "plant-id-001",
    }
    await coordinator.async_set_light("light-id-001", True)
    mock_api.set_light.assert_called_once_with("gateway-id-001", "light-id-001", True)
