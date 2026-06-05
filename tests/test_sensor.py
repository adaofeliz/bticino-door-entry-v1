# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUntypedFunctionDecorator=false, reportUnknownLambdaType=false, reportUnknownArgumentType=false
"""Tests for gateway diagnostics sensors."""
"""Tests for gateway diagnostics sensors."""
import pytest
import asyncio
from unittest.mock import MagicMock

from homeassistant.helpers.entity import EntityCategory

from custom_components.bticino_v1.sensor import (
    BticinoV1FirmwareSensor,
    BticinoV1IpSensor,
    BticinoV1ConnectionSensor,
    async_setup_entry,
)
from custom_components.bticino_v1.const import DOMAIN


GATEWAY_MODULE = {
    "id": "gateway-id-001",
    "device": "gateway",
    "firmwareVersion": "1.5.8",
    "ipAddress": "192.168.0.1",
    "connectionState": "CONNECTED",
    "deviceType": "C1X",
}


@pytest.fixture
def mock_coordinator():
    coordinator = MagicMock()
    coordinator.data = {
        "modules": {"gateway-id-001": GATEWAY_MODULE},
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


def test_firmware_sensor_state_from_coordinator(mock_coordinator, mock_entry):
    """Firmware sensor state must equal gateway firmwareVersion."""
    sensor = BticinoV1FirmwareSensor(mock_coordinator, mock_entry, "gateway-id-001")
    assert sensor.state == "1.5.8"


def test_ip_sensor_state_from_coordinator(mock_coordinator, mock_entry):
    """IP sensor state must equal gateway ipAddress."""
    sensor = BticinoV1IpSensor(mock_coordinator, mock_entry, "gateway-id-001")
    assert sensor.state == "192.168.0.1"


def test_connection_sensor_state_connected(mock_coordinator, mock_entry):
    """Connection sensor state must equal gateway connectionState."""
    sensor = BticinoV1ConnectionSensor(mock_coordinator, mock_entry, "gateway-id-001")
    assert sensor.state == "CONNECTED"


def test_sensors_are_diagnostic_category(mock_coordinator, mock_entry):
    """All gateway sensors must have EntityCategory.DIAGNOSTIC."""
    for SensorClass in [
        BticinoV1FirmwareSensor,
        BticinoV1IpSensor,
        BticinoV1ConnectionSensor,
    ]:
        sensor = SensorClass(mock_coordinator, mock_entry, "gateway-id-001")
        assert sensor.entity_category == EntityCategory.DIAGNOSTIC


def test_sensors_unavailable_when_no_gateway(mock_coordinator, mock_entry):
    """Sensors must be unavailable when coordinator has no gateway data."""
    mock_coordinator.data = {"modules": {}, "gateway_id": None, "plant_id": "plant-id-001"}
    mock_coordinator.gateway_id = None
    
    entities = []
    async_add = MagicMock(side_effect=lambda e: entities.extend(e))
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry_id_001": {"coordinator": mock_coordinator}}}
    
    asyncio.get_event_loop().run_until_complete(
        async_setup_entry(hass, mock_entry, async_add)
    )
    
    assert len(entities) == 0
