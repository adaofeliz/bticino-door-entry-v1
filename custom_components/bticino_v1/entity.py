"""Base entity for BTicino Door Entry v1 devices."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BticinoV1Coordinator


class BticinoV1Entity(CoordinatorEntity[BticinoV1Coordinator]):
    """Base entity — all BTicino v1 entities inherit from this."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BticinoV1Coordinator,
        entry,
        module_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._module_id = module_id
        self._attr_unique_id = f"{entry.entry_id}_{module_id}"

    @property
    def device_info(self) -> DeviceInfo:
        gateway_id = self.coordinator.gateway_id or ""
        gateway_data = self.coordinator.data.get("modules", {}).get(gateway_id, {})
        return DeviceInfo(
            identifiers={(DOMAIN, gateway_id)},
            name="BTicino Door Entry v1",
            manufacturer="BTicino",
            model=gateway_data.get("deviceType"),
            sw_version=gateway_data.get("firmwareVersion"),
        )
