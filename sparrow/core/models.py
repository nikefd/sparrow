"""Core domain models — the pure data structures the engine reasons about.

Everything here is a plain ``@dataclass`` with no behavior, no I/O and no
third-party types, so the whole agent state is trivially JSON-serializable. That
property is what makes checkpointing (save → load → resume across processes)
possible: :class:`RunState` is the single thing the engine persists, and it
never holds a live object (connection, registry, port) — only data.

Conversions to/from the OpenAI wire format live in ``core.schema``, deliberately
kept out of these classes so they stay pure data.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class Usage:
    """Token accounting for one LLM call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class ToolCall:
    """A single tool invocation requested by the model."""
    id: str
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class Message:
    """One turn in the conversation. ``role`` is system|user|assistant|tool.

    ``tool_calls`` is populated on assistant turns that call tools;
    ``tool_call_id`` + ``name`` identify which call a ``role="tool"`` turn
    answers.
    """
    role: str
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str = ""
    name: str = ""


# Why the model stopped. Mirrors OpenAI's finish_reason; the engine branches on
# it (the old harness threw this away — re-surfacing it is a core fix).
#   "tool_calls"     -> the model wants to call tools
#   "stop"           -> a complete answer
#   "length"         -> truncated by max_tokens; should be continued
#   "content_filter" -> blocked
StopReason = str


@dataclass
class Completion:
    """The unified result of one LLM call."""
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: StopReason = "stop"
    usage: Usage = field(default_factory=Usage)


@dataclass
class Skill:
    """A lazily-disclosed capability: a name + when-to-use shown up front, with
    full ``instructions`` and ``tools`` revealed only after activation.

    ``active`` is part of :class:`RunState`, so progressive disclosure survives
    checkpoint/resume.
    """
    name: str
    when: str                              # one line: when to reach for this
    instructions: str = ""                 # revealed only once active
    tools: list[str] = field(default_factory=list)   # tool names, gated until active
    active: bool = False


@dataclass
class Decision:
    """An approver's verdict on a pending tool call.

    ``verdict`` is approve|reject|edit; ``arguments`` carries replacement args
    when the approver edits the call before allowing it.
    """
    verdict: str = "approve"
    arguments: Optional[dict] = None
    reason: str = ""


@dataclass
class Event:
    """Something worth telling the caller about. The driver yields these; the
    transport layer (SSE/CLI) only serializes them.

    ``type`` is one of: tool_call, tool_result, skill_activated, compacted,
    awaiting_approval, delegated, final, error.
    """
    type: str
    data: dict = field(default_factory=dict)


@dataclass
class RunState:
    """The entire persistable state of one agent run — the checkpoint payload.

    Pure data only: no functions, no connections, no registries. Ports/tools are
    injected as ``deps`` at drive time and never stored here, which is exactly
    what lets a run be saved, reloaded in another process, and resumed.
    """
    run_id: str
    messages: list[Message] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    round: int = 0
    max_rounds: int = 8
    pending_approval: Optional[ToolCall] = None    # set while paused for approval
    output_schema: Optional[dict] = None           # structured-output contract
    status: str = "running"                        # running|awaiting_approval|done|error
    final: Optional[dict] = None                   # the finished result
    citations: list[str] = field(default_factory=list)


# ── serialization (pure; the checkpoint boundary) ────────────────────────────
def state_to_dict(state: RunState) -> dict:
    """Flatten a :class:`RunState` to a JSON-able dict. ``asdict`` recurses into
    the nested dataclasses (messages, tool_calls, skills)."""
    return asdict(state)


def state_from_dict(d: dict) -> RunState:
    """Rebuild a :class:`RunState` from :func:`state_to_dict` output."""
    def _toolcall(t: dict) -> ToolCall:
        return ToolCall(id=t.get("id", ""), name=t.get("name", ""),
                        arguments=t.get("arguments") or {})

    messages = [
        Message(role=m["role"], content=m.get("content", ""),
                tool_calls=[_toolcall(t) for t in m.get("tool_calls") or []],
                tool_call_id=m.get("tool_call_id", ""), name=m.get("name", ""))
        for m in d.get("messages", [])
    ]
    skills = [
        Skill(name=s["name"], when=s.get("when", ""), instructions=s.get("instructions", ""),
              tools=list(s.get("tools") or []), active=bool(s.get("active")))
        for s in d.get("skills", [])
    ]
    pa = d.get("pending_approval")
    return RunState(
        run_id=d["run_id"], messages=messages, skills=skills,
        round=d.get("round", 0), max_rounds=d.get("max_rounds", 8),
        pending_approval=_toolcall(pa) if pa else None,
        output_schema=d.get("output_schema"), status=d.get("status", "running"),
        final=d.get("final"), citations=list(d.get("citations") or []),
    )
