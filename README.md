# 🐦 sparrow

**A small-but-complete agent harness.**

> [English](README.md) | [中文](README.zh-CN.md)

Bring your own tools and a system prompt; sparrow wires them into an agent loop
with citations, then adds the organs of a real agent — **skills, context
compaction, stop-reason handling, checkpoint/resume, sub-agent delegation,
human-in-the-loop approval, and structured output** — each in its minimal form.
Stdlib-only core, zero runtime dependencies — no LangChain, no LangGraph.

## Why sparrow

Most agent frameworks are big. sparrow is the opposite: a library you can fully
read in an afternoon, organized with **clean architecture (ports & adapters)**,
yet it has all the organs of a real agent:

- **Skills** — progressive disclosure: tools stay hidden behind a skill until the
  model activates it, so context doesn't bloat as capabilities grow.
- **Context compaction** — when the window fills, the oldest turns are summarized
  (not dropped), so conversations continue indefinitely.
- **Stop-reason handling** — truncated replies are continued, tool calls run,
  done means done. The model's `finish_reason` is never thrown away.
- **Checkpoint / resume** — run state is pure data, persisted every round; a run
  survives a crash or a pause and resumes across processes.
- **Sub-agent delegation** — hand a subtask to an isolated sub-agent.
- **Human-in-the-loop** — `writes=True` tools pause for approval; resume on a verdict.
- **Structured output** — force a JSON-schema-shaped final answer.
- **Citations by construction** — every tool result carries a `source`; finals
  collect them automatically.

The guiding principle: **the LLM emits declarations, not code.** It only chooses
which tool, which skill, which column expression — real execution is plain Python.

## Install

```bash
pip install sparrow-agent          # import name is `sparrow`
```

Point it at any OpenAI-compatible endpoint (DeepSeek by default) via env or
`configure()`:

```bash
export SPARROW_LLM_API_KEY=sk-...
export SPARROW_LLM_BASE_URL=https://api.deepseek.com   # optional
export SPARROW_LLM_MODEL=deepseek-chat                 # optional
```

## Quickstart

```python
from sparrow import tool, AgentConfig, Agent

@tool(description="Get current weather", source="demo-weather")
def get_weather(city: str) -> dict:
    return {"city": city, "weather": "sunny, 24°C"}

config = AgentConfig(
    system_prompt="You are a weather assistant. Always call a tool; never invent weather.",
    tools=[get_weather],
)

for event in Agent(config).run([{"role": "user", "content": "Weather in Beijing?"}]):
    print(event)   # Event(type=tool_call | tool_result | final | ...)
```

See [`examples/`](examples/) for full runs: `weather_agent.py`, `skills_agent.py`
(progressive disclosure), `approval_agent.py` (approval + checkpoint/resume).

## A few organs, briefly

```python
from sparrow import Skill, builtins
from sparrow.adapters.sqlite_store import SqliteStore
from sparrow.adapters.interactive_approver import InteractiveApprover

config = AgentConfig(
    system_prompt="You are a coding assistant.",
    tools=[*builtins(root="/safe/workdir")],   # opt-in fs/glob/grep/bash/http battery
    skills=[Skill(name="refactor", when="when asked to refactor code",
                  instructions="...", tools=["edit_file"])],
    output_schema={"type": "object"},          # force structured final (optional)
    enable_delegation=True,                     # allow `delegate` to a sub-agent
)

agent = Agent(config, store=SqliteStore("ck.db"), approver=InteractiveApprover())
for event in agent.run(messages, run_id="job-1"):
    if event.type == "awaiting_approval":
        ...                                     # paused & checkpointed; resume(run_id) later
```

Dangerous built-in tools (`write_file` / `edit_file` / `run_bash`) are
`writes=True`, so they route through the approver — basic tools and
human-in-the-loop are designed to pair.

## Memory & panels (optional battery)

```python
from sparrow import Memory, panel_tools
mem = Memory("ui.db", transforms={"count": lambda d: {"value": len(next(iter(d.values()), []))}})
config = AgentConfig(system_prompt="...", tools=[*my_tools, *panel_tools(mem)])
```

Panels store *recipes*, not snapshots, so they recompute from live data. Custom
columns use a restricted-expression engine (`current_price * shares` is fine;
`__import__('os')` is rejected).

## Architecture

Hexagonal: a pure `core` (loop + models, zero I/O) depends only on the Protocols
in `sparrow.ports`; concrete `adapters` (OpenAI client, sqlite store, …) are
injected by the `app` layer; optional batteries live in `sparrow.tools`. The
whole loop is one pure `step()` reducer, fully testable with fakes and no network.

## Documentation

For the full picture — the step reducer, ports & adapters, the seven
capabilities, checkpointing — see [`llmdoc/`](llmdoc/index.md), a docs system for
humans and AI agents. Start at [`llmdoc/index.md`](llmdoc/index.md).

| I want to... | Start here |
|---|---|
| Build a working agent end-to-end | [guides/how-to-build-an-agent.md](llmdoc/guides/how-to-build-an-agent.md) |
| Understand the core loop & ports/adapters | [architecture/core-and-ports.md](llmdoc/architecture/core-and-ports.md) |
| See how each capability is implemented | [architecture/capabilities.md](llmdoc/architecture/capabilities.md) |
| Look up the public API | [reference/api-reference.md](llmdoc/reference/api-reference.md) |
| Release to PyPI | [guides/how-to-release.md](llmdoc/guides/how-to-release.md) |

## Status

`v0.3` — clean-slate rewrite into a hexagonal core with the seven capabilities
above. The old `Harness` is a deprecated shim over `Agent`. API may still move
before `1.0`.

MIT licensed.
