"""Tests for BticinoV1Lock."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.lock import LockEntityFeature

from custom_components.bticino_v1.lock import BticinoV1Lock, async_setup_entry
from custom_components.bticino_v1.const import DOMAIN, DEVICE_TYPE_LOCK, LOCK_RELOCK_DELAY


LOCK_MODULES = {
    "gateway-id-001": {"id": "gateway-id-001", "device": "gateway", "firmwareVersion": "1.5.8", "deviceType": "C1X"},
    "lock-id-001": {"id": "lock-id-001", "device": "lock", "name": "A-Door", "deviceType": "Lock", "status": "registered"},
    "lock-id-002": {"id": "lock-id-002", "device": "lock", "name": "Gate", "deviceType": "Lock", "status": "registered"},
    "light-id-001": {"id": "light-id-001", "device": "light", "name": "Staircase", "deviceType": "Staircase"},
    "eu-id-001": {"id": "eu-id-001", "device": "audioVideoTerminal", "name": "A-Door", "deviceType": "EU"},
}


@pytest.fixture
def mock_coordinator():
    coordinator = MagicMock()
    coordinator.data = {
        "modules": LOCK_MODULES,
        "gateway_id": "gateway-id-001",
        "plant_id": "plant-id-001",
    }
    coordinator.gateway_id = "gateway-id-001"
    coordinator.last_update_success = True
    coordinator.async_open_lock = AsyncMock()
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    return coordinator


@pytest.fixture
def mock_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry_id_001"
    entry.options = {"light_as_lock": False}
    return entry


def test_lock_created_for_lock_modules_only(mock_coordinator, mock_entry):
    """async_setup_entry must create lock entities only for device=='lock' modules."""
    entities = []
    async_add = MagicMock(side_effect=lambda e: entities.extend(e))
    
    import asyncio
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id_001": {"coordinator": mock_coordinator}}}
    
    asyncio.get_event_loop().run_until_complete(
        async_setup_entry(hass, mock_entry, async_add)
    )
    
    assert len(entities) == 2  # lock-id-001 and lock-id-002
    entity_module_ids = {e._module_id for e in entities}
    assert "lock-id-001" in entity_module_ids
    assert "lock-id-002" in entity_module_ids


def test_lock_not_created_for_gateway_modules(mock_coordinator, mock_entry):
    """No lock entity must be created for gateway, light, or EU modules."""
    entities = []
    async_add = MagicMock(side_effect=lambda e: entities.extend(e))
    
    import asyncio
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id_001": {"coordinator": mock_coordinator}}}
    
    asyncio.get_event_loop().run_until_complete(
        async_setup_entry(hass, mock_entry, async_add)
    )
    
    module_ids = {e._module_id for e in entities}
    assert "gateway-id-001" not in module_ids
    assert "light-id-001" not in module_ids
    assert "eu-id-001" not in module_ids


def test_lock_unique_id_format(mock_coordinator, mock_entry):
    """Lock unique_id must be f'{entry_id}_lock_{module_id}'."""
    lock = BticinoV1Lock(mock_coordinator, mock_entry, "lock-id-001")
    assert lock.unique_id == "test_entry_id_001_lock_lock-id-001"


@pytest.mark.asyncio
async def test_async_unlock_calls_coordinator_open_lock(mock_coordinator, mock_entry):
    """async_unlock must call coordinator.async_open_lock with the module_id."""
    lock = BticinoV1Lock(mock_coordinator, mock_entry, "lock-id-001")
    lock.hass = MagicMock()
    lock.hass.loop = MagicMock()
    lock.async_write_ha_state = MagicMock()
    
    with patch("custom_components.bticino_v1.lock.async_call_later", return_value=lambda: None):
        await lock.async_unlock()
    
    mock_coordinator.async_open_lock.assert_called_once_with("lock-id-001")


@pytest.mark.asyncio
async def test_async_unlock_sets_optimistic_unlocked_state(mock_coordinator, mock_entry):
    """After async_unlock, is_locked must be False (optimistic)."""
    lock = BticinoV1Lock(mock_coordinator, mock_entry, "lock-id-001")
    lock.hass = MagicMock()
    lock.async_write_ha_state = MagicMock()
    
    assert lock.is_locked is True  # default locked
    
    with patch("custom_components.bticino_v1.lock.async_call_later", return_value=lambda: None):
        await lock.async_unlock()
    
    assert lock.is_locked is False


@pytest.mark.asyncio
async def test_async_unlock_schedules_relock(mock_coordinator, mock_entry):
    """async_unlock must schedule a relock via async_call_later."""
    lock = BticinoV1Lock(mock_coordinator, mock_entry, "lock-id-001")
    lock.hass = MagicMock()
    lock.async_write_ha_state = MagicMock()
    
    with patch("custom_components.bticino_v1.lock.async_call_later") as mock_call_later:
        mock_call_later.return_value = lambda: None
        await lock.async_unlock()
    
    mock_call_later.assert_called_once()
    args = mock_call_later.call_args
    assert args[0][1] == LOCK_RELOCK_DELAY  # second arg is delay


def test_lock_unavailable_when_coordinator_fails(mock_coordinator, mock_entry):
    """Lock must be unavailable when coordinator.last_update_success is False."""
    mock_coordinator.last_update_success = False
    lock = BticinoV1Lock(mock_coordinator, mock_entry, "lock-id-001")
    assert lock.available is False


@pytest.mark.asyncio
async def test_lock_handles_api_error_without_crash(mock_coordinator, mock_entry):
    """async_unlock must not crash if coordinator raises an exception."""
    from custom_components.bticino_v1.api import ApiError
    mock_coordinator.async_open_lock = AsyncMock(side_effect=ApiError(500, "Server Error"))
    
    lock = BticinoV1Lock(mock_coordinator, mock_entry, "lock-id-001")
    lock.hass = MagicMock()
    lock.async_write_ha_state = MagicMock()
    
    with patch("custom_components.bticino_v1.lock.async_call_later", return_value=lambda: None):
        # Must not raise
        await lock.async_unlock()
    
    # State should be reset to locked after error
    assert lock.is_locked is True
