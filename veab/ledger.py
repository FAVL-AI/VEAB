"""Append-only canonical JSON trace; HMAC optional, external key custody required."""
from __future__ import annotations
import hashlib
import hmac
from typing import Any
from .spec import canonical, digest

GENESIS = "0" * 64


class Ledger:
    def __init__(self):
        self.events: list[dict[str, Any]] = []
        self._last_hash = GENESIS

    def emit(self, tick: int, kind: str, payload: dict[str, Any]):
        if not isinstance(tick, int) or tick < 0:
            raise ValueError("tick must be nonnegative")
        base = {"seq": len(self.events), "tick": tick, "kind": kind,
                "payload": payload, "prev_hash": self._last_hash}
        event = {**base, "hash": digest(base)}
        self.events.append(event)
        self._last_hash = event["hash"]
        return event

    @property
    def root(self) -> str:
        return self._last_hash


def check_chain(events: list[dict]) -> tuple[bool, str]:
    previous = GENESIS
    if not events:
        return False, "empty event stream"
    last_tick = -1
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            return False, f"invalid event at {index}"
        if event.get("seq") != index or event.get("prev_hash") != previous:
            return False, f"sequence or chain mismatch at {index}"
        if not isinstance(event.get("tick"), int) or event["tick"] < last_tick:
            return False, f"nonmonotonic tick at {index}"
        allowed = {"seq", "tick", "kind", "payload", "prev_hash", "hash"}
        if set(event) != allowed:
            return False, f"unknown event attributes at {index}"
        try:
            computed = digest({k: v for k, v in event.items() if k != "hash"})
        except (ValueError, TypeError):
            return False, f"invalid event body at {index}"
        if not hmac.compare_digest(str(event.get("hash", "")), computed):
            return False, f"event digest mismatch at {index}"
        previous = event["hash"]
        last_tick = event["tick"]
    return True, "valid SHA-256 chain"


def sign(root: str, key: str | None) -> dict[str, str] | None:
    if not key:
        return None
    return {"algorithm": "HMAC-SHA256", "signature": hmac.new(key.encode(), root.encode(), hashlib.sha256).hexdigest()}


def verify_signature(root: str, attestation: dict | None, key: str | None) -> bool | None:
    if not attestation or not key:
        return None
    if attestation.get("algorithm") != "HMAC-SHA256":
        return False
    expected = sign(root, key)
    return hmac.compare_digest(str(attestation.get("signature", "")), expected["signature"])
