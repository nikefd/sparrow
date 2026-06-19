"""Ports — the abstract seams between the pure core and the outside world.

Each port is a :class:`typing.Protocol` (structural typing: zero dependencies,
no forced inheritance, trivial to fake in tests). The core depends only on these
interfaces; concrete implementations live in ``sparrow.adapters``.

Design rule: a port exists only for something that genuinely varies — roughly,
"two adapters make a seam". The real/fake split needed to unit-test the core
without a network counts as a second adapter. Deliberately *not* ports:
multi-provider routing, retry policy, tracing, permission policy — those are
non-essential and would just be single-implementation ceremony.

Tool execution is intentionally not a port: tools are ordinary host functions
and ``ToolRegistry`` already wraps their errors; wrapping them in a port would
be layering for its own sake.
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..core.models import Completion, Decision, Message, RunState, ToolCall


@runtime_checkable
class LLM(Protocol):
    """The transport seam: one call to a chat-completions endpoint.

    Must populate :attr:`Completion.stop_reason` from the provider's
    finish_reason — the core branches on it (the old client dropped it).
    """
    def complete(self, messages: list[Message], *, tools: Optional[list[dict]] = None,
                 response_format: Optional[dict] = None, max_tokens: int = 2000,
                 temperature: float = 0.3) -> Completion: ...


@runtime_checkable
class Store(Protocol):
    """Checkpoint persistence: save every round, load to resume, delete on
    successful finish."""
    def save(self, run_id: str, state: RunState) -> None: ...
    def load(self, run_id: str) -> Optional[RunState]: ...
    def delete(self, run_id: str) -> None: ...


@runtime_checkable
class Approver(Protocol):
    """Human-in-the-loop gate. ``review`` returns synchronously; any blocking or
    polling is the adapter's concern — the core only sees a :class:`Decision`."""
    def review(self, call: ToolCall) -> Decision: ...


@runtime_checkable
class Clock(Protocol):
    """Time and identity, injectable so tests can be deterministic."""
    def now(self) -> str: ...
    def new_id(self) -> str: ...


@runtime_checkable
class Summarizer(Protocol):
    """Compaction's execution body: turn a block of the oldest messages into a
    single ``role="system"`` summary message."""
    def summarize(self, messages: list[Message]) -> Message: ...


@runtime_checkable
class SubAgentRunner(Protocol):
    """Delegation: run a sub-task in an isolated context and return text the
    parent loop can fold back in as a tool result."""
    def run(self, task: str, *, tools: list[str], skills: list[str]) -> str: ...
