"""Sub-agent runner — implements the ``SubAgentRunner`` port by running a
delegated task in a fresh, isolated :class:`Agent`.

The child gets its own RunState and an ephemeral in-memory store (its checkpoints
never mix with the parent's), an optionally-restricted subset of the parent's
tools/skills, and delegation disabled so it cannot recurse forever. Its final
answer is returned as plain text for the parent loop to fold in as a tool result.
"""
from __future__ import annotations

import json

from ..adapters.memory_store import MemoryStore
from ..core.models import Message


class SubAgentRunner:
    def __init__(self, parent):
        self.parent = parent

    def run(self, task: str, *, tools: list, skills: list) -> str:
        from .agent import Agent           # local import avoids a config/agent cycle
        from .config import AgentConfig

        pcfg = self.parent.config
        child_tools = [t for t in pcfg.tools if not tools or t.name in tools]
        child_skills = [s for s in pcfg.skills if not skills or s.name in skills]
        child_cfg = AgentConfig(
            system_prompt=pcfg.system_prompt + "\n\nYou are a sub-agent handling one "
            "delegated subtask. Complete it and report the result concisely.",
            tools=child_tools, skills=child_skills,
            max_rounds=pcfg.max_rounds, token_budget=pcfg.token_budget,
            enable_delegation=False,        # no recursive delegation
        )
        child = Agent(child_cfg, llm=self.parent.llm, store=MemoryStore(),
                      approver=self.parent.approver, clock=self.parent.clock,
                      summarizer=self.parent.summarizer)

        final = ""
        for ev in child.run([Message(role="user", content=task)]):
            if ev.type == "final":
                final = ev.data.get("content") or json.dumps(
                    ev.data.get("structured", ""), ensure_ascii=False)
            elif ev.type == "error":
                final = f"sub-agent error: {ev.data.get('message') or ev.data.get('error', '')}"
        return final
