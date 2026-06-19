"""Engine smoke tests — exercise registry, expr, and memory without any network
or LLM calls."""
import os
import tempfile

import pytest

from sparrow import tool, AgentConfig, ToolRegistry, Memory, safe_eval, is_safe_expr
from sparrow import panel_data


# ── tool / registry ──────────────────────────────────────────────────
def test_tool_decorator_introspects_schema():
    @tool(description="add two", source="calc")
    def add(a: int, b: int = 0) -> dict:
        return {"sum": a + b}

    assert add.name == "add"
    assert add.schema["properties"]["a"]["type"] == "integer"
    assert add.schema["required"] == ["a"]          # b has a default
    assert add.source == "calc"


def test_registry_runs_and_attaches_source():
    @tool(description="echo", source="demo")
    def echo(text: str = "") -> dict:
        return {"text": text}

    reg = ToolRegistry([echo])
    assert "echo" in reg
    out = reg.run("echo", {"text": "hi"})
    assert out == {"text": "hi", "source": "demo"}   # source auto-attached
    assert reg.run("nope", {})["error"].startswith("unknown tool")


def test_registry_openai_specs_shape():
    @tool(description="d")
    def t(x: str = "") -> dict:
        return {}
    spec = ToolRegistry([t]).openai_specs()[0]
    assert spec["type"] == "function"
    assert spec["function"]["name"] == "t"


def test_args_dict_style_tool():
    @tool(name="raw", description="raw-style")
    def raw(args):
        return {"got": args.get("k")}
    assert ToolRegistry([raw]).run("raw", {"k": 9}) == {"got": 9}


# ── expr ──────────────────────────────────────────────────────────────
def test_safe_eval_arithmetic():
    assert safe_eval("current_price * shares", {"current_price": 10, "shares": 100}) == 1000
    assert safe_eval("(a - b) / b * 100", {"a": 110, "b": 100}) == 10.0


@pytest.mark.parametrize("evil", [
    "__import__('os').system('ls')",
    "shares.__class__",
    "[x for x in range(9)]",
    "open('/etc/passwd')",
])
def test_is_safe_expr_blocks_evil(evil):
    assert is_safe_expr(evil) is False


def test_is_safe_expr_allows_arithmetic():
    assert is_safe_expr("a * b + 3") is True


# ── memory ────────────────────────────────────────────────────────────
@pytest.fixture
def mem():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    m = Memory(path, transforms={"count": lambda d: {"value": len(next(iter(d.values()), []))}})
    yield m
    os.unlink(path)


def test_conversation_roundtrip(mem):
    mem.add_message("c1", "user", "hello")
    mem.add_message("c1", "assistant", "hi", meta={"citations": ["demo"]})
    msgs = mem.get_messages("c1")
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["citations"] == ["demo"]
    assert mem.message_count("c1") == 2


def test_journal_append_and_summary(mem):
    mem.journal_append("agent", "tool", "create_panel", detail="made X")
    assert "create_panel" in mem.journal_summary_for_prompt()


def test_panel_create_validate_archive(mem):
    mem.tool_names = {"q"}
    spec = {"id": "p1", "title": "P", "viz": "metric-card", "query": {"tool": "q"}, "transform": "count"}
    assert mem.create_panel(spec)["ok"] is True
    assert any(p["id"] == "p1" for p in mem.list_panels())
    assert mem.archive_panel("p1")["ok"] is True
    assert not any(p["id"] == "p1" for p in mem.list_panels())


def test_panel_spec_rejects_unknown_tool(mem):
    mem.tool_names = {"q"}
    bad = {"id": "p2", "title": "P", "viz": "table", "query": {"tool": "nope"}}
    assert "error" in mem.create_panel(bad)


def test_panel_spec_rejects_unsafe_expr(mem):
    mem.tool_names = {"q"}
    bad = {"id": "p3", "title": "P", "viz": "table", "query": {"tool": "q"},
           "columns": [{"title": "x", "expr": "__import__('os')"}]}
    assert "error" in mem.create_panel(bad)


# ── panel_data resolve ────────────────────────────────────────────────
def test_panel_data_resolve_with_columns(mem):
    @tool(name="q", description="data")
    def q(args):
        return {"rows": [{"price": 10, "qty": 2}, {"price": 5, "qty": 3}]}
    reg = ToolRegistry([q])
    mem.tool_names = {"q"}
    mem.create_panel({"id": "pv", "title": "V", "viz": "table", "query": {"tool": "q"},
                      "columns": [{"title": "total", "expr": "price * qty"}]})
    out = panel_data.resolve("pv", mem, reg)
    assert out["data"]["rows"] == [{"total": 20}, {"total": 15}]


# ── config ────────────────────────────────────────────────────────────
def test_agent_config_builds_registry():
    @tool(description="x")
    def x() -> dict:
        return {}
    cfg = AgentConfig(system_prompt="hi", tools=[x])
    assert "x" in cfg.registry()
