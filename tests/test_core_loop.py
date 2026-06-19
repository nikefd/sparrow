"""Core loop tests — exercise every branch of the step reducer with fakes.

No network, no real LLM. The loop talks only to ports, so we inject scripted
fakes and assert on the (state, events) it produces.
"""
from sparrow.core import budget, schema
from sparrow.core.loop import Deps, step
from sparrow.core.models import (Completion, Decision, Message, RunState, Skill,
                                 ToolCall)
from sparrow.adapters.memory_store import MemoryStore
from sparrow.tools.registry import ToolRegistry, tool


# ── fakes ─────────────────────────────────────────────────────────────────────
class FakeLLM:
    def __init__(self, completions):
        self.completions = list(completions)
        self.calls = []

    def complete(self, messages, *, tools=None, response_format=None,
                 max_tokens=2000, temperature=0.3):
        self.calls.append({"tools": tools, "response_format": response_format})
        return self.completions.pop(0)


class FakeApprover:
    def __init__(self, decision):
        self.decision = decision

    def review(self, call):
        return self.decision(call) if callable(self.decision) else self.decision


class FakeSummarizer:
    def summarize(self, messages):
        return Message(role="system", content=f"[summary of {len(messages)} msgs]")


class FakeSub:
    def run(self, task, *, tools, skills):
        return f"sub-result for {task}"


# ── tools ─────────────────────────────────────────────────────────────────────
@tool(description="echo", source="demo")
def echo(text: str = "") -> dict:
    return {"text": text}


@tool(description="write a note", source="db", writes=True)
def save_note(note: str = "", conversation_id: str = "") -> dict:
    return {"ok": True, "note": note}


def comp_tool(name, args, id="c1"):
    return Completion(tool_calls=[ToolCall(id=id, name=name, arguments=args)], stop_reason="tool_calls")


def comp_final(text):
    return Completion(content=text, stop_reason="stop")


def drive(state, deps, store=None, max_steps=20):
    events = []
    for _ in range(max_steps):
        state, ev = step(state, deps)
        if store:
            store.save(state.run_id, state)
        events += ev
        if state.status != "running":
            break
    return state, events


# ── budget ─────────────────────────────────────────────────────────────────────
def test_over_budget_and_split():
    big = [Message(role="user", content="x" * 4000)]
    assert budget.over_budget(big, limit=100)
    assert not budget.over_budget(big, limit=100000)
    msgs = [Message(role="system", content="s")] + [Message(role="user", content=str(i)) for i in range(10)]
    head, tail = budget.split_oldest(msgs, keep_recent=3)
    assert len(tail) == 3 and len(head) == 7


# ── stop-reason branches ───────────────────────────────────────────────────────
def test_final_no_tools():
    deps = Deps(llm=FakeLLM([comp_final("hello")]), tools=ToolRegistry([echo]))
    state = RunState(run_id="r", messages=[Message(role="system", content="sys"),
                                           Message(role="user", content="hi")])
    state, events = drive(state, deps)
    assert state.status == "done"
    assert state.final["content"] == "hello"
    assert any(e.type == "final" for e in events)


def test_tool_then_final_collects_citation():
    deps = Deps(llm=FakeLLM([comp_tool("echo", {"text": "hey"}), comp_final("done")]),
                tools=ToolRegistry([echo]))
    state = RunState(run_id="r", messages=[Message(role="user", content="hi")])
    state, events = drive(state, deps)
    assert state.status == "done"
    assert "demo" in state.final["citations"]
    assert {"tool_call", "tool_result", "final"} <= {e.type for e in events}


def test_length_triggers_continuation():
    deps = Deps(llm=FakeLLM([Completion(content="partial", stop_reason="length"),
                             comp_final("complete")]), tools=ToolRegistry([]))
    state = RunState(run_id="r", messages=[Message(role="user", content="long")])
    state, events = drive(state, deps)
    assert state.status == "done"
    assert state.final["content"] == "complete"
    assert "partial" in [m.content for m in state.messages]


def test_content_filter_errors():
    deps = Deps(llm=FakeLLM([Completion(stop_reason="content_filter")]), tools=ToolRegistry([]))
    state = RunState(run_id="r", messages=[Message(role="user", content="x")])
    state, events = drive(state, deps)
    assert state.status == "error"
    assert any(e.type == "error" for e in events)


# ── compaction ─────────────────────────────────────────────────────────────────
def test_compaction_replaces_oldest():
    msgs = [Message(role="system", content="sys")] + \
           [Message(role="user", content="x" * 8000) for _ in range(5)]
    deps = Deps(llm=FakeLLM([comp_final("ok")]), tools=ToolRegistry([]),
                summarizer=FakeSummarizer(), token_budget=100, keep_recent=2)
    state = RunState(run_id="r", messages=msgs)
    state, events = drive(state, deps, max_steps=3)
    assert any(e.type == "compacted" for e in events)
    assert any("summary of" in m.content for m in state.messages)


# ── approval (human in the loop) ───────────────────────────────────────────────
def test_approval_pause_and_reject():
    deps = Deps(llm=FakeLLM([comp_tool("save_note", {"note": "hi"}), comp_final("after")]),
                tools=ToolRegistry([save_note]),
                approver=FakeApprover(Decision(verdict="reject", reason="nope")))
    state = RunState(run_id="r", messages=[Message(role="user", content="save")])
    state, ev = step(state, deps)                       # tool call → pause
    assert state.status == "awaiting_approval"
    assert state.pending_approval.name == "save_note"
    assert state.pending_approval.arguments.get("conversation_id") == "r"   # injected
    assert any(e.type == "awaiting_approval" for e in ev)
    state, ev = step(state, deps)                       # resume → reject
    assert state.status == "running"
    assert any(m.role == "tool" and "rejected" in m.content for m in state.messages)
    state, ev = step(state, deps)                       # final
    assert state.status == "done"


def test_approval_edit_rewrites_args():
    deps = Deps(llm=FakeLLM([comp_tool("save_note", {"note": "orig"}), comp_final("ok")]),
                tools=ToolRegistry([save_note]),
                approver=FakeApprover(Decision(verdict="edit", arguments={"note": "edited"})))
    state = RunState(run_id="r", messages=[Message(role="user", content="save")])
    state, _ = step(state, deps)                        # pause
    state, _ = step(state, deps)                        # resume → edit
    tool_msgs = [m for m in state.messages if m.role == "tool"]
    assert "edited" in tool_msgs[0].content


# ── skills (progressive disclosure) ────────────────────────────────────────────
def test_skill_activation_unlocks_tools():
    @tool(description="secret tool", source="s")
    def secret(x: str = "") -> dict:
        return {"x": x}

    skill = Skill(name="math", when="for math", instructions="Use secret carefully", tools=["secret"])
    deps = Deps(llm=FakeLLM([comp_tool("activate_skill", {"name": "math"})]),
                tools=ToolRegistry([secret]))
    state = RunState(run_id="r", messages=[Message(role="user", content="hi")], skills=[skill])

    names0 = [s["function"]["name"] for s in schema.specs_for(deps.tools, state.skills)]
    assert "activate_skill" in names0 and "secret" not in names0   # hidden until active

    state, ev = step(state, deps)
    assert any(s.active for s in state.skills)
    assert any(e.type == "skill_activated" for e in ev)
    names1 = [s["function"]["name"] for s in schema.specs_for(deps.tools, state.skills)]
    assert "secret" in names1                                      # now visible


def test_activate_unknown_skill_errors():
    deps = Deps(llm=FakeLLM([comp_tool("activate_skill", {"name": "ghost"})]),
                tools=ToolRegistry([]))
    state = RunState(run_id="r", messages=[Message(role="user", content="hi")],
                     skills=[Skill(name="real", when="w")])
    state, ev = step(state, deps)
    assert any(m.role == "tool" and "unknown" in m.content for m in state.messages)


# ── delegation ─────────────────────────────────────────────────────────────────
def test_delegate_folds_subagent_result():
    deps = Deps(llm=FakeLLM([comp_tool("delegate", {"task": "do x"}), comp_final("done")]),
                tools=ToolRegistry([]), subagent=FakeSub())
    state = RunState(run_id="r", messages=[Message(role="user", content="hi")])
    state, ev = step(state, deps)
    assert any(e.type == "delegated" for e in ev)
    assert any(m.role == "tool" and "sub-result" in m.content for m in state.messages)


# ── structured output ──────────────────────────────────────────────────────────
def test_structured_output_parses():
    llm = FakeLLM([Completion(content='{"answer": "42"}', stop_reason="stop")])
    deps = Deps(llm=llm, tools=ToolRegistry([]))
    state = RunState(run_id="r", messages=[Message(role="user", content="q")],
                     output_schema={"type": "object"})
    state, ev = drive(state, deps)
    assert state.status == "done"
    assert state.final["structured"] == {"answer": "42"}
    assert llm.calls[0]["response_format"] == {"type": "json_object"}


# ── checkpoint / resume ────────────────────────────────────────────────────────
def test_checkpoint_roundtrip():
    store = MemoryStore()
    s = RunState(run_id="r",
                 messages=[Message(role="user", content="hi"),
                           Message(role="assistant",
                                   tool_calls=[ToolCall(id="1", name="t", arguments={"a": 1})])],
                 skills=[Skill(name="k", when="w", active=True)], round=3, citations=["x"])
    store.save("r", s)
    assert store.load("r") == s
    assert store.load("missing") is None


def test_resume_after_approval_across_reload():
    store = MemoryStore()
    deps = Deps(llm=FakeLLM([comp_tool("save_note", {"note": "hi"}), comp_final("ok")]),
                tools=ToolRegistry([save_note]),
                approver=FakeApprover(Decision(verdict="approve")), store=store)
    state = RunState(run_id="r", messages=[Message(role="user", content="save")])
    state, _ = drive(state, deps, store=store)
    assert state.status == "awaiting_approval"
    # simulate restart: reload from store and resume
    reloaded = store.load("r")
    reloaded, _ = drive(reloaded, deps, store=store)
    assert reloaded.status == "done"
    assert any(m.role == "tool" and '"ok": true' in m.content for m in reloaded.messages)


# ── round budget ───────────────────────────────────────────────────────────────
def test_round_cap_forces_finalize():
    # model keeps calling tools; after max_rounds the forced close-out asks once
    # more (the 4th call) and that answer is what finalizes.
    looping = [comp_tool("echo", {"text": "x"}, id=f"c{i}") for i in range(3)]
    deps = Deps(llm=FakeLLM(looping + [comp_final("forced")]), tools=ToolRegistry([echo]))
    state = RunState(run_id="r", messages=[Message(role="user", content="go")], max_rounds=3)
    state, events = drive(state, deps, max_steps=30)
    assert state.status == "done"
    assert state.final["content"] == "forced"
