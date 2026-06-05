#!/usr/bin/env python3
"""
BTicino CLASSE100X PoC — tests auth + discovery + door open.

Usage:
  python -m poc.poc --email you@example.com --password secret
  python -m poc.poc --email you@example.com --password secret --open-door
  python -m poc.poc --email you@example.com --password secret --listen-rings
  python -m poc.poc --help

Steps performed:
  1. Authenticate against Legrand Azure B2C (ROPC)
  2. Discover plants and modules on your account
  3. Fetch SIP credentials for the found device
  4. (optional) Attempt to open the door via:
       a. Legrand cloud REST API  (--open-door)
       b. SIP MESSAGE to the gateway  (--open-door --sip)
  5. (optional) Listen for doorbell ring events via SIP INVITE  (--listen-rings)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

import aiohttp

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from poc.auth import AuthHandler, AuthError
from poc.legrand_api import LegrandApiClient, ApiError
from poc.sip_client import SipClient, SipCredentials

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
_LOGGER = logging.getLogger("poc")

_VDESIP_HOST = "vdesip.bs.iotleg.com"  # fallback remote SIP proxy from APK
_SIP_PORT    = 5228                      # from BTicino CLASSE100X device manual


def _pretty(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)


async def run(args: argparse.Namespace) -> None:
    async with aiohttp.ClientSession() as session:
        auth   = AuthHandler(args.email, args.password, session=session)
        client = LegrandApiClient(auth, session=session)

        # ── 1. Auth ─────────────────────────────────────────────────────
        _LOGGER.info("Authenticating …")
        await auth.authenticate()
        _LOGGER.info("✓ Authentication succeeded")

        # ── 2. Discover plants ───────────────────────────────────────────
        _LOGGER.info("Fetching plants …")
        try:
            plants = await client.get_plants()
        except ApiError as exc:
            _LOGGER.error("get_plants failed: %s", exc)
            _LOGGER.info("Trying topology via raw access_token dump …")
            plants = []

        if not plants:
            _LOGGER.warning("No plants returned — check account or API response shape")
            _LOGGER.info("Raw token info:")
            token = await auth.get_access_token()
            _LOGGER.info("  access_token[:60] = %s…", token[:60])
            return

        plant = plants[0]
        plant_id = plant.get("id") or plant.get("plantId") or plant.get("_id")
        _LOGGER.info("Using plant: %s  (id=%s)", plant.get("name", "?"), plant_id)
        if len(plants) > 1:
            _LOGGER.info("  (found %d plant(s) total — using first)", len(plants))

        # ── 3. Discover modules ──────────────────────────────────────────
        _LOGGER.info("Fetching modules …")
        try:
            modules = await client.get_modules(plant_id)
        except ApiError as exc:
            _LOGGER.error("get_modules failed (%s) — trying topology", exc)
            modules = []

        if not modules:
            _LOGGER.info("Trying topology endpoint …")
            try:
                topo = await client.get_topology(plant_id)
                _LOGGER.info("Topology raw:\n%s", _pretty(topo))
            except ApiError as exc:
                _LOGGER.error("get_topology failed: %s", exc)
            return

        _LOGGER.info("Modules found (%d):", len(modules))
        for m in modules:
            _LOGGER.info("  • %s", _pretty(m))

        # Pick the first module that looks like a door/intercom
        door_module = next(
            (m for m in modules if any(
                t in str(m).lower() for t in ("door", "lock", "bncx", "bnmh", "vde", "classe")
            )),
            modules[0],
        )
        module_id = door_module.get("id") or door_module.get("moduleId")
        _LOGGER.info("Using module: %s  (id=%s)", door_module.get("name", "?"), module_id)

        # ── 4. SIP accounts ──────────────────────────────────────────────
        _LOGGER.info("Fetching SIP accounts for device %s …", module_id)
        sip_creds_list: list[dict] = []
        try:
            sip_creds_list = await client.get_sip_accounts(module_id)
            _LOGGER.info("SIP accounts (%d):", len(sip_creds_list))
            for s in sip_creds_list:
                safe = {**s}
                if "sipPassword" in safe:
                    safe["sipPassword"] = "***"
                _LOGGER.info("  • %s", _pretty(safe))
        except ApiError as exc:
            _LOGGER.warning("get_sip_accounts failed: %s", exc)

        # ── 5. Open door ─────────────────────────────────────────────────
        if args.open_door:
            if args.sip and sip_creds_list:
                await _open_door_sip(sip_creds_list[0], plant_id)
            else:
                await _open_door_rest(client, plant_id, module_id)

        # ── 6. Listen for rings ──────────────────────────────────────────
        if args.listen_rings and sip_creds_list:
            await _listen_rings(sip_creds_list[0], plant_id)


async def _open_door_rest(client: LegrandApiClient, plant_id: str, module_id: str) -> None:
    _LOGGER.info("Opening door via REST API …")
    try:
        result = await client.open_lock(plant_id, module_id)
        _LOGGER.info("✓ open_lock response: %s", _pretty(result))
    except ApiError as exc:
        _LOGGER.error("open_lock REST failed: %s", exc)
        _LOGGER.info(
            "The REST endpoint may have been removed (Legrand deprecated it).\n"
            "Run with --sip to try the SIP MESSAGE path instead."
        )


async def _open_door_sip(raw: dict, plant_id: str) -> None:
    sip_uri  = raw.get("sipUri", "")
    password = raw.get("sipPassword", "")
    username = raw.get("username", "")
    device_id = raw.get("deviceId", "")

    if not sip_uri or not password:
        _LOGGER.error("SIP credentials incomplete: %s", raw)
        return

    creds = SipCredentials(
        sip_uri=sip_uri,
        password=password,
        username=username,
        plant_id=plant_id,
        device_id=device_id,
    )

    # Gateway host: from sipUri domain, or fallback to vdesip.bs.iotleg.com
    _, domain = sip_uri.removeprefix("sip:").partition("@")[::2]
    host = domain or _VDESIP_HOST

    _LOGGER.info("Connecting SIP to %s:%d …", host, _SIP_PORT)
    sip = SipClient(creds, plant_id=plant_id)
    try:
        await sip.connect(host, _SIP_PORT)
        _LOGGER.info("Waiting for SIP registration …")
        await sip.wait_registered(timeout=15.0)
        _LOGGER.info("Opening door via SIP MESSAGE …")
        await sip.open_door()
        await asyncio.sleep(2)  # wait for 200 OK
    except TimeoutError:
        _LOGGER.error("SIP registration timed out — check credentials/host")
    except Exception as exc:
        _LOGGER.error("SIP error: %s", exc)
    finally:
        sip.disconnect()


async def _listen_rings(raw: dict, plant_id: str) -> None:
    sip_uri  = raw.get("sipUri", "")
    password = raw.get("sipPassword", "")
    username = raw.get("username", "")
    device_id = raw.get("deviceId", "")

    if not sip_uri or not password:
        _LOGGER.error("SIP credentials incomplete")
        return

    creds = SipCredentials(sip_uri=sip_uri, password=password, username=username,
                           plant_id=plant_id, device_id=device_id)
    _, domain = sip_uri.removeprefix("sip:").partition("@")[::2]
    host = domain or _VDESIP_HOST

    _LOGGER.info("Listening for doorbell rings on %s:%d (Ctrl-C to stop) …", host, _SIP_PORT)
    sip = SipClient(creds, plant_id=plant_id)
    try:
        await sip.connect(host, _SIP_PORT)
        await sip.wait_registered(timeout=15.0)
        _LOGGER.info("✓ Registered — waiting for rings …")
        while True:
            event = await sip.ring_events.get()
            _LOGGER.info("🔔 RING EVENT: %s", event)
    except asyncio.CancelledError:
        pass
    except TimeoutError:
        _LOGGER.error("SIP registration timed out")
    finally:
        sip.disconnect()


def main() -> None:
    import os
    env_email    = os.environ.get("BTI_EMAIL")
    env_password = os.environ.get("BTI_PASSWORD")

    parser = argparse.ArgumentParser(
        description="BTicino CLASSE100X PoC — firmware v1 (Legrand Eliot cloud)"
    )
    parser.add_argument("--email",    required=not env_email,    default=env_email,
                        help="Legrand account email (or set BTI_EMAIL env var)")
    parser.add_argument("--password", required=not env_password, default=env_password,
                        help="Legrand account password (or set BTI_PASSWORD env var)")
    parser.add_argument("--open-door",    action="store_true", help="Trigger door unlock")
    parser.add_argument("--sip",          action="store_true", help="Use SIP instead of REST for door open")
    parser.add_argument("--listen-rings", action="store_true", help="Stay connected and log ring events")
    parser.add_argument("--debug",        action="store_true", help="Verbose debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        asyncio.run(run(args))
    except AuthError as exc:
        _LOGGER.error("Authentication failed: %s", exc)
        sys.exit(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
