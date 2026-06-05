"""BTicino Door Entry v1 — Home Assistant integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.storage import Store

from .api import LegrandApiClientV1
from .auth import AuthError, AuthHandler
from .const import (
    API_KEY,
    AUTH_KEY,
    COORDINATOR_KEY,
    DOMAIN,
    PLATFORMS,
    TOKEN_STORAGE_VERSION,
)
from .coordinator import BticinoV1Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    token_store = Store(hass, TOKEN_STORAGE_VERSION, f"{DOMAIN}.tokens.{entry.entry_id}")

    async def _save_tokens(token_data: dict) -> None:
        await token_store.async_save(token_data)

    auth = AuthHandler(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        token_callback=_save_tokens,
    )

    saved = await token_store.async_load()
    if saved:
        auth.set_tokens(
            access_token=saved["access_token"],
            refresh_token=saved.get("refresh_token"),
            expires_at=saved.get("expires_at", 0.0),
        )

    try:
        await auth.get_access_token()
    except AuthError as err:
        await auth.close()
        raise ConfigEntryAuthFailed(str(err)) from err

    api = LegrandApiClientV1(auth)
    coordinator = BticinoV1Coordinator(hass, entry, auth, api)

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await auth.close()
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR_KEY: coordinator,
        AUTH_KEY: auth,
        API_KEY: api,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        auth: AuthHandler = entry_data.get(AUTH_KEY)
        if auth:
            await auth.close()
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    token_store = Store(hass, TOKEN_STORAGE_VERSION, f"{DOMAIN}.tokens.{entry.entry_id}")
    await token_store.async_remove()
