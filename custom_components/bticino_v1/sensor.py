# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportUntypedBaseClass=false, reportUnannotatedClassAttribute=false, reportUnusedImport=false
"""Sensor platform for BTicino Door Entry v1 — gateway diagnostics."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, COORDINATOR_KEY
from .coordinator import BticinoV1Coordinator
from .entity import BticinoV1Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BticinoV1Coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR_KEY]
    gateway_id = coordinator.gateway_id
    if not gateway_id:
        return
    gateway_data = coordinator.data.get("modules", {}).get(gateway_id)
    if not gateway_data:
        return
    async_add_entities([
        BticinoV1FirmwareSensor(coordinator, entry, gateway_id),
        BticinoV1IpSensor(coordinator, entry, gateway_id),
        BticinoV1ConnectionSensor(coordinator, entry, gateway_id),
    ])


class _GatewaySensor(BticinoV1Entity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _gateway_field: str = ""

    def __init__(self, coordinator: BticinoV1Coordinator, entry: ConfigEntry, module_id: str) -> None:
        super().__init__(coordinator, entry, module_id)

    @property
    def entity_category(self) -> EntityCategory:
        return EntityCategory.DIAGNOSTIC

    @property
    def state(self) -> str | None:
        module = self.coordinator.data.get("modules", {}).get(self._module_id, {})
        return module.get(self._gateway_field)


class BticinoV1FirmwareSensor(_GatewaySensor):
    _gateway_field = "firmwareVersion"

    def __init__(self, coordinator: BticinoV1Coordinator, entry: ConfigEntry, module_id: str) -> None:
        super().__init__(coordinator, entry, module_id)
        self._attr_unique_id = f"{entry.entry_id}_sensor_firmware_{module_id}"
        self._attr_name = "Firmware Version"


class BticinoV1IpSensor(_GatewaySensor):
    _gateway_field = "ipAddress"

    def __init__(self, coordinator: BticinoV1Coordinator, entry: ConfigEntry, module_id: str) -> None:
        super().__init__(coordinator, entry, module_id)
        self._attr_unique_id = f"{entry.entry_id}_sensor_ip_{module_id}"
        self._attr_name = "IP Address"


class BticinoV1ConnectionSensor(_GatewaySensor):
    _gateway_field = "connectionState"

    def __init__(self, coordinator: BticinoV1Coordinator, entry: ConfigEntry, module_id: str) -> None:
        super().__init__(coordinator, entry, module_id)
        self._attr_unique_id = f"{entry.entry_id}_sensor_connection_{module_id}"
        self._attr_name = "Connection State"
