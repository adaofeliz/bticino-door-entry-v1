"""Tests for BticinoV1Light and BticinoV1LightAsLock."""
# pyright: reportMissingImports=false
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.bticino_v1.light import BticinoV1Light, BticinoV1LightAsLock, async_setup_entry
from custom_components.bticino_v1.const import DOMAIN


MODULES = {
    "gateway-id-001": {"id": "gateway-id-001", "device": "gateway", "firmwareVersion": "1.5.8", "deviceType": "C1X"},
    "lock-id-001": {"id": "lock-id-001", "device": "lock", "name": "A-Door"},
    "light-id-001": {"id": "light-id-001", "device": "light", "name": "Staircase Lights", "status": "off"},
}


@pytest.fixture
def mock_coordinator():
    coordinator = MagicMock()
    coordinator.data = {
        "modules": MODULES,
        "gateway_id": "gateway-id-001",
        "plant_id": "plant-id-001",
    }
    coordinator.gateway_id = "gateway-id-001"
    coordinator.last_update_success = True
    coordinator.async_set_light = AsyncMock()
    coordinator.async_open_lock = AsyncMock()
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    return coordinator


@pytest.fixture
def mock_entry_no_light_as_lock():
    entry = MagicMock()
    entry.entry_id = "test_entry_id_001"
    entry.options = {"light_as_lock": False}
    return entry


@pytest.fixture
def mock_entry_light_as_lock():
    entry = MagicMock()
    entry.entry_id = "test_entry_id_001"
    entry.options = {"light_as_lock": True}
    return entry


def test_light_created_for_light_modules(mock_coordinator, mock_entry_no_light_as_lock):
    """async_setup_entry must create BticinoV1Light for device=='light' modules."""
    entities = []
    async_add = MagicMock(side_effect=lambda e: entities.extend(e))
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id_001": {"coordinator": mock_coordinator}}}
    
    asyncio.get_event_loop().run_until_complete(
        async_setup_entry(hass, mock_entry_no_light_as_lock, async_add)
    )
    
    assert len(entities) == 1
    assert isinstance(entities[0], BticinoV1Light)
    assert entities[0]._module_id == "light-id-001"


def test_light_as_lock_created_when_option_true(mock_coordinator, mock_entry_light_as_lock):
    """With light_as_lock=True, must create BticinoV1LightAsLock instead of BticinoV1Light."""
    entities = []
    async_add = MagicMock(side_effect=lambda e: entities.extend(e))
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id_001": {"coordinator": mock_coordinator}}}
    
    asyncio.get_event_loop().run_until_complete(
        async_setup_entry(hass, mock_entry_light_as_lock, async_add)
    )
    
    assert len(entities) == 1
    assert isinstance(entities[0], BticinoV1LightAsLock)


def test_light_as_lock_not_created_when_option_false(mock_coordinator, mock_entry_no_light_as_lock):
    """With light_as_lock=False, must NOT create BticinoV1LightAsLock."""
    entities = []
    async_add = MagicMock(side_effect=lambda e: entities.extend(e))
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id_001": {"coordinator": mock_coordinator}}}
    
    asyncio.get_event_loop().run_until_complete(
        async_setup_entry(hass, mock_entry_no_light_as_lock, async_add)
    )
    
    assert not any(isinstance(e, BticinoV1LightAsLock) for e in entities)


@pytest.mark.asyncio
async def test_light_turn_on_calls_coordinator(mock_coordinator, mock_entry_no_light_as_lock):
    """async_turn_on must call coordinator.async_set_light(module_id, True)."""
    light = BticinoV1Light(mock_coordinator, mock_entry_no_light_as_lock, "light-id-001")
    light.hass = MagicMock()
    light.async_write_ha_state = MagicMock()
    
    await light.async_turn_on()
    
    mock_coordinator.async_set_light.assert_called_once_with("light-id-001", True)


@pytest.mark.asyncio
async def test_light_turn_off_calls_coordinator(mock_coordinator, mock_entry_no_light_as_lock):
    """async_turn_off must call coordinator.async_set_light(module_id, False)."""
    light = BticinoV1Light(mock_coordinator, mock_entry_no_light_as_lock, "light-id-001")
    light.hass = MagicMock()
    light.async_write_ha_state = MagicMock()
    
    await light.async_turn_off()
    
    mock_coordinator.async_set_light.assert_called_once_with("light-id-001", False)


@pytest.mark.asyncio
async def test_light_as_lock_unlock_calls_set_light_on(mock_coordinator, mock_entry_light_as_lock):
    """BticinoV1LightAsLock.async_unlock must call coordinator.async_set_light(module_id, True)."""
    light_lock = BticinoV1LightAsLock(mock_coordinator, mock_entry_light_as_lock, "light-id-001")
    light_lock.hass = MagicMock()
    light_lock.async_write_ha_state = MagicMock()
    
    with patch("custom_components.bticino_v1.light.async_call_later", return_value=lambda: None):
        await light_lock.async_unlock()
    
    mock_coordinator.async_set_light.assert_called_once_with("light-id-001", True)
