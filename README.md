# 🐦 sparrow

**A small-but-complete agent harness.** 麻雀虽小，五脏俱全。

Bring your own tools and a system prompt; sparrow wires them into a ReAct loop
with citations, three-tier memory, and a restricted-expression engine for safe
computed panels. Stdlib-only core, zero heavy dependencies — no LangChain, no
LangGraph.

> [English](#english) · [中文](#中文)

---

## English

### Why sparrow

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

### Install

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

### Quickstart

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

### Memory & panels (optional)

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

### Design principles

1. **LLM decides *what*, deterministic code decides *how*.** The model only ever
   emits declarations (which tool, which transform, which column expression);
   real execution is plain Python. This prevents hallucinated data and confines
   the model to a read-only, validated surface.
2. **Read/write separation.** Query tools read your business data; write tools
   only touch the agent's own memory db. The LLM can shape presentation, never
   the underlying truth.
3. **Memory covers every actor.** The journal records what the user did, what
   the agent did, and what the system did — so the agent's worldview is complete.

### Status

`v0.1` — extracted from two production agents (a quant-trading assistant and an
AI-frontier tracker) and generalized. API may still move before `1.0`.

MIT licensed.

---

## 中文

### 为什么是 sparrow

大多数 agent 框架都很重。sparrow 反其道而行：一个一下午就能读透的单包，却五脏俱全：

- **ReAct 工具循环** —— LLM 决定「要什么」，确定性代码决定「怎么做」。
- **工具注入** —— 引擎对业务零假设。你把普通函数注入成工具；金融、新闻、天气，同一套引擎。
- **三层记忆** —— 对话、物化面板、append-only 流水，同一个 SQLite 文件，与业务数据物理隔离。
- **LLM 只产声明，不产代码** —— 连自定义面板列都是「受限表达式」（AST 白名单：字段名+数字+四则运算），模型能组合衍生指标，却碰不到任意代码。
- **天生带溯源** —— 每个工具结果带 `source`，最终答案自动收集成 citations。

### 安装

```bash
pip install sparrow-agent          # import 名是 sparrow
```

核心引擎零三方依赖（仅 stdlib）。指向任意 OpenAI 兼容端点（默认 DeepSeek）：

```bash
export SPARROW_LLM_API_KEY=sk-...
```

### 快速开始

```python
from sparrow import tool, AgentConfig, Harness

@tool(description="查天气", source="demo")
def get_weather(city: str) -> dict:
    return {"city": city, "weather": "晴, 24°C"}

config = AgentConfig(
    system_prompt="你是天气助手，必须调工具拿真实数据，绝不编造。",
    tools=[get_weather],
)

for event in Harness(config).run([{"role": "user", "content": "北京天气？"}]):
    print(event)
```

### 设计理念

1. **LLM 决定「要什么」，确定性代码决定「怎么做」。** 模型永远只产声明（用哪个工具、哪种 transform、哪个列表达式），真正执行都是普通代码。防幻觉，且把模型限制在只读、已校验的边界内。
2. **读写分级。** 查询工具读业务数据，写工具只动 agent 自己的记忆库。LLM 能塑造呈现，永远碰不到底层真相。
3. **记忆覆盖所有 actor。** 流水记录人做的、AI 做的、系统做的——agent 的世界观才完整。

### 状态

`v0.1` —— 从两个生产 agent（A股量化助手 + AI 前沿追踪）抽取并通用化而来。`1.0` 前 API 可能调整。

MIT 协议。
