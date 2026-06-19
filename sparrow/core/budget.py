"""Context budgeting — a deliberately crude, dependency-free token estimate.

We approximate tokens as ``len(json)/4`` rather than pulling in a real
tokenizer; that keeps the core stdlib-only. The estimate is biased, so callers
should trigger compaction with headroom (e.g. ~80% of the real window).
"""
from __future__ import annotations

import json

from .models import Message

# Default compaction trigger (approx tokens). Tunable per AgentConfig.
DEFAULT_TOKEN_BUDGET = 12000


def approx_tokens(messages: list[Message]) -> int:
    """~len(serialized)/4 across all messages, incl. tool-call payloads."""
    total = 0
    for m in messages:
        total += len(m.content or "")
        for tc in m.tool_calls:
            total += len(json.dumps(tc.arguments, ensure_ascii=False, default=str)) + len(tc.name)
    return total // 4


def over_budget(messages: list[Message], limit: int = DEFAULT_TOKEN_BUDGET) -> bool:
    return approx_tokens(messages) > limit


def split_oldest(messages: list[Message], keep_recent: int = 6):
    """Choose which messages to compact.

    Returns ``(head, tail)``: ``head`` is the oldest block to summarize, ``tail``
    the most recent ``keep_recent`` to keep verbatim. A leading system message is
    the caller's responsibility to preserve (it is not included in ``head``).
    """
    body = messages[1:] if messages and messages[0].role == "system" else messages
    if len(body) <= keep_recent:
        return [], body
    cut = len(body) - keep_recent
    return body[:cut], body[cut:]
