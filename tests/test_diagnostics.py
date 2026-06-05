import pytest
from unittest.mock import MagicMock
from custom_components.bticino_v1.diagnostics import async_get_config_entry_diagnostics
from custom_components.bticino_v1.const import DOMAIN, COORDINATOR_KEY

@pytest.fixture
def mock_hass():
    hass = MagicMock()
    coordinator = MagicMock()
    coordinator.data = {"modules": {"gw-001": {"id": "gw-001", "device": "gateway"}}, "gateway_id": "gw-001", "plant_id": "plant-001"}
    hass.data = {DOMAIN: {"test_entry_id": {COORDINATOR_KEY: coordinator}}}
    return hass

@pytest.fixture
def mock_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {"username": "user@example.com", "password": "supersecret", "home_id": "plant-001", "gateway_id": "gw-001"}
    entry.options = {"light_as_lock": False}
    return entry

@pytest.mark.asyncio
async def test_password_redacted_in_diagnostics(mock_hass, mock_entry):
    result = await async_get_config_entry_diagnostics(mock_hass, mock_entry)
    assert result["config_entry"]["data"]["password"] == "**REDACTED**"

@pytest.mark.asyncio
async def test_access_token_redacted_in_diagnostics(mock_hass, mock_entry):
    mock_entry.data = {**mock_entry.data, "access_token": "eyJSECRET"}
    result = await async_get_config_entry_diagnostics(mock_hass, mock_entry)
    assert result["config_entry"]["data"].get("access_token") == "**REDACTED**"

@pytest.mark.asyncio
async def test_username_preserved_in_diagnostics(mock_hass, mock_entry):
    result = await async_get_config_entry_diagnostics(mock_hass, mock_entry)
    assert result["config_entry"]["data"]["username"] == "user@example.com"

@pytest.mark.asyncio
async def test_home_id_preserved_in_diagnostics(mock_hass, mock_entry):
    result = await async_get_config_entry_diagnostics(mock_hass, mock_entry)
    assert result["config_entry"]["data"]["home_id"] == "plant-001"

@pytest.mark.asyncio
async def test_coordinator_data_included_in_diagnostics(mock_hass, mock_entry):
    result = await async_get_config_entry_diagnostics(mock_hass, mock_entry)
    assert "coordinator_data" in result
    assert "gateway_id" in result["coordinator_data"]
