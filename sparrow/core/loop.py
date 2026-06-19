"""The step reducer — the design's soul.

``step(state, deps) -> (state, events)`` applies one transition to a
:class:`RunState`. It performs no I/O of its own; every side effect goes through
a port in ``deps``. The driver (``app.agent``) just calls ``step`` repeatedly,
checkpointing after each round, until a terminal status.

All seven capabilities are routed through this one function:
  - stop-reason branching (E)
  - compaction trigger (B)
  - approval pause/resume (A, F)
  - sub-agent delegation (F)
  - skill activation / progressive disclosure (F)
  - structured-output finalize (_finalize)
  - checkpoint is the driver's job, enabled by RunState being pure data.

Pausing for approval is modelled as a normal terminal state plus a checkpoint —
never a blocking yield. The generator only ever pushes events; when it needs
outside input it ends, the driver persists, and ``resume()`` re-enters at the
``pending_approval`` branch. That keeps the event stream one-way and replayable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Callable, Optional

from . import budget, schema
from .models import Completion, Event, Message, RunState, ToolCall


@dataclass
class Deps:
    """The injection bag: live ports + the tool registry + tuning knobs. Never
    stored in RunState — re-supplied by the driver every step, which is what lets
    a checkpoint resume in another process."""
    llm: object
    tools: object                                    # ToolRegistry (duck-typed)
    approver: object = None
    clock: object = None
    summarizer: object = None
    subagent: object = None
    store: object = None
    token_budget: int = budget.DEFAULT_TOKEN_BUDGET
    keep_recent: int = 6
    tool_result_max_chars: int = 8000
    needs_approval: Optional[Callable] = None        # (ToolCall, Tool|None) -> bool

    def approval_required(self, call: ToolCall, tool) -> bool:
        if self.approver is None:
            return False
        if self.needs_approval is not None:
            return self.needs_approval(call, tool)
        return bool(tool and getattr(tool, "writes", False))


def step(state: RunState, deps: Deps):
    """Apply one transition. Returns ``(new_state, [events])``."""
    # ── A. resume from an approval pause ──
    if state.pending_approval is not None:
        return _resolve_approval(state, deps)

    events: list = []

    # ── B. compaction (before we spend the next LLM call) ──
    if budget.over_budget(state.messages, deps.token_budget):
        state, ev = _compact(state, deps)
        events += ev

    # ── C. round budget exhausted → forced close-out ──
    if state.round >= state.max_rounds:
        return _finalize(state, deps, None, forced=True, events=events)

    # ── D. call the model ──
    specs = schema.specs_for(deps.tools, state.skills, allow_delegate=deps.subagent is not None)
    comp = deps.llm.complete(state.messages, tools=specs or None,
                             response_format=_response_format(state))
    state = replace(state, round=state.round + 1)

    # ── E. stop-reason branching ──
    if comp.stop_reason == "content_filter":
        final = {"error": "content_filter"}
        return replace(state, status="error", final=final), events + [Event("error", final)]

    if comp.tool_calls:
        state = _append_assistant(state, comp)
        return _run_calls(state, comp.tool_calls, deps, events)

    if comp.stop_reason == "length":
        return _continuation(state, comp, events)

    return _finalize(state, deps, comp, events=events)


# ── tool-call processing ─────────────────────────────────────────────────────
def _run_calls(state: RunState, calls: list, deps: Deps, events: list):
    """Process a batch of tool calls, appending each result. Pauses (returns
    early with ``pending_approval`` set) at the first call that needs approval;
    siblings are resumed from message history, never re-executed."""
    for call in calls:
        if _answered(state, call):
            continue
        if call.name == schema.ACTIVATE_SKILL:
            state, ev = _activate_skill(state, call, deps)
            events += ev
            continue
        if call.name == schema.DELEGATE:
            state, ev = _delegate(state, call, deps)
            events += ev
            continue

        tool = deps.tools.get(call.name)
        # inject the run id into write tools that accept a conversation_id
        if tool and getattr(tool, "writes", False) and isinstance(call.arguments, dict):
            call.arguments.setdefault("conversation_id", state.run_id)

        if deps.approval_required(call, tool):
            paused = replace(state, pending_approval=call, status="awaiting_approval")
            return paused, events + [Event("awaiting_approval", {"call": _tc_dict(call)})]

        out = deps.tools.run(call.name, call.arguments)
        state = _append_tool_result(state, call, out, deps)
        events.append(Event("tool_result", {"name": call.name, "summary": _summarize(out)}))
    return state, events


def _resolve_approval(state: RunState, deps: Deps):
    """Resume point: ask the approver about the paused call, then continue with
    any still-unanswered siblings."""
    call = state.pending_approval
    decision = deps.approver.review(call)
    state = replace(state, pending_approval=None, status="running")

    if decision.verdict == "reject":
        out = {"error": f"rejected by approver{': ' + decision.reason if decision.reason else ''}"}
    else:
        args = (decision.arguments if decision.verdict == "edit" and decision.arguments is not None
                else call.arguments)
        out = deps.tools.run(call.name, args)
    state = _append_tool_result(state, call, out, deps)
    events = [Event("tool_result", {"name": call.name, "summary": _summarize(out)})]

    state, more = _run_calls(state, _unanswered_calls(state), deps, [])
    return state, events + more


# ── the special control "tools" ──────────────────────────────────────────────
def _activate_skill(state: RunState, call: ToolCall, deps: Deps):
    name = (call.arguments or {}).get("name", "")
    found = None
    skills = []
    for s in state.skills:
        if s.name == name and not s.active:
            found = s
            skills.append(replace(s, active=True))
        else:
            skills.append(s)
    state = replace(state, skills=skills)
    if not found:
        out = {"error": f"unknown or already-active skill: {name}"}
        state = _append_tool_result(state, call, out, deps)
        return state, [Event("tool_result", {"name": schema.ACTIVATE_SKILL, "summary": out["error"]})]
    out = {"activated": name, "instructions": found.instructions,
           "_summary": f"skill '{name}' activated"}
    state = _append_tool_result(state, call, out, deps)
    return state, [Event("skill_activated", {"name": name})]


def _delegate(state: RunState, call: ToolCall, deps: Deps):
    if deps.subagent is None:
        out = {"error": "delegation not available"}
        state = _append_tool_result(state, call, out, deps)
        return state, [Event("tool_result", {"name": schema.DELEGATE, "summary": out["error"]})]
    args = call.arguments or {}
    task = args.get("task", "")
    result = deps.subagent.run(task, tools=args.get("tools") or [], skills=args.get("skills") or [])
    out = {"result": result, "_summary": f"delegated: {task[:40]}"}
    state = _append_tool_result(state, call, out, deps)
    return state, [Event("delegated", {"task": task})]


# ── compaction / continuation / finalize ─────────────────────────────────────
def _compact(state: RunState, deps: Deps):
    head, tail = budget.split_oldest(state.messages, deps.keep_recent)
    if not head:
        return state, []
    summary = deps.summarizer.summarize(head)
    sys = [state.messages[0]] if state.messages and state.messages[0].role == "system" else []
    return replace(state, messages=sys + [summary] + tail), [Event("compacted", {"freed": len(head)})]


def _continuation(state: RunState, comp: Completion, events: list):
    """The reply was truncated by max_tokens: keep the partial text and nudge the
    model to continue. The continuation costs a round, so it can't loop forever."""
    state = _append(state, Message(role="assistant", content=comp.content))
    state = _append(state, Message(role="user",
                    content="(your previous reply was cut off; continue from where you stopped)"))
    return state, events + [Event("tool_result",
                                  {"name": "_continuation", "summary": "continuing truncated reply"})]


def _finalize(state: RunState, deps: Deps, comp: Optional[Completion], *,
              forced: bool = False, events: Optional[list] = None):
    events = events or []
    if forced:
        state = _append(state, Message(role="user",
                        content="(tool-call limit reached; answer now from what you have)"))
        comp = deps.llm.complete(state.messages, response_format=_response_format(state))
    citations = sorted(set(state.citations))
    if state.output_schema:
        try:
            final = {"structured": json.loads(comp.content), "citations": citations}
        except (ValueError, TypeError):
            final = {"content": comp.content, "citations": citations,
                     "error": "output did not parse as JSON"}
    else:
        final = {"content": comp.content, "citations": citations}
    return replace(state, status="done", final=final), events + [Event("final", final)]


# ── small pure helpers ───────────────────────────────────────────────────────
def _response_format(state: RunState) -> Optional[dict]:
    # provider-agnostic: ask for a JSON object; the host's prompt carries the schema
    return {"type": "json_object"} if state.output_schema else None


def _append(state: RunState, msg: Message) -> RunState:
    return replace(state, messages=state.messages + [msg])


def _append_assistant(state: RunState, comp: Completion) -> RunState:
    return _append(state, Message(role="assistant", content=comp.content, tool_calls=comp.tool_calls))


def _append_tool_result(state: RunState, call: ToolCall, out, deps: Deps) -> RunState:
    """Append a tool result as a serialized string — the core never holds the
    live object, which keeps RunState checkpointable. Collects ``source`` into
    citations."""
    content = _truncate(json.dumps(out, ensure_ascii=False, default=str), deps.tool_result_max_chars)
    msg = Message(role="tool", tool_call_id=call.id, name=call.name, content=content)
    citations = state.citations
    if isinstance(out, dict) and out.get("source"):
        citations = citations + [out["source"]]
    return replace(state, messages=state.messages + [msg], citations=citations)


def _answered(state: RunState, call: ToolCall) -> bool:
    return any(m.role == "tool" and m.tool_call_id == call.id for m in state.messages)


def _unanswered_calls(state: RunState) -> list:
    """Tool calls from the most recent assistant turn that still lack a result."""
    last = next((m for m in reversed(state.messages) if m.role == "assistant" and m.tool_calls), None)
    if not last:
        return []
    return [tc for tc in last.tool_calls if not _answered(state, tc)]


def _truncate(s: str, limit: int) -> str:
    return s if len(s) <= limit else s[:limit] + "…(truncated)"


def _tc_dict(call: ToolCall) -> dict:
    return {"id": call.id, "name": call.name, "arguments": call.arguments}


def _summarize(out) -> str:
    """One human line for a tool result. Hosts can override via a ``_summary``
    key."""
    if isinstance(out, dict):
        if out.get("error"):
            return f"error: {out['error']}"
        if out.get("_summary"):
            return out["_summary"]
        for k, v in out.items():
            if isinstance(v, list):
                return f"{len(v)} {k}"
        if out.get("message"):
            return out["message"]
    return "done"
