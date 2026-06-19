"""System clock — implements the ``Clock`` port with real time and uuids.
Injectable so tests can stay deterministic with a fake.
"""
from __future__ import annotations

import time
import uuid


class SystemClock:
    def now(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def new_id(self) -> str:
        return uuid.uuid4().hex
