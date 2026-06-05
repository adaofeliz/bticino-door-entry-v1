"""Tests for BticinoV1Entity base class."""
import pytest
from unittest.mock import MagicMock

from custom_components.bticino_v1.entity import BticinoV1Entity
from custom_components.bticino_v1.const import DOMAIN


class ConcreteEntity(BticinoV1Entity):
    """Concrete subclass for testing the abstract base."""
    pass


@pytest.fixture
def mock_coordinator():
    coordinator = MagicMock()
    coordinator.data = {
        "modules": {
            "gateway-id-001": {
                "id": "gateway-id-001",
                "device": "gateway",
                "firmwareVersion": "1.5.8",
                "deviceType": "C1X",
                "name": "",
            },
            "lock-id-001": {
                "id": "lock-id-001",
                "device": "lock",
                "name": "A-Door",
            },
        },
        "gateway_id": "gateway-id-001",
        "plant_id": "plant-id-001",
    }
    coordinator.gateway_id = "gateway-id-001"
    coordinator.last_update_success = True
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    return coordinator


@pytest.fixture
def mock_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry_id_001"
    return entry


def test_entity_has_entity_name_true(mock_coordinator, mock_entry):
    """_attr_has_entity_name must be True."""
    entity = ConcreteEntity(mock_coordinator, mock_entry, "lock-id-001")
    assert entity._attr_has_entity_name is True


def test_device_info_anchors_to_gateway(mock_coordinator, mock_entry):
    """device_info identifiers must use DOMAIN and gateway_id."""
    entity = ConcreteEntity(mock_coordinator, mock_entry, "lock-id-001")
    device_info = entity.device_info
    assert (DOMAIN, "gateway-id-001") in device_info["identifiers"]


def test_device_info_includes_firmware_version(mock_coordinator, mock_entry):
    """device_info sw_version must come from gateway module firmwareVersion."""
    entity = ConcreteEntity(mock_coordinator, mock_entry, "lock-id-001")
    device_info = entity.device_info
    assert device_info.get("sw_version") == "1.5.8"


def test_unique_id_uses_entry_id_and_module_id(mock_coordinator, mock_entry):
    """unique_id base must be f'{entry_id}_{module_id}'."""
    entity = ConcreteEntity(mock_coordinator, mock_entry, "lock-id-001")
    assert entity.unique_id == "test_entry_id_001_lock-id-001"
