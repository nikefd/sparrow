"""Agent — the public façade. Wires the pure core to concrete adapters and drives
the step loop, checkpointing after every round.

    for event in Agent(config).run([{"role": "user", "content": "hi"}]):
        ...

Pausing for approval ends the generator after persisting a checkpoint; the host
resumes with ``Agent(config, store=...).resume(run_id)`` once it has a verdict.
"""
from __future__ import annotations

import json
from dataclasses import replace
from typing import Iterator, Optional

from ..adapters.llm_summarizer import LLMSummarizer
from ..adapters.memory_store import MemoryStore
from ..adapters.openai_llm import OpenAILLM
from ..adapters.system_clock import SystemClock
from ..core.loop import Deps, step
from ..core.models import Event, Message, RunState
from ..tools.registry import ToolRegistry
from .config import AgentConfig
from .subagent import SubAgentRunner


class Agent:
    """Runs one agent defined by an :class:`AgentConfig`.

    Adapters are injectable (and default to the standard ones), so the same
    Agent is fully testable with fakes and runs for real with no extra wiring.
    """

    def __init__(self, config: AgentConfig, *, llm=None, store=None, approver=None,
                 clock=None, summarizer=None, subagent=None):
        self.config = config
        self.clock = clock or SystemClock()
        self.store = store or MemoryStore()
        self.llm = llm or OpenAILLM()
        self.summarizer = summarizer or LLMSummarizer(self.llm)
        self.approver = approver                       # None => no approval gating
        self.registry = ToolRegistry(config.tools)
        if subagent is not None:
            self.subagent = subagent
        elif config.enable_delegation:
            self.subagent = SubAgentRunner(self)
        else:
            self.subagent = None

    @property
    def deps(self) -> Deps:
        return Deps(
            llm=self.llm, tools=self.registry, approver=self.approver,
            clock=self.clock, summarizer=self.summarizer, subagent=self.subagent,
            store=self.store, token_budget=self.config.token_budget,
            keep_recent=self.config.keep_recent,
            tool_result_max_chars=self.config.tool_result_max_chars,
            needs_approval=self.config.needs_approval,
        )

    # ── entry points ─────────────────────────────────────────────────────────
    def run(self, user_messages, run_id: Optional[str] = None) -> Iterator[Event]:
        """Start a fresh run. ``user_messages`` may be dicts or
        :class:`Message`. Returns the event stream; the run_id is available on
        each ``awaiting_approval``/persisted state for resuming."""
        run_id = run_id or self.clock.new_id()
        state = RunState(run_id=run_id, messages=self._seed(user_messages),
                         skills=list(self.config.skills), max_rounds=self.config.max_rounds,
                         output_schema=self.config.output_schema)
        yield from self._drive(state)

    def resume(self, run_id: str) -> Iterator[Event]:
        """Resume a checkpointed run (e.g. after an approval verdict)."""
        state = self.store.load(run_id)
        if state is None:
            raise KeyError(f"no checkpoint for run {run_id}")
        # flip the paused status back to running so the driver re-enters; step's
        # pending_approval branch then resolves the verdict.
        state = replace(state, status="running")
        yield from self._drive(state)

    # ── driver ───────────────────────────────────────────────────────────────
    def _drive(self, state: RunState) -> Iterator[Event]:
        deps = self.deps
        while state.status == "running":
            state, events = step(state, deps)
            self.store.save(state.run_id, state)       # checkpoint every round
            yield from events
        # awaiting_approval: the pause event already went out; checkpoint stands,
        # waiting for resume(). done: clear the checkpoint.
        if state.status == "done":
            self.store.delete(state.run_id)

    def _seed(self, user_messages) -> list:
        system = self.config.system_prompt
        if self.config.output_schema:
            system += ("\n\nRespond with a single JSON object matching this schema:\n"
                       + json.dumps(self.config.output_schema, ensure_ascii=False))
        msgs = [Message(role="system", content=system)]
        for m in user_messages:
            if isinstance(m, Message):
                msgs.append(m)
            else:
                msgs.append(Message(role=m.get("role", "user"), content=m.get("content", "")))
        return msgs
