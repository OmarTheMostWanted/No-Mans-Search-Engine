from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LookupOutcome:
    """Simple wrapper for generated lookup results."""

    address: str
    galaxy: int
    payload: dict[str, Any]


__all__ = ["LookupOutcome"]
