from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from config import normalize_address, validate_galaxy


class JSBridge:
    """Persistent JSON-lines adapter for the repository's `js/bridge.mjs` process."""

    def __init__(self, script: str | Path, node: str = "node"):
        path = Path(script)
        if not path.is_file():
            raise FileNotFoundError(f"Generator bridge not found: {path}. Initialize the nms-galactic-map submodule.")
        self.process = subprocess.Popen([node, str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None, text=True, bufsize=1, cwd=path.parent.parent)

    def lookup(self, address: str, galaxy: int) -> dict[str, Any]:
        address=normalize_address(address); validate_galaxy(galaxy)
        if self.process.poll() is not None or self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("The generator bridge is not running")
        self.process.stdin.write(json.dumps({"action":"lookup","portal_code":address,"galaxy":galaxy})+"\n")
        self.process.stdin.flush()
        line=self.process.stdout.readline()
        if not line:
            raise RuntimeError("Generator bridge closed without a response")
        try: response=json.loads(line)
        except json.JSONDecodeError as exc: raise RuntimeError(f"Invalid JSON from generator bridge: {line[:200]}") from exc
        if response.get("success") is not True: raise RuntimeError(response.get("error","Generator lookup failed"))
        result=response.get("data")
        if not isinstance(result,dict): raise RuntimeError("Generator returned a non-object result")
        return result

    def close(self) -> None:
        if self.process.stdin and not self.process.stdin.closed: self.process.stdin.close()
        try: self.process.wait(timeout=5)
        except subprocess.TimeoutExpired: self.process.terminate(); self.process.wait(timeout=5)

    def __enter__(self) -> "JSBridge": return self
    def __exit__(self,*_: object) -> None: self.close()
