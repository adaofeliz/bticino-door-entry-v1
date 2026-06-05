from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import re
import secrets
import time
import urllib.parse
from typing import Any, Callable, Awaitable

import aiohttp

from .const import (
    B2C_BASE,
    B2C_TENANT,
    B2C_POLICY,
    B2C_CLIENT_ID,
    B2C_SCOPE,
    B2C_REDIRECT_URI,
    B2C_USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)

_REFRESH_BUFFER = 300


class AuthError(Exception):
    def __init__(self, message: str, last_html: str = "") -> None:
        super().__init__(message)
        self.last_html = last_html


class AuthHandler:
    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
        token_callback: Callable[[dict], Awaitable[None]] | None = None,
    ) -> None:
        self._username = username
        self._password = password
        self._session = session
        self._owns_session = session is None
        self._token_callback = token_callback
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float | None = None
        self._lock = asyncio.Lock()
        self._client_session: aiohttp.ClientSession | None = None

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is not None:
            return self._session
        if self._client_session is None or self._client_session.closed:
            self._client_session = aiohttp.ClientSession(
                headers={"User-Agent": B2C_USER_AGENT}
            )
        return self._client_session

    async def authenticate(self) -> None:
        verifier = secrets.token_urlsafe(32)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        csrf, trans_id, tenant = await self._scrape_authorize(verifier, challenge)
        await self._post_selfasserted(csrf, trans_id, tenant)
        code = await self._get_auth_code(csrf, trans_id, tenant)
        await self._exchange_code(code, verifier)

    async def _scrape_authorize(
        self, verifier: str, challenge: str
    ) -> tuple[str, str, str]:
        url = f"{B2C_BASE}/{B2C_TENANT}/oauth2/v2.0/authorize"
        params = {
            "p": B2C_POLICY,
            "client_id": B2C_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": B2C_REDIRECT_URI,
            "response_mode": "query",
            "scope": B2C_SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        session = self._get_session()
        async with session.get(url, params=params, allow_redirects=True) as resp:
            html = await resp.text()

        csrf_match = re.search(r'"csrf":"([^"]+)"', html)
        if not csrf_match:
            raise AuthError("csrf_not_found", last_html=html)
        csrf = csrf_match.group(1)

        trans_id_match = re.search(r'"transId":"([^"]+)"', html)
        if not trans_id_match:
            raise AuthError("transId_not_found", last_html=html)
        trans_id = trans_id_match.group(1)

        tenant_match = re.search(r'"hosts"\s*:\s*\{"tenant"\s*:\s*"([^"]+)"', html)
        if not tenant_match:
            raise AuthError("tenant_not_found", last_html=html)
        tenant = tenant_match.group(1)

        return csrf, trans_id, tenant

    async def _post_selfasserted(
        self, csrf: str, trans_id: str, tenant: str
    ) -> None:
        url = f"{B2C_BASE}{tenant}/SelfAsserted"
        params = {"tx": trans_id, "p": B2C_POLICY}
        headers = {"X-CSRF-TOKEN": csrf}
        data = (
            f"request_type=RESPONSE"
            f"&logonIdentifier={urllib.parse.quote(self._username, safe='')}"
            f"&password={urllib.parse.quote(self._password, safe='')}"
        )
        session = self._get_session()
        async with session.post(
            url, params=params, headers=headers, data=data
        ) as resp:
            body = await resp.json(content_type=None)

        status = str(body.get("status", ""))
        if status != "200":
            message = body.get("message", "")
            raise AuthError(f"invalid_credentials: status={status} {message}")

    async def _get_auth_code(
        self, csrf: str, trans_id: str, tenant: str
    ) -> str:
        url = f"{B2C_BASE}{tenant}/api/CombinedSigninAndSignup/confirmed"
        params = {"csrf_token": csrf, "tx": trans_id, "p": B2C_POLICY}
        session = self._get_session()
        async with session.get(
            url, params=params, allow_redirects=False
        ) as resp:
            location = resp.headers.get("Location", "")

        code_match = re.search(r"[?&]code=([^&]+)", location)
        if not code_match:
            raise AuthError(f"auth_code_not_found in Location: {location!r}")
        return code_match.group(1)

    async def _exchange_code(self, code: str, verifier: str) -> None:
        url = f"{B2C_BASE}/{B2C_TENANT}/oauth2/v2.0/token"
        params = {"p": B2C_POLICY}
        data = {
            "grant_type": "authorization_code",
            "client_id": B2C_CLIENT_ID,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": B2C_REDIRECT_URI,
            "scope": B2C_SCOPE,
        }
        session = self._get_session()
        async with session.post(url, params=params, data=data) as resp:
            token_data = await resp.json(content_type=None)

        self._store_tokens(token_data)
        if self._token_callback is not None:
            await self._token_callback(token_data)

    async def _do_refresh(self) -> None:
        url = f"{B2C_BASE}/{B2C_TENANT}/oauth2/v2.0/token"
        params = {"p": B2C_POLICY}
        data = {
            "grant_type": "refresh_token",
            "client_id": B2C_CLIENT_ID,
            "refresh_token": self._refresh_token,
            "scope": B2C_SCOPE,
            "redirect_uri": B2C_REDIRECT_URI,
        }
        session = self._get_session()
        try:
            async with session.post(url, params=params, data=data) as resp:
                if resp.status >= 400:
                    _LOGGER.warning(
                        "Token refresh failed (HTTP %s), falling back to full scrape",
                        resp.status,
                    )
                    self._refresh_token = None
                    await self.authenticate()
                    return
                token_data = await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            _LOGGER.warning("Token refresh error: %s, falling back to full scrape", exc)
            self._refresh_token = None
            await self.authenticate()
            return

        self._store_tokens(token_data)

    def _store_tokens(self, token_data: dict) -> None:
        self._access_token = token_data["access_token"]
        self._refresh_token = token_data.get("refresh_token")
        expires_in = int(token_data.get("expires_in", 3600))
        self._expires_at = time.time() + expires_in

    def set_tokens(
        self,
        access_token: str,
        refresh_token: str | None,
        expires_at: float,
    ) -> None:
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._expires_at = expires_at

    async def get_access_token(self) -> str:
        if (
            self._access_token is not None
            and self._expires_at is not None
            and time.time() < self._expires_at - _REFRESH_BUFFER
        ):
            return self._access_token

        async with self._lock:
            if (
                self._access_token is not None
                and self._expires_at is not None
                and time.time() < self._expires_at - _REFRESH_BUFFER
            ):
                return self._access_token

            if self._refresh_token:
                await self._do_refresh()
            else:
                await self.authenticate()

        return self._access_token  # type: ignore[return-value]

    async def close(self) -> None:
        if self._owns_session and self._client_session and not self._client_session.closed:
            await self._client_session.close()
