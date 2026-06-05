"""Shared pytest fixtures for bticino_v1 tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_auth():
    """Mock AuthHandler."""
    auth = AsyncMock()
    auth.get_access_token = AsyncMock(return_value="eyJFIXTURE_ACCESS_TOKEN")
    auth.authenticate = AsyncMock()
    auth.close = AsyncMock()
    auth.set_tokens = MagicMock()
    return auth


@pytest.fixture
def mock_api():
    """Mock LegrandApiClientV1."""
    api = AsyncMock()
    api.get_plants = AsyncMock(return_value=[
        {"id": "plant-id-001", "name": "Test Home", "ownerEmail": "fixture@example.com"}
    ])
    api.get_modules = AsyncMock(return_value=[
        {"id": "gateway-id-001", "device": "gateway", "name": "", "firmwareVersion": "1.5.8",
         "ipAddress": "192.168.0.1", "connectionState": "CONNECTED", "deviceType": "C1X",
         "macAddress": "00:00:00:00:00:01"},
        {"id": "lock-id-001", "device": "lock", "name": "A-Door", "deviceType": "Lock",
         "status": "registered"},
        {"id": "lock-id-002", "device": "lock", "name": "Gate", "deviceType": "Lock",
         "status": "registered"},
        {"id": "light-id-001", "device": "light", "name": "Staircase Lights",
         "deviceType": "Staircase", "status": "registered"},
        {"id": "eu-id-001", "device": "audioVideoTerminal", "name": "A-Door",
         "deviceType": "EU", "status": "registered"},
    ])
    api.open_lock = AsyncMock(return_value={})
    api.set_light = AsyncMock(return_value={})
    api.close = AsyncMock()
    return api


@pytest.fixture
def mock_coordinator(mock_api, mock_auth):
    """Mock BticinoV1Coordinator with pre-populated data."""
    coordinator = MagicMock()
    coordinator.data = {
        "modules": {
            "gateway-id-001": {"id": "gateway-id-001", "device": "gateway", "name": "",
                               "firmwareVersion": "1.5.8", "ipAddress": "192.168.0.1",
                               "connectionState": "CONNECTED", "deviceType": "C1X"},
            "lock-id-001": {"id": "lock-id-001", "device": "lock", "name": "A-Door",
                            "deviceType": "Lock", "status": "registered"},
            "lock-id-002": {"id": "lock-id-002", "device": "lock", "name": "Gate",
                            "deviceType": "Lock", "status": "registered"},
            "light-id-001": {"id": "light-id-001", "device": "light", "name": "Staircase Lights",
                             "deviceType": "Staircase", "status": "registered"},
            "eu-id-001": {"id": "eu-id-001", "device": "audioVideoTerminal", "name": "A-Door",
                          "deviceType": "EU", "status": "registered"},
        },
        "gateway_id": "gateway-id-001",
        "plant_id": "plant-id-001",
    }
    coordinator.gateway_id = "gateway-id-001"
    coordinator.last_update_success = True
    coordinator.async_open_lock = AsyncMock()
    coordinator.async_set_light = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    return coordinator


@pytest.fixture
def config_entry():
    """Mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id_001"
    entry.data = {
        "username": "fixture@example.com",
        "password": "fixture_password",
        "home_id": "plant-id-001",
        "gateway_id": "gateway-id-001",
    }
    entry.options = {"light_as_lock": False}
    return entry
