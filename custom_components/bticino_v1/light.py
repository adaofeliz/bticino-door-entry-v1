"""Light platform for BTicino Door Entry v1."""

# pyright: reportMissingImports=false, reportExplicitAny=false
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import LightEntity
from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import COORDINATOR_KEY, DEVICE_TYPE_LIGHT, DOMAIN, LOCK_RELOCK_DELAY
from .coordinator import BticinoV1Coordinator
from .entity import BticinoV1Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BticinoV1Coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR_KEY]
    light_as_lock = entry.options.get("light_as_lock", False)
    entities = []
    for module_id, module in coordinator.data.get("modules", {}).items():
        if module.get("device") == DEVICE_TYPE_LIGHT:
            if light_as_lock:
                entities.append(BticinoV1LightAsLock(coordinator, entry, module_id))
            else:
                entities.append(BticinoV1Light(coordinator, entry, module_id))
    async_add_entities(entities)


class BticinoV1Light(BticinoV1Entity, LightEntity):
    def __init__(self, coordinator: BticinoV1Coordinator, entry: ConfigEntry, module_id: str) -> None:
        super().__init__(coordinator, entry, module_id)
        self._attr_unique_id = f"{entry.entry_id}_light_{module_id}"
        module = coordinator.data.get("modules", {}).get(module_id, {})
        self._attr_name = module.get("name", "Light")

    @property
    def is_on(self) -> bool:
        module = self.coordinator.data.get("modules", {}).get(self._module_id, {})
        return module.get("status") == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_light(self._module_id, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_light(self._module_id, False)
        self.async_write_ha_state()


class BticinoV1LightAsLock(BticinoV1Entity, LockEntity):
    _attr_supported_features = LockEntityFeature.OPEN

    def __init__(self, coordinator: BticinoV1Coordinator, entry: ConfigEntry, module_id: str) -> None:
        super().__init__(coordinator, entry, module_id)
        self._attr_unique_id = f"{entry.entry_id}_light_lock_{module_id}"
        module = coordinator.data.get("modules", {}).get(module_id, {})
        self._attr_name = f"{module.get('name', 'Light')} Lock"
        self._is_locked = True
        self._relock_cancel = None

    @property
    def is_locked(self) -> bool:
        return self._is_locked

    async def async_unlock(self, **kwargs: Any) -> None:
        if self._relock_cancel:
            self._relock_cancel()
            self._relock_cancel = None
        self._is_locked = False
        self.async_write_ha_state()
        self._relock_cancel = async_call_later(self.hass, LOCK_RELOCK_DELAY, self._relock_cb)
        try:
            await self.coordinator.async_set_light(self._module_id, True)
        except Exception as err:
            _LOGGER.error("Failed to unlock light %s: %s", self._module_id, err)
            if self._relock_cancel:
                self._relock_cancel()
                self._relock_cancel = None
            self._is_locked = True
            self.async_write_ha_state()

    @callback
    def _relock_cb(self, *args: Any) -> None:
        self._relock_cancel = None
        self._is_locked = True
        self.async_write_ha_state()
