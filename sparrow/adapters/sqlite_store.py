"""SQLite checkpoint Store — implements the ``Store`` port.

Each run's :class:`RunState` is persisted as one JSON blob keyed by run_id. A
host that also wants conversation history can use a separate table; checkpoints
and conversation logs are deliberately kept apart (a checkpoint is engine state,
a conversation log is host data).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from ..core.models import RunState, state_from_dict, state_to_dict


class SqliteStore:
    """Implements the :class:`~sparrow.ports.Store` protocol over one sqlite file."""

    def __init__(self, db_path):
        self.db_path = Path(db_path)

    def _conn(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(self.db_path))
        c.execute("""CREATE TABLE IF NOT EXISTS checkpoints (
            run_id TEXT PRIMARY KEY, state TEXT NOT NULL, updated_at TEXT)""")
        return c

    def save(self, run_id: str, state: RunState) -> None:
        c = self._conn()
        try:
            c.execute("INSERT OR REPLACE INTO checkpoints (run_id, state, updated_at) "
                      "VALUES (?,?,datetime('now'))",
                      (run_id, json.dumps(state_to_dict(state), ensure_ascii=False)))
            c.commit()
        finally:
            c.close()

    def load(self, run_id: str) -> Optional[RunState]:
        c = self._conn()
        try:
            row = c.execute("SELECT state FROM checkpoints WHERE run_id=?", (run_id,)).fetchone()
            return state_from_dict(json.loads(row[0])) if row else None
        finally:
            c.close()

    def delete(self, run_id: str) -> None:
        c = self._conn()
        try:
            c.execute("DELETE FROM checkpoints WHERE run_id=?", (run_id,))
            c.commit()
        finally:
            c.close()
