"""Tools battery tests — registry, restricted expr, panels, and the built-in
tool set (read-only directly; dangerous ones via the registry, checking the
writes flag and the root sandbox)."""
import os
import tempfile

import pytest

from sparrow.tools.builtins import builtins
from sparrow.tools.expr import is_safe_expr, safe_eval
from sparrow.tools.panels import Memory, panel_tools, resolve
from sparrow.tools.registry import ToolRegistry, tool


# ── registry ──────────────────────────────────────────────────────────────────
def test_tool_introspects_schema_and_runs():
    @tool(description="add", source="calc")
    def add(a: int, b: int = 0) -> dict:
        return {"sum": a + b}

    assert add.schema["properties"]["a"]["type"] == "integer"
    assert add.schema["required"] == ["a"]
    reg = ToolRegistry([add])
    assert reg.run("add", {"a": 2, "b": 3}) == {"sum": 5, "source": "calc"}
    assert reg.run("nope", {})["error"].startswith("unknown tool")


def test_args_dict_style_tool():
    @tool(name="raw", description="raw")
    def raw(args):
        return {"got": args.get("k")}
    assert ToolRegistry([raw]).run("raw", {"k": 9}) == {"got": 9}


# ── expr ──────────────────────────────────────────────────────────────────────
def test_safe_eval_arithmetic():
    assert safe_eval("current_price * shares", {"current_price": 10, "shares": 100}) == 1000
    assert safe_eval("(a - b) / b * 100", {"a": 110, "b": 100}) == 10.0


@pytest.mark.parametrize("evil", ["__import__('os').system('ls')", "shares.__class__",
                                  "[x for x in range(9)]", "open('/etc/passwd')"])
def test_is_safe_expr_blocks_evil(evil):
    assert is_safe_expr(evil) is False


# ── panels (optional battery) ──────────────────────────────────────────────────
@pytest.fixture
def mem():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    m = Memory(path, transforms={"count": lambda d: {"value": len(next(iter(d.values()), []))}})
    yield m
    os.unlink(path)


def test_conversation_and_journal(mem):
    mem.add_message("c1", "user", "hello")
    mem.add_message("c1", "assistant", "hi", meta={"citations": ["demo"]})
    msgs = mem.get_messages("c1")
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["citations"] == ["demo"]
    mem.journal_append("agent", "tool", "create_panel", detail="made X")
    assert "create_panel" in mem.journal_summary_for_prompt()


def test_panel_lifecycle_and_resolve(mem):
    mem.tool_names = {"q"}

    @tool(name="q", description="data")
    def q(args):
        return {"rows": [{"price": 10, "qty": 2}, {"price": 5, "qty": 3}]}
    reg = ToolRegistry([q])

    bad = {"id": "p", "title": "P", "viz": "table", "query": {"tool": "q"},
           "columns": [{"title": "x", "expr": "__import__('os')"}]}
    assert "error" in mem.create_panel(bad)                       # unsafe expr rejected

    mem.create_panel({"id": "pv", "title": "V", "viz": "table", "query": {"tool": "q"},
                      "columns": [{"title": "total", "expr": "price * qty"}]})
    out = resolve("pv", mem, reg)
    assert out["data"]["rows"] == [{"total": 20}, {"total": 15}]
    assert mem.archive_panel("pv")["ok"] is True


def test_panel_tools_factory(mem):
    names = {t.name for t in panel_tools(mem)}
    assert names == {"create_panel", "archive_panel", "list_panels"}


# ── builtins ────────────────────────────────────────────────────────────────────
def test_builtins_read_write_roundtrip(tmp_path):
    reg = ToolRegistry(builtins(root=str(tmp_path)))
    assert reg.run("write_file", {"path": "a.txt", "content": "hello"})["ok"]
    assert reg.run("read_file", {"path": "a.txt"})["content"] == "hello"


def test_builtins_dangerous_are_write_gated():
    by_name = {t.name: t for t in builtins()}
    assert by_name["write_file"].writes and by_name["edit_file"].writes and by_name["run_bash"].writes
    assert not by_name["read_file"].writes and not by_name["grep"].writes


def test_builtins_root_sandbox_rejects_escape(tmp_path):
    reg = ToolRegistry(builtins(root=str(tmp_path)))
    out = reg.run("read_file", {"path": "../../etc/passwd"})
    assert "error" in out and "escapes sandbox" in out["error"]


def test_builtins_allow_filter():
    assert {t.name for t in builtins(allow={"read_file", "grep"})} == {"read_file", "grep"}


def test_builtins_grep_and_run_bash(tmp_path):
    (tmp_path / "f.txt").write_text("alpha\nfind-the-needle here\nbeta\n")
    reg = ToolRegistry(builtins(root=str(tmp_path)))
    hits = reg.run("grep", {"pattern": "needle", "path": "."})["hits"]
    assert len(hits) == 1 and "needle" in hits[0]["text"]
    out = reg.run("run_bash", {"command": "echo hi"})
    assert out["returncode"] == 0 and out["stdout"].strip() == "hi"
