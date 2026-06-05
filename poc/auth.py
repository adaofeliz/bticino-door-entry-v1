"""
Azure B2C ROPC authentication for Legrand Eliot / BTicino CLASSE100X (firmware v1).

Constants from decompiled APK: com.legrandgroup.c100x v1.8.2, class k3/C1818b.java.

ROPC (Resource Owner Password Credentials) lets us authenticate with email+password
directly. Azure B2C ROPC differs from standard OAuth2: the policy name is appended
as a query param (?p=<policy>) on the token endpoint.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

# From k3/C1818b.java in the decompiled APK
_TENANT    = "EliotClouduamprd.onmicrosoft.com"
_BASE      = "https://eliotclouduamprd.b2clogin.com"
_POLICY    = "B2C_1_DoorEliot-C100X-SignUporSignIn"
_CLIENT_ID = "c7d272d9-e76a-41b7-824f-a988ad964cf8"
_SCOPE     = (
    "https://EliotClouduamprd.onmicrosoft.com/security/access.full "
    "offline_access openid"
)
# Azure B2C ROPC endpoint — policy in query string (B2C-specific, not standard OAuth2)
_TOKEN_URL = f"{_BASE}/{_TENANT}/oauth2/v2.0/token?p={_POLICY}"

_REFRESH_BUFFER_SECS = 300  # refresh 5 min before expiry


class AuthError(Exception):
    pass


class AuthHandler:
    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._username = username
        self._password = password
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float | None = None
        self._session = session
        self._owns_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    def _is_expired(self) -> bool:
        if not self._expires_at:
            return True
        return time.time() >= (self._expires_at - _REFRESH_BUFFER_SECS)

    def _store_tokens(self, data: dict[str, Any]) -> None:
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token")
        expires_in = data.get("expires_in")
        self._expires_at = time.time() + int(expires_in) if expires_in else None

    async def authenticate(self) -> None:
        session = await self._get_session()
        payload = {
            "grant_type": "password",
            "client_id": _CLIENT_ID,
            "username": self._username,
            "password": self._password,
            "scope": _SCOPE,
            "response_type": "token",
        }
        async with session.post(
            _TOKEN_URL,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            body = await resp.json(content_type=None)
            if resp.status >= 400:
                err  = body.get("error", "unknown")
                desc = body.get("error_description", str(body))
                raise AuthError(f"[{resp.status}] {err}: {desc}")
            self._store_tokens(body)
            _LOGGER.info("Authenticated as %s", self._username)

    async def _do_refresh(self) -> None:
        if not self._refresh_token:
            await self.authenticate()
            return
        session = await self._get_session()
        payload = {
            "grant_type": "refresh_token",
            "client_id": _CLIENT_ID,
            "refresh_token": self._refresh_token,
            "scope": _SCOPE,
        }
        async with session.post(
            _TOKEN_URL,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            body = await resp.json(content_type=None)
            if resp.status >= 400:
                _LOGGER.warning("Refresh failed (%s), re-authenticating", resp.status)
                self._refresh_token = None
                await self.authenticate()
                return
            self._store_tokens(body)
            _LOGGER.debug("Token refreshed")

    async def get_access_token(self) -> str:
        if self._is_expired():
            await self._do_refresh() if self._refresh_token else await self.authenticate()
        if not self._access_token:
            raise AuthError("No access token after auth")
        return self._access_token
