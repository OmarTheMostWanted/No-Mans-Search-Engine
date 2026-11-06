from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Sequence

from config import normalize_portal_address


class JSBridge:
    """Persistent JSON-lines client for the real nms-galactic-map Node bridge."""

    def __init__(self, bridge_path: str | Path = "js/bridge.mjs", node_bin: str = "node") -> None:
        path = Path(bridge_path)
        if not path.is_file():
            raise RuntimeError(f"NMS bridge not found: {path}. Run from the project root and initialize submodules.")
        try:
            self.process = subprocess.Popen([node_bin, str(path)], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=None, text=True, bufsize=1)
        except OSError as exc:
            raise RuntimeError(f"Could not start Node.js executable {node_bin!r}: {exc}") from exc

    def _request(self, request: dict[str, Any]) -> Any:
        if self.process.poll() is not None:
            raise RuntimeError(f"NMS bridge exited with status {self.process.returncode}.")
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("NMS bridge standard streams are unavailable.")
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(f"NMS bridge closed its output (exit status {self.process.poll()}).")
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"NMS bridge returned invalid JSON: {line[:200]!r}") from exc
        if not isinstance(response, dict) or response.get("success") is not True:
            message = response.get("error", "Invalid NMS bridge response") if isinstance(response, dict) else "Invalid NMS bridge response"
            raise RuntimeError(message)
        return response.get("data")

    def batch(self, portal_addresses: Sequence[str], galaxy: int = 0) -> list[dict[str, Any]]:
        addresses = [normalize_portal_address(address) for address in portal_addresses]
        if not addresses:
            return []
        data = self._request({"action": "batch", "systems": [
            {"portal_code": address, "galaxy": galaxy} for address in addresses]})
        if not isinstance(data, list) or len(data) != len(addresses):
            raise RuntimeError("NMS bridge returned an invalid batch response.")
        for address, item in zip(addresses, data):
            if not isinstance(item, dict) or item.get("address", "").upper() != address:
                raise RuntimeError(f"NMS bridge returned invalid data for {address}.")
            if item.get("galaxy") != galaxy:
                raise RuntimeError(f"NMS bridge returned the wrong galaxy for {address}.")
        return data

    def close(self) -> None:
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=5)

    def __enter__(self) -> "JSBridge":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
