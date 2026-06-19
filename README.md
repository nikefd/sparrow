# 🐦 sparrow

**A small-but-complete agent harness.**

> [English](README.md) | [中文](README.zh-CN.md)

Bring your own tools and a system prompt; sparrow wires them into a ReAct loop
with citations, three-tier memory, and a restricted-expression engine for safe
computed panels. Stdlib-only core, zero heavy dependencies — no LangChain, no
LangGraph.

## Why sparrow

Most agent frameworks are big. sparrow is the opposite: a single readable
package you can fully understand in an afternoon, yet it has all the organs of a
real agent:

- **ReAct tool loop** — the model decides *what* it needs; deterministic code
  decides *how* to get it.
- **Tool injection** — the engine assumes nothing about your domain. You inject
  plain functions as tools; finance, news, weather — all the same engine.
- **Three-tier memory** — conversations, materialized panels, and an append-only
  journal, all in one SQLite file, physically isolated from your business data.
- **LLM emits declarations, not code** — even custom panel columns are a
  *restricted expression* (AST allowlist: field names + numbers + arithmetic),
  so the model can compose derived metrics but never run arbitrary code.
- **Citations by construction** — every tool result carries a `source`; final
  answers collect them automatically.

## Install

```bash
pip install sparrow-agent          # import name is `sparrow`
```

The core engine is stdlib-only. Point it at any OpenAI-compatible endpoint
(DeepSeek by default) via env or `configure()`:

```bash
export SPARROW_LLM_API_KEY=sk-...
export SPARROW_LLM_BASE_URL=https://api.deepseek.com   # optional
export SPARROW_LLM_MODEL=deepseek-chat                 # optional
```

## Quickstart

```python
from sparrow import tool, AgentConfig, Harness

@tool(description="Get current weather", source="demo-weather")
def get_weather(city: str) -> dict:
    return {"city": city, "weather": "sunny, 24°C"}

config = AgentConfig(
    system_prompt="You are a weather assistant. Always call a tool; never invent weather.",
    tools=[get_weather],
)

for event in Harness(config).run([{"role": "user", "content": "Weather in Beijing?"}]):
    print(event)   # tool_call / tool_result / final / error
```

See [`examples/weather_agent.py`](examples/weather_agent.py) for a full run.

## Memory & panels (optional)

For dashboard-style apps, sparrow ships "panel as memory": the agent can persist
a conversation insight as a live, declarative panel.

```python
from sparrow import Memory, AgentConfig, panel_tools

mem = Memory("ui.db", transforms={"count": lambda d: {"value": len(next(iter(d.values()), []))}})

config = AgentConfig(
    system_prompt="...",
    tools=[*my_query_tools, *panel_tools(mem)],   # adds create/archive/list_panels
    recall_provider=mem.journal_summary_for_prompt,  # inject episodic recall
)
```

Panels store *recipes* (a tool + transform/columns), not snapshots, so they
recompute from live data every time. Custom table columns use the restricted
expression engine:

```python
{"title": "Market Value", "expr": "current_price * shares"}   # safe
{"title": "x", "expr": "__import__('os')"}                    # rejected
```

## Design principles

1. **LLM decides *what*, deterministic code decides *how*.** The model only ever
   emits declarations (which tool, which transform, which column expression);
   real execution is plain Python. This prevents hallucinated data and confines
   the model to a read-only, validated surface.
2. **Read/write separation.** Query tools read your business data; write tools
   only touch the agent's own memory db. The LLM can shape presentation, never
   the underlying truth.
3. **Memory covers every actor.** The journal records what the user did, what
   the agent did, and what the system did — so the agent's worldview is complete.

## Status

`v0.1` — extracted from two production agents (a quant-trading assistant and an
AI-frontier tracker) and generalized. API may still move before `1.0`.

MIT licensed.
