"""sparrow — a small-but-complete agent harness.

麻雀虽小，五脏俱全 / Small bird, all the organs.

Bring your own tools and a system prompt; sparrow wires them into a ReAct loop
with citations, then layers on the organs of a real agent — skills (progressive
disclosure), context compaction, stop-reason handling, checkpoint/resume,
sub-agent delegation, human-in-the-loop approval, and structured output — each in
its minimal form. Stdlib-only core, zero runtime dependencies.

    from sparrow import tool, AgentConfig, Agent

    @tool(description="Echo back", source="demo")
    def echo(text: str) -> dict:
        return {"text": text}

    cfg = AgentConfig(system_prompt="You are a helpful assistant.", tools=[echo])
    for event in Agent(cfg).run([{"role": "user", "content": "hi"}]):
        print(event)            # Event(type=..., data=...)

Architecture is hexagonal: a pure ``core`` (loop + models) depends only on the
Protocols in ``sparrow.ports``; concrete ``adapters`` (OpenAI client, sqlite
store, ...) are injected by the ``app`` layer. Optional batteries live in
``sparrow.tools`` (the built-in tool set, the restricted-expression engine, and
panels-as-memory).
"""
from . import ports
from .app.agent import Agent
from .app.config import AgentConfig
from .core.models import (Completion, Decision, Event, Message, RunState, Skill,
                          ToolCall)
from .adapters.openai_llm import LLMError, OpenAILLM, configure
from .tools.builtins import builtins
from .tools.expr import is_safe_expr, safe_eval
from .tools.registry import Tool, ToolRegistry, tool
from .harness import Harness  # deprecated shim

__version__ = "0.3.0"

__all__ = [
    # core engine
    "Agent", "AgentConfig", "Event", "RunState", "Skill",
    "Message", "Completion", "ToolCall", "Decision",
    # tools
    "tool", "Tool", "ToolRegistry", "builtins",
    "safe_eval", "is_safe_expr",
    # LLM adapter
    "OpenAILLM", "configure", "LLMError",
    # ports namespace (for custom adapters)
    "ports",
    # optional panels battery (lazy import to keep them off the core path)
    "Memory", "panel_tools",
    # deprecated
    "Harness",
]


def __getattr__(name):
    # Lazy access to the optional panels battery so importing sparrow never
    # pulls in sqlite/panels unless a host actually uses them.
    if name in ("Memory", "panel_tools"):
        from .tools import panels
        return getattr(panels, name)
    raise AttributeError(f"module 'sparrow' has no attribute {name!r}")
