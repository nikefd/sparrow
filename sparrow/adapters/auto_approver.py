"""Auto approver — implements the ``Approver`` port by approving everything,
optionally filtered through a host callback. The default for non-interactive
runs; pair with ``writes=True`` tools only when the host has its own guardrails.
"""
from __future__ import annotations

from ..core.models import Decision, ToolCall


class AutoApprover:
    """Approves every call. If ``policy(call) -> Decision`` is given, defers to it
    (so a host can auto-reject or edit without a human in the loop)."""

    def __init__(self, policy=None):
        self.policy = policy

    def review(self, call: ToolCall) -> Decision:
        if self.policy is not None:
            return self.policy(call)
        return Decision(verdict="approve")
