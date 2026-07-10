from __future__ import annotations

from dataclasses import dataclass
import hashlib
import time


@dataclass(frozen=True)
class RequestSignature:
    ts: str
    decodes: str


def make_signature(usercode: str, timestamp_ms: int | None = None) -> RequestSignature:
    if timestamp_ms is None:
        timestamp_ms = time.time_ns() // 1_000_000
    ts = str(timestamp_ms)
    digest = hashlib.md5(f"{usercode}Unifrinew{ts}".encode("utf-8")).hexdigest()
    decodes = f"{digest[16:]}{digest[:16]}".upper()
    return RequestSignature(ts=ts, decodes=decodes)
