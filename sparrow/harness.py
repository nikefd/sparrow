"""Deprecated — use :class:`sparrow.Agent`.

A thin back-compat shim mapping the old ``Harness(config).run(messages)`` API to
the new :class:`~sparrow.app.agent.Agent`, yielding old-style dict events
(``{"type": ..., ...}``) so existing consumers keep working for one release.
"""
from __future__ import annotations

import warnings

from .app.agent import Agent


class Harness:
    """Deprecated alias for :class:`sparrow.Agent`. Yields dict events."""

    def __init__(self, config, *, journal_fn=None):
        warnings.warn("sparrow.Harness is deprecated; use sparrow.Agent instead.",
                      DeprecationWarning, stacklevel=2)
        self._agent = Agent(config)

    def run(self, user_messages, conversation_id=""):
        for ev in self._agent.run(user_messages, run_id=conversation_id or None):
            yield {"type": ev.type, **ev.data}
