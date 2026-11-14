from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


class NodeBridge:
    """Small helper that calls the upstream Node lookup module.

    This is intentionally very thin. The real algorithm lives in the upstream
    project, and this wrapper just invokes it and returns JSON.
    """

    def __init__(self, bridge_path: str | Path, core_path: str | Path):
        self.bridge_path = Path(bridge_path)
        self.core_path = Path(core_path)
        if not self.bridge_path.exists():
            raise FileNotFoundError(f"Upstream generator bridge not found: {self.bridge_path}")
        if not self.core_path.exists():
            raise FileNotFoundError(f"Upstream generator core directory not found: {self.core_path}")

    def lookup(self, address: str, galaxy: int = 0) -> dict[str, Any]:
        """Call the upstream module and return its data structure."""

        command = [
            "node",
            "--input-type=module",
            "-e",
            (
                "import { init, getSystem } from process.argv[1];"
                "await init(process.argv[2]);"
                "const result = await getSystem(process.argv[3], Number(process.argv[4]));"
                "console.log(JSON.stringify(result));"
            ),
            str(self.bridge_path),
            str(self.core_path),
            str(address).upper(),
            str(galaxy),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
            raise RuntimeError(f"Upstream generator call failed: {stderr}")
        try:
            return json.loads(completed.stdout.strip())
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON from upstream generator: {completed.stdout!r}") from exc


__all__ = ["NodeBridge"]
