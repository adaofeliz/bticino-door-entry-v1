from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.selector import BooleanSelector

from .api import ApiError, LegrandApiClientV1
from .auth import AuthError, AuthHandler
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

_STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)

_STEP_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required("light_as_lock", default=False): BooleanSelector(),
    }
)


class BticinoV1ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1

    def __init__(self) -> None:
        self._username: str | None = None
        self._password: str | None = None
        self._plants: list[dict] = []
        self._home_id: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=_STEP_USER_SCHEMA)

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        auth = AuthHandler(username, password)
        try:
            await auth.authenticate()
        except AuthError:
            await auth.close()
            return self.async_show_form(
                step_id="user",
                data_schema=_STEP_USER_SCHEMA,
                errors={"base": "invalid_auth"},
            )
        except Exception as exc:
            _LOGGER.exception("Unexpected error during authentication: %s", exc)
            await auth.close()
            return self.async_show_form(
                step_id="user",
                data_schema=_STEP_USER_SCHEMA,
                errors={"base": "cannot_connect"},
            )

        api = LegrandApiClientV1(auth)
        try:
            plants = await api.get_plants()
        except ApiError:
            await api.close()
            await auth.close()
            return self.async_show_form(
                step_id="user",
                data_schema=_STEP_USER_SCHEMA,
                errors={"base": "cannot_connect"},
            )

        await api.close()
        await auth.close()

        if not plants:
            return self.async_abort(reason="no_plants_found")

        await self.async_set_unique_id(username)
        self._abort_if_unique_id_configured()

        self._username = username
        self._password = password
        self._plants = plants

        if len(plants) == 1:
            self._home_id = plants[0]["id"]
            return await self.async_step_init_options()

        return await self.async_step_select_home()

    async def async_step_select_home(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            self._home_id = user_input["home_id"]
            return await self.async_step_init_options()

        plant_options = {p["id"]: p["name"] for p in self._plants}
        schema = vol.Schema({vol.Required("home_id"): vol.In(plant_options)})
        return self.async_show_form(step_id="select_home", data_schema=schema)

    async def async_step_init_options(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="init_options", data_schema=_STEP_OPTIONS_SCHEMA
            )

        light_as_lock = user_input.get("light_as_lock", False)

        gateway_id: str | None = None
        auth = AuthHandler(self._username, self._password)
        try:
            await auth.authenticate()
            api = LegrandApiClientV1(auth)
            try:
                modules = await api.get_modules(self._home_id)
                for module in modules:
                    if module.get("device") == "gateway":
                        gateway_id = module["id"]
                        break
            finally:
                await api.close()
        except Exception:
            _LOGGER.warning("Could not retrieve gateway_id during setup")
        finally:
            await auth.close()

        return self.async_create_entry(
            title=self._username,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                "home_id": self._home_id,
                "gateway_id": gateway_id,
            },
            options={"light_as_lock": light_as_lock},
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=_STEP_REAUTH_SCHEMA
            )

        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        username = entry.data[CONF_USERNAME]
        new_password = user_input[CONF_PASSWORD]

        auth = AuthHandler(username, new_password)
        try:
            await auth.authenticate()
        except AuthError:
            await auth.close()
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=_STEP_REAUTH_SCHEMA,
                errors={"base": "invalid_auth"},
            )
        except Exception as exc:
            _LOGGER.exception("Unexpected error during reauth: %s", exc)
            await auth.close()
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=_STEP_REAUTH_SCHEMA,
                errors={"base": "cannot_connect"},
            )

        await auth.close()

        self.hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_PASSWORD: new_password}
        )
        return self.async_abort(reason="reauth_successful")

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return BticinoV1OptionsFlowHandler()


class BticinoV1OptionsFlowHandler(config_entries.OptionsFlow):

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get("light_as_lock", False)
        schema = vol.Schema(
            {vol.Required("light_as_lock", default=current): BooleanSelector()}
        )
        return self.async_show_form(step_id="init", data_schema=schema)
