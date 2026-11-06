from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Sequence

from config import normalize_portal_address


class JSBridge:
    """Line-oriented JSON bridge to the nms-galactic-map lookup module."""

    def __init__(self, bridge_path: str | Path = "js/bridge.mjs", node_bin: str = "node") -> None:
        self.process = subprocess.Popen(
            [node_bin, str(bridge_path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            # Inherit stderr to avoid deadlocks from an unread PIPE.
            stderr=None, text=True, bufsize=1,
        )

    def _request(self, request: dict[str, Any]) -> Any:
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("Node bridge is not available.")
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(f"Node bridge exited with status {self.process.poll()}.")
        response = json.loads(line)
        if not isinstance(response, dict) or response.get("success") is not True:
            message = response.get("error", "Invalid bridge response") if isinstance(response, dict) else "Invalid bridge response"
            raise RuntimeError(message)
        return response.get("data")

    def batch(self, portal_addresses: Sequence[str], galaxy: int = 0) -> list[dict[str, Any]]:
        addresses = [normalize_portal_address(value) for value in portal_addresses]
        if not addresses:
            return []
        data = self._request({
            "action": "batch",
            "systems": [{"portal_code": address, "galaxy": galaxy} for address in addresses],
        })
        if not isinstance(data, list) or len(data) != len(addresses):
            raise RuntimeError("Bridge batch response must contain one system per requested address.")
        if any(not isinstance(item, dict) for item in data):
            raise RuntimeError("Bridge batch response contains a non-object system.")
        for address, item in zip(addresses, data):
            if item.get("address", "").upper() != address:
                raise RuntimeError(f"Bridge response address did not match request {address}.")
            if item.get("galaxy") != galaxy:
                raise RuntimeError(f"Bridge response galaxy did not match request for {address}.")
            required = {"starType", "planets", "moons", "race", "economy", "econTier", "conflict", "conTier", "abandoned", "uncharted", "outlaw", "isBlackHole", "isAtlas", "coords"}
            missing = required.difference(item)
            if missing:
                raise RuntimeError(f"Upstream system payload is missing fields: {', '.join(sorted(missing))}.")
        return data

    def close(self) -> None:
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=3)

    def __enter__(self) -> "JSBridge":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
