"""Tool registry — the injection surface for host capabilities.

A tool is an ordinary function returning a dict, wrapped with metadata the
LLM/loop need. The ``@tool`` decorator introspects the signature into a JSON
Schema (via ``core.schema``); mark state-changing tools ``writes=True`` so the
loop routes them through the approval gate and journals them.

This is a battery, not core: the engine depends on the registry only through the
duck-typed ``tools()``/``get()``/``run()`` surface that ``core.loop`` uses.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..core.schema import introspect


@dataclass
class Tool:
    """A registered tool: a callable plus the metadata the LLM/loop need."""
    name: str
    fn: Callable[[dict], Any]
    description: str
    schema: dict
    label: str = ""           # short human label for UI
    source: str = ""          # default citation source if the fn omits one
    writes: bool = False      # state-changing => approval-gated + journaled

    def __call__(self, args: dict) -> Any:
        return self.fn(args or {})


def tool(_fn=None, *, name: str = "", description: str = "", schema: Optional[dict] = None,
         label: str = "", source: str = "", writes: bool = False):
    """Turn a function into a :class:`Tool`. The function may take keyword params
    (introspected into a schema) or a single ``args`` dict; either way the loop
    calls it as ``fn(args_dict)``."""
    def wrap(fn: Callable) -> Tool:
        sig = inspect.signature(fn)
        takes_args_dict = list(sig.parameters) in (["args"], ["_args"])

        def adapter(args: dict):
            if takes_args_dict:
                return fn(args)
            valid = {k: v for k, v in (args or {}).items() if k in sig.parameters}
            return fn(**valid)

        return Tool(
            name=name or fn.__name__,
            fn=adapter,
            description=description or (fn.__doc__ or "").strip().split("\n")[0],
            schema=introspect(fn, schema),
            label=label, source=source, writes=writes,
        )
    return wrap(_fn) if callable(_fn) else wrap


class ToolRegistry:
    """Holds the tools available to one agent."""

    def __init__(self, tools: Optional[list] = None):
        self._tools: dict = {}
        for t in tools or []:
            self.add(t)

    def add(self, t: Tool) -> None:
        self._tools[t.name] = t

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list:
        return list(self._tools)

    def tools(self) -> list:
        return list(self._tools.values())

    def run(self, name: str, arguments: dict) -> Any:
        """Execute a tool, auto-attaching its default source and wrapping any
        exception into ``{"error": ...}`` so one bad tool never breaks the loop."""
        t = self.get(name)
        if t is None:
            return {"error": f"unknown tool: {name}"}
        try:
            out = t(arguments or {})
            if isinstance(out, dict) and t.source and "source" not in out:
                out["source"] = t.source
            return out
        except Exception as e:  # noqa: broad-except
            return {"error": f"{type(e).__name__}: {e}"}
