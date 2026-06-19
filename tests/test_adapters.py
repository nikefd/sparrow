"""Adapter tests — the network-free ones. LLM/summarizer need a real endpoint,
so we only check their construction + the pure stop_reason mapping."""
import os
import tempfile

from sparrow import ports
from sparrow.adapters.auto_approver import AutoApprover
from sparrow.adapters.interactive_approver import InteractiveApprover
from sparrow.adapters.openai_llm import OpenAILLM
from sparrow.adapters.sqlite_store import SqliteStore
from sparrow.adapters.system_clock import SystemClock
from sparrow.core.models import Decision, Message, RunState, ToolCall
from sparrow.core.schema import completion_from_openai


def test_sqlite_store_roundtrip():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        store = SqliteStore(path)
        state = RunState(run_id="r", messages=[Message(role="user", content="hi")],
                         round=2, citations=["a"])
        store.save("r", state)
        assert store.load("r") == state
        assert store.load("missing") is None
        store.delete("r")
        assert store.load("r") is None
    finally:
        os.unlink(path)


def test_system_clock():
    c = SystemClock()
    assert isinstance(c.now(), str)
    assert c.new_id() != c.new_id()


def test_auto_approver_default_and_policy():
    assert AutoApprover().review(ToolCall(id="1", name="t")).verdict == "approve"
    rejecter = AutoApprover(policy=lambda call: Decision(verdict="reject", reason="no"))
    assert rejecter.review(ToolCall(id="1", name="t")).verdict == "reject"


def test_interactive_approver_callback():
    appr = InteractiveApprover(ask=lambda call: Decision(verdict="edit", arguments={"x": 1}))
    d = appr.review(ToolCall(id="1", name="t"))
    assert d.verdict == "edit" and d.arguments == {"x": 1}


def test_stop_reason_is_preserved():
    # the essential fix: finish_reason must survive into Completion.stop_reason
    comp = completion_from_openai({"content": "hi"}, {}, stop_reason="length")
    assert comp.stop_reason == "length"


def test_adapters_satisfy_ports():
    assert isinstance(SqliteStore(":memory:"), ports.Store)
    assert isinstance(SystemClock(), ports.Clock)
    assert isinstance(AutoApprover(), ports.Approver)
    assert isinstance(InteractiveApprover(), ports.Approver)
    assert isinstance(OpenAILLM(), ports.LLM)
