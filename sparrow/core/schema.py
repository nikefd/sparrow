"""Schema & wire-format rendering — pure, no I/O.

Three jobs, all of them pure functions over domain models:
1. Introspect a Python function's signature into a JSON Schema (used by ``@tool``).
2. Render the OpenAI ``tools`` array for the current step, honouring skill
   gating (inactive skills are hidden behind a single ``activate_skill`` pseudo
   tool — this is progressive disclosure).
3. Convert :class:`~sparrow.core.models.Message` objects to/from the OpenAI wire
   shape, so adapters stay thin.
"""
from __future__ import annotations

import inspect
from typing import Callable, Optional

from .models import Completion, Message, ToolCall, Usage

# Python type -> JSON Schema type
_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean",
               list: "array", dict: "object"}

# Names of the engine's built-in pseudo-tools (handled in the loop, never the
# registry). The model "calls" these but they are control signals, not tools.
ACTIVATE_SKILL = "activate_skill"
DELEGATE = "delegate"


def introspect(fn: Callable, explicit: Optional[dict] = None) -> dict:
    """Derive a JSON Schema for a function's keyword params (or return the
    explicit one). Params named self/args/_args are skipped; defaulted params are
    optional."""
    if explicit is not None:
        return explicit
    props: dict = {}
    required: list = []
    for pname, p in inspect.signature(fn).parameters.items():
        if pname in ("self", "args", "_args"):
            continue
        props[pname] = {"type": _JSON_TYPES.get(p.annotation, "string")}
        if p.default is inspect.Parameter.empty:
            required.append(pname)
    schema: dict = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


def _fn_spec(name: str, description: str, parameters: dict) -> dict:
    return {"type": "function",
            "function": {"name": name, "description": description, "parameters": parameters}}


def specs_for(registry, skills: list, *, allow_delegate: bool = False) -> list[dict]:
    """Render the OpenAI tools array for this step.

    Tools owned by a skill are hidden until that skill is active; inactive skills
    collapse into one ``activate_skill`` pseudo tool whose description lists them
    and their ``when``. ``delegate`` is exposed when a sub-agent runner is wired.
    """
    skill_tool_names = {t for s in skills for t in s.tools}
    inactive = [s for s in skills if not s.active]

    specs: list[dict] = []
    for t in registry.tools():
        # base tools (not owned by any skill) are always visible; skill tools
        # only once their skill is active
        if t.name in skill_tool_names:
            owners = [s for s in skills if t.name in s.tools]
            if not any(s.active for s in owners):
                continue
        specs.append(_fn_spec(t.name, t.description, t.schema))

    if inactive:
        listing = "\n".join(f"- {s.name}: {s.when}" for s in inactive)
        specs.append(_fn_spec(
            ACTIVATE_SKILL,
            "Activate a skill to unlock its instructions and tools before using "
            "them. Available skills:\n" + listing,
            {"type": "object",
             "properties": {"name": {"type": "string", "enum": [s.name for s in inactive]}},
             "required": ["name"]}))

    if allow_delegate:
        specs.append(_fn_spec(
            DELEGATE,
            "Delegate a self-contained subtask to an isolated sub-agent. It runs "
            "with its own fresh context and returns a text result.",
            {"type": "object",
             "properties": {"task": {"type": "string"},
                            "tools": {"type": "array", "items": {"type": "string"}},
                            "skills": {"type": "array", "items": {"type": "string"}}},
             "required": ["task"]}))
    return specs


# ── Message <-> OpenAI wire shape ────────────────────────────────────────────
def to_openai_messages(messages: list[Message]) -> list[dict]:
    """Serialize domain messages to the OpenAI chat format."""
    out: list[dict] = []
    for m in messages:
        if m.role == "assistant" and m.tool_calls:
            out.append({
                "role": "assistant",
                "content": m.content or None,
                "tool_calls": [{"id": tc.id, "type": "function",
                                "function": {"name": tc.name,
                                             "arguments": _dump_args(tc.arguments)}}
                               for tc in m.tool_calls],
            })
        elif m.role == "tool":
            out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content})
        else:
            out.append({"role": m.role, "content": m.content})
    return out


def completion_from_openai(msg: dict, raw_usage: Optional[dict] = None,
                           stop_reason: str = "stop") -> Completion:
    """Build a :class:`Completion` from one OpenAI choice message + finish_reason."""
    u = raw_usage or {}
    return Completion(
        content=msg.get("content") or "",
        tool_calls=[ToolCall(id=tc["id"], name=tc["function"]["name"],
                             arguments=_load_args(tc["function"].get("arguments")))
                    for tc in (msg.get("tool_calls") or [])],
        stop_reason=stop_reason,
        usage=Usage(prompt_tokens=u.get("prompt_tokens", 0),
                    completion_tokens=u.get("completion_tokens", 0)),
    )


def _dump_args(args) -> str:
    import json
    return json.dumps(args or {}, ensure_ascii=False)


def _load_args(s) -> dict:
    import json
    try:
        return json.loads(s or "{}")
    except (ValueError, TypeError):
        return {}
