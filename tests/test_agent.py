"""Agent (driver) tests — checkpoint lifecycle, approval pause/resume, real
sub-agent delegation, structured output. Fakes only, no network."""
from sparrow.adapters.memory_store import MemoryStore
from sparrow.app.agent import Agent
from sparrow.app.config import AgentConfig
from sparrow.core.models import Completion, Decision, ToolCall
from sparrow.tools.registry import tool


class FakeLLM:
    def __init__(self, completions):
        self.completions = list(completions)

    def complete(self, messages, *, tools=None, response_format=None,
                 max_tokens=2000, temperature=0.3):
        return self.completions.pop(0)


class FakeApprover:
    def __init__(self, decision):
        self.decision = decision

    def review(self, call):
        return self.decision


def comp_tool(name, args, id="c1"):
    return Completion(tool_calls=[ToolCall(id=id, name=name, arguments=args)], stop_reason="tool_calls")


def comp_final(text):
    return Completion(content=text, stop_reason="stop")


@tool(description="echo", source="demo")
def echo(text: str = "") -> dict:
    return {"text": text}


@tool(description="write", source="db", writes=True)
def save_note(note: str = "", conversation_id: str = "") -> dict:
    return {"ok": True}


def test_run_simple_final_and_checkpoint_cleared():
    store = MemoryStore()
    agent = Agent(AgentConfig(system_prompt="sys", tools=[echo]),
                  llm=FakeLLM([comp_final("hi")]), store=store)
    events = list(agent.run([{"role": "user", "content": "q"}], run_id="r1"))
    assert any(e.type == "final" and e.data["content"] == "hi" for e in events)
    assert store.load("r1") is None          # checkpoint cleared on done


def test_run_checkpoints_each_round():
    store = MemoryStore()
    agent = Agent(AgentConfig(system_prompt="sys", tools=[echo]),
                  llm=FakeLLM([comp_tool("echo", {"text": "x"}), comp_final("done")]),
                  store=store)
    # consume one event then peek the store mid-run
    gen = agent.run([{"role": "user", "content": "q"}], run_id="r2")
    next(gen)                                 # advance past the first round
    assert store.load("r2") is not None       # a checkpoint exists mid-run
    list(gen)                                 # finish
    assert store.load("r2") is None


def test_approval_pause_then_resume():
    store = MemoryStore()
    agent = Agent(AgentConfig(system_prompt="sys", tools=[save_note]),
                  llm=FakeLLM([comp_tool("save_note", {"note": "hi"}), comp_final("ok")]),
                  store=store, approver=FakeApprover(Decision(verdict="approve")))
    events = list(agent.run([{"role": "user", "content": "save"}], run_id="r3"))
    pause = next(e for e in events if e.type == "awaiting_approval")
    assert pause.data["run_id"] == "r3"
    assert store.load("r3").status == "awaiting_approval"     # checkpoint persists
    # resume with the verdict
    events2 = list(agent.resume("r3"))
    assert any(e.type == "final" for e in events2)
    assert store.load("r3") is None


def test_delegation_runs_isolated_subagent():
    # parent delegates; the child shares the same FakeLLM, so the script
    # interleaves: parent-delegate, child-final, parent-final.
    agent = Agent(AgentConfig(system_prompt="sys", tools=[echo], enable_delegation=True),
                  llm=FakeLLM([comp_tool("delegate", {"task": "subtask"}),
                               comp_final("child answer"),
                               comp_final("parent answer")]),
                  store=MemoryStore())
    events = list(agent.run([{"role": "user", "content": "go"}], run_id="r4"))
    assert any(e.type == "delegated" for e in events)
    assert any(e.type == "final" and e.data["content"] == "parent answer" for e in events)


def test_structured_output_through_facade():
    agent = Agent(AgentConfig(system_prompt="sys", output_schema={"type": "object"}),
                  llm=FakeLLM([Completion(content='{"answer": 42}', stop_reason="stop")]),
                  store=MemoryStore())
    events = list(agent.run([{"role": "user", "content": "q"}], run_id="r5"))
    final = next(e for e in events if e.type == "final")
    assert final.data["structured"] == {"answer": 42}


def test_resume_unknown_run_raises():
    agent = Agent(AgentConfig(system_prompt="sys"), llm=FakeLLM([]), store=MemoryStore())
    try:
        list(agent.resume("nope"))
        assert False, "expected KeyError"
    except KeyError:
        pass
