"""Interactive approver — implements the ``Approver`` port via a synchronous
callback (defaults to a terminal prompt). Blocking happens here, inside the
adapter; the core only ever sees the returned :class:`Decision`.
"""
from __future__ import annotations

import json

from ..core.models import Decision, ToolCall


def _terminal_prompt(call: ToolCall) -> Decision:
    args = json.dumps(call.arguments, ensure_ascii=False)
    print(f"\n[approval] {call.name}({args})")
    ans = input("approve / reject / edit? [a/r/e] ").strip().lower()
    if ans.startswith("r"):
        return Decision(verdict="reject", reason=input("reason: ").strip())
    if ans.startswith("e"):
        raw = input("new JSON args: ").strip()
        try:
            return Decision(verdict="edit", arguments=json.loads(raw))
        except (ValueError, TypeError):
            return Decision(verdict="reject", reason="invalid edit JSON")
    return Decision(verdict="approve")


class InteractiveApprover:
    """Asks a human (or any ``ask(call) -> Decision`` callback) to review each
    gated call."""

    def __init__(self, ask=None):
        self.ask = ask or _terminal_prompt

    def review(self, call: ToolCall) -> Decision:
        return self.ask(call)
