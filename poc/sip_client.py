from __future__ import annotations
import asyncio
import hashlib
import json
import logging
import random
import ssl
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)

# Fixed SIP user on every BTicino gateway — from VctLinphoneService.O()
_GATEWAY_SIP_USER = "c100x"


def _md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def _build_door_payload(plant_id: str | None) -> str:
    """
    JSON-RPC 2.0 body sent as SIP MESSAGE to trigger the door lock.
    Reconstructed from JsonRpcKotlin + Action.Lock (decompiled APK):
      method = "lock.setStatus"  (Action.Lock.value)
      status = "open"            (Params constructor for Lock branch)
    """
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": str(random.randint(100_000, 999_999_999)),
            "method": "lock.setStatus",
            "params": [
                {
                    "status": "open",
                    "receiver": {"plant": {"coal": {"id": plant_id}, "module": {}}},
                }
            ],
        },
        separators=(",", ":"),
    )


def _parse_uri(sip_uri: str) -> tuple[str, str]:
    uri = sip_uri.removeprefix("sip:").removeprefix("sips:")
    user, _, domain = uri.partition("@")
    return user, domain


@dataclass
class SipCredentials:
    sip_uri:   str   # e.g. "abc123@abc123.bs.iotleg.com"
    password:  str
    username:  str
    plant_id:  str
    device_id: str


class _SipProtocol(asyncio.Protocol):
    """
    Minimal SIP/TLS stream protocol — exactly what the PoC needs:
      REGISTER (with digest challenge handling)
      MESSAGE  (to send door-open payload)
      INVITE   (to detect incoming doorbell rings)

    Not a full SIP stack — no SDP, no media, no fragmented-message reassembly
    beyond the Content-Length framing already required by RFC 3261.
    """

    def __init__(
        self,
        creds: SipCredentials,
        plant_id: str | None,
        ring_queue: asyncio.Queue,
        registered: asyncio.Event,
    ) -> None:
        self._creds      = creds
        self._plant_id   = plant_id
        self._ring_queue = ring_queue
        self._registered = registered
        self._transport: asyncio.Transport | None = None
        self._cseq    = 0
        self._call_id = f"{random.randint(10**9, 10**10)}@bticino-poc"
        self._buffer  = b""
        self._user, self._domain = _parse_uri(creds.sip_uri)

    # ── asyncio.Protocol ─────────────────────────────────────────────

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._transport = transport  # type: ignore[assignment]
        _LOGGER.info("SIP TLS connected → %s", self._domain)
        self._register()

    def data_received(self, data: bytes) -> None:
        self._buffer += data
        self._drain()

    def connection_lost(self, exc: Exception | None) -> None:
        _LOGGER.warning("SIP connection closed: %s", exc)

    # ── message framing (RFC 3261 §20.14) ────────────────────────────

    def _drain(self) -> None:
        while b"\r\n\r\n" in self._buffer:
            head, _, tail = self._buffer.partition(b"\r\n\r\n")
            headers: dict[str, str] = {}
            lines = head.decode(errors="replace").splitlines()
            first_line = lines[0] if lines else ""
            for line in lines[1:]:
                if ":" in line:
                    k, _, v = line.partition(":")
                    headers[k.strip().lower()] = v.strip()
            clen = int(headers.get("content-length", "0"))
            if len(tail) < clen:
                break  # wait for more data
            body = tail[:clen].decode(errors="replace")
            self._buffer = tail[clen:]
            self._dispatch(first_line, headers, body)

    # ── message dispatch ─────────────────────────────────────────────

    def _dispatch(self, first: str, hdrs: dict[str, str], body: str) -> None:
        _LOGGER.debug("SIP << %s", first)
        if first.startswith("SIP/2.0"):
            code = int(first.split(" ", 2)[1])
            if code in (401, 407):
                challenge = hdrs.get("www-authenticate") or hdrs.get("proxy-authenticate", "")
                self._register(challenge=challenge)
            elif code == 200:
                cseq = hdrs.get("cseq", "")
                if "REGISTER" in cseq:
                    _LOGGER.info("SIP registered ✓")
                    self._registered.set()
                elif "MESSAGE" in cseq:
                    _LOGGER.info("Door-open SIP MESSAGE acknowledged")
        else:
            method = first.split(" ", 1)[0].upper()
            if method == "INVITE":
                from_hdr = hdrs.get("from", "unknown")
                _LOGGER.info("Doorbell ring! INVITE from %s", from_hdr)
                self._ring_queue.put_nowait({"from": from_hdr})

    # ── SIP helpers ──────────────────────────────────────────────────

    def _send(self, msg: str) -> None:
        if self._transport:
            _LOGGER.debug("SIP >> %s", msg.split("\r\n")[0])
            self._transport.write(msg.encode())

    def _next_cseq(self) -> int:
        self._cseq += 1
        return self._cseq

    def _register(self, challenge: str | None = None) -> None:
        cseq   = self._next_cseq()
        tag    = hex(random.getrandbits(32))[2:]
        branch = f"z9hG4bK{hex(random.getrandbits(32))[2:]}"
        auth   = ""

        if challenge:
            import re
            rm = re.search(r'realm="([^"]+)"', challenge)
            nm = re.search(r'nonce="([^"]+)"', challenge)
            if rm and nm:
                realm = rm.group(1)
                nonce = nm.group(1)
                ha1   = _md5(f"{self._user}:{realm}:{self._creds.password}")
                ha2   = _md5(f"REGISTER:sip:{self._domain}")
                resp  = _md5(f"{ha1}:{nonce}:{ha2}")
                auth  = (
                    f'Authorization: Digest username="{self._user}",'
                    f'realm="{realm}",nonce="{nonce}",'
                    f'uri="sip:{self._domain}",response="{resp}"\r\n'
                )

        self._send(
            f"REGISTER sip:{self._domain} SIP/2.0\r\n"
            f"Via: SIP/2.0/TLS {self._domain};branch={branch}\r\n"
            f"From: <sip:{self._user}@{self._domain}>;tag={tag}\r\n"
            f"To: <sip:{self._user}@{self._domain}>\r\n"
            f"Call-ID: {self._call_id}\r\n"
            f"CSeq: {cseq} REGISTER\r\n"
            f"Contact: <sip:{self._user}@{self._domain}>\r\n"
            f"Expires: 3600\r\n"
            f"Max-Forwards: 70\r\n"
            f"{auth}"
            f"Content-Length: 0\r\n\r\n"
        )

    def send_door_open(self) -> None:
        cseq   = self._next_cseq()
        tag    = hex(random.getrandbits(32))[2:]
        branch = f"z9hG4bK{hex(random.getrandbits(32))[2:]}"
        target = f"sip:{_GATEWAY_SIP_USER}@{self._domain}"
        body   = _build_door_payload(self._plant_id)

        self._send(
            f"MESSAGE {target} SIP/2.0\r\n"
            f"Via: SIP/2.0/TLS {self._domain};branch={branch}\r\n"
            f"From: <sip:{self._user}@{self._domain}>;tag={tag}\r\n"
            f"To: <{target}>\r\n"
            f"Call-ID: {self._call_id}\r\n"
            f"CSeq: {cseq} MESSAGE\r\n"
            f"Max-Forwards: 70\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body.encode())}\r\n\r\n"
            f"{body}"
        )


class SipClient:
    def __init__(self, creds: SipCredentials, plant_id: str | None = None) -> None:
        self._creds     = creds
        self._plant_id  = plant_id
        self._proto: _SipProtocol | None  = None
        self._transport: asyncio.BaseTransport | None = None
        self.ring_events: asyncio.Queue   = asyncio.Queue()
        self._registered = asyncio.Event()

    async def connect(self, host: str, port: int = 5228) -> None:
        loop    = asyncio.get_running_loop()
        ssl_ctx = ssl.create_default_context()
        # PoC: skip cert verification — enable in production
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode    = ssl.CERT_NONE

        self._proto = _SipProtocol(
            self._creds, self._plant_id, self.ring_events, self._registered
        )
        self._transport, _ = await loop.create_connection(
            lambda: self._proto,
            host=host,
            port=port,
            ssl=ssl_ctx,
        )
        _LOGGER.info("SIP client connecting to %s:%d …", host, port)

    async def wait_registered(self, timeout: float = 15.0) -> None:
        await asyncio.wait_for(self._registered.wait(), timeout=timeout)

    async def open_door(self) -> None:
        if not self._proto:
            raise RuntimeError("SIP client not connected")
        self._proto.send_door_open()

    def disconnect(self) -> None:
        if self._transport:
            self._transport.close()
