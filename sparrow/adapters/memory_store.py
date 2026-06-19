"""In-memory Store adapter — the checkpoint store with no database.

Useful when there is no need to persist across processes (and as the fake in
tests). It round-trips state through :func:`state_to_dict`/:func:`state_from_dict`
so it exercises the same serialization boundary the sqlite store relies on —
catching "accidentally stored a live object" bugs early.
"""
from __future__ import annotations

from typing import Optional

from ..core.models import RunState, state_from_dict, state_to_dict


class MemoryStore:
    """Implements the :class:`~sparrow.ports.Store` protocol over a dict."""

    def __init__(self):
        self._db: dict = {}

    def save(self, run_id: str, state: RunState) -> None:
        self._db[run_id] = state_to_dict(state)        # serialize on the way in

    def load(self, run_id: str) -> Optional[RunState]:
        d = self._db.get(run_id)
        return state_from_dict(d) if d is not None else None

    def delete(self, run_id: str) -> None:
        self._db.pop(run_id, None)
