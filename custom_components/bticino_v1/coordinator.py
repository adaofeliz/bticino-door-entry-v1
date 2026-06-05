from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LegrandApiClientV1, ApiError
from .auth import AuthHandler, AuthError
from .const import DOMAIN, UPDATE_INTERVAL, DEVICE_TYPE_GATEWAY

_LOGGER = logging.getLogger(__name__)


class BticinoV1Coordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        auth: AuthHandler,
        api: LegrandApiClientV1,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} coordinator - {entry.entry_id}",
            update_interval=timedelta(minutes=UPDATE_INTERVAL),
        )
        self._entry = entry
        self._auth = auth
        self._api = api
        self._plant_id: str = entry.data["home_id"]
        self._gateway_id: str | None = entry.data.get("gateway_id")

    @property
    def gateway_id(self) -> str | None:
        return self._gateway_id

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            modules_list = await self._api.get_modules(self._plant_id)
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ApiError as err:
            if self.data:
                _LOGGER.warning("Transient API error (%s), keeping last data", err)
                return self.data
            raise UpdateFailed(str(err)) from err

        modules_dict = {m["id"]: m for m in modules_list}

        for module in modules_list:
            if module.get("device") == DEVICE_TYPE_GATEWAY:
                self._gateway_id = module["id"]
                break

        return {
            "modules": modules_dict,
            "gateway_id": self._gateway_id,
            "plant_id": self._plant_id,
        }

    async def async_open_lock(self, module_id: str) -> None:
        if not self._gateway_id:
            _LOGGER.error("Cannot open lock: gateway_id not known")
            return
        await self._api.open_lock(self._gateway_id, module_id)

    async def async_set_light(self, module_id: str, on: bool) -> None:
        if not self._gateway_id:
            _LOGGER.error("Cannot set light: gateway_id not known")
            return
        await self._api.set_light(self._gateway_id, module_id, on)
