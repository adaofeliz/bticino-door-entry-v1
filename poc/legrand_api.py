from __future__ import annotations
import logging
from typing import Any
import aiohttp
from .auth import AuthHandler, AuthError

_LOGGER = logging.getLogger(__name__)

_API_BASE         = "https://api.developer.legrand.com"
_CATALOG_V3       = f"{_API_BASE}/servicecatalog/api/v3.0"
_DEVMGMT_V2       = f"{_API_BASE}/devicemanagement/api/v2.0"
_VDE_SIP_V1       = f"{_API_BASE}/vde/sip/v1.0"
# Lock ticket endpoint found in decompiled APK (also confirmed via Legrand developer forum)
_VDEPRODUCTS_LOCK = (
    f"{_API_BASE}/vdeproducts/v1.0/lock/automation"
    "/addressLocation/plants/{plant_id}/modules/parameter/id/value/{module_id}/ticket"
)


class ApiError(Exception):
    def __init__(self, status: int, body: Any) -> None:
        super().__init__(f"[{status}] {body}")
        self.status = status
        self.body   = body


class LegrandApiClient:
    def __init__(self, auth: AuthHandler, session: aiohttp.ClientSession | None = None) -> None:
        self._auth       = auth
        self._session    = session
        self._owns_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session    = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, url: str) -> Any:
        token   = await self._auth.get_access_token()
        session = await self._get_session()
        _LOGGER.debug("GET %s", url)
        async with session.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            body = await resp.json(content_type=None)
            if resp.status >= 400:
                raise ApiError(resp.status, body)
            return body

    async def _post(self, url: str, payload: dict | None = None) -> Any:
        token   = await self._auth.get_access_token()
        session = await self._get_session()
        _LOGGER.debug("POST %s  body=%s", url, payload)
        async with session.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
            },
            json=payload or {},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status == 204:
                return {}
            body = await resp.json(content_type=None)
            if resp.status >= 400:
                raise ApiError(resp.status, body)
            return body

    # ------------------------------------------------------------------ discovery

    async def get_plants(self) -> list[dict]:
        data = await self._get(f"{_CATALOG_V3}/plants")
        plants = data if isinstance(data, list) else data.get("plants", data.get("value", []))
        _LOGGER.info("Found %d plant(s)", len(plants))
        return plants

    async def get_modules(self, plant_id: str) -> list[dict]:
        data = await self._get(f"{_CATALOG_V3}/plants/{plant_id}/modules")
        modules = data if isinstance(data, list) else data.get("modules", data.get("value", []))
        _LOGGER.info("Plant %s — %d module(s)", plant_id, len(modules))
        return modules

    async def get_topology(self, plant_id: str) -> dict:
        return await self._get(f"{_CATALOG_V3}/plants/{plant_id}/topology")

    # ------------------------------------------------------------------ SIP accounts
    # Returns: [{sipUri, sipPassword, username, plantId, deviceId, clientId, …}]

    async def get_sip_accounts(self, device_id: str) -> list[dict]:
        data = await self._get(f"{_VDE_SIP_V1}/devices/{device_id}/sipaccounts")
        accounts = data if isinstance(data, list) else data.get("value", [data])
        _LOGGER.info("Device %s — %d SIP account(s)", device_id, len(accounts))
        return accounts

    # ------------------------------------------------------------------ door control

    async def open_lock(self, plant_id: str, module_id: str) -> dict:
        url = _VDEPRODUCTS_LOCK.format(plant_id=plant_id, module_id=module_id)
        _LOGGER.info("Opening lock — plant=%s  module=%s", plant_id, module_id)
        return await self._post(url)

    async def get_firmware(self, device_id: str) -> dict:
        return await self._get(f"{_DEVMGMT_V2}/modules/{device_id}/firmware")
