"""Agent configuration — the slim injection surface for the host.

Everything domain-specific (prompt, tools, skills, output contract) lives here;
the engine reads nothing else. Compared with the old AgentConfig this drops
``history_turns`` / ``tool_result_max_chars`` knobs that the budget now owns and
the ``ui_db_path`` / ``enable_*`` flags that adapter wiring now handles.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from ..core import budget


@dataclass
class AgentConfig:
    """What the engine needs, injected by the host."""
    system_prompt: str
    tools: list = field(default_factory=list)
    skills: list = field(default_factory=list)          # list[Skill]
    output_schema: Optional[dict] = None                # structured-output contract
    max_rounds: int = 8
    token_budget: int = budget.DEFAULT_TOKEN_BUDGET
    keep_recent: int = 6
    tool_result_max_chars: int = 8000
    enable_delegation: bool = False                     # expose the `delegate` tool
    # Optional override of the approval predicate (call, tool) -> bool. Default:
    # gate tools marked writes=True (only when an approver is wired).
    needs_approval: Optional[Callable] = None
