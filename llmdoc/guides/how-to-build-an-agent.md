# 如何搭一个 agent

> 端到端走一遍：定义工具 → 组装 config → 跑 Agent → 消费事件流 →（可选）skill /
> 审批+checkpoint / 子 agent / 结构化输出 / 基础工具电池 → 前端。背后原理见
> [核心与 ports 架构](../architecture/core-and-ports.md)、[七大能力](../architecture/capabilities.md)。
> 可跑示例：`examples/`。

## 前置：配置 LLM

```bash
export SPARROW_LLM_API_KEY=sk-...                       # 必填
export SPARROW_LLM_BASE_URL=https://api.deepseek.com    # 可选,默认即此
export SPARROW_LLM_MODEL=deepseek-chat                  # 可选
```

或代码里 `from sparrow import configure; configure(api_key="sk-...")`。没配 key 第一次
LLM 调用抛 `LLMError`。

## 1. 定义工具

```python
from sparrow import tool

@tool(description="Get current weather", source="demo-weather", label="weather")
def get_weather(city: str) -> dict:
    return {"city": city, "weather": "sunny, 24°C"}
```

- 参数自省成 JSON Schema；也支持单 `args` dict 风格。
- 带 `source` 自动溯源；**状态写入类**加 `writes=True`（会被审批门拦、并注入 `run_id`
  作 `conversation_id`）。

## 2. 组装 AgentConfig

```python
from sparrow import AgentConfig

config = AgentConfig(
    system_prompt="You are a weather assistant. Always call a tool; never invent weather.",
    tools=[get_weather],
    max_rounds=8,             # 循环上限
    token_budget=12000,       # 超过则触发压缩
)
```

> system prompt 必须明确要求「答案只能来自工具结果」，才让 citations 名副其实、防住幻觉。

## 3. 跑 Agent，消费事件流

`run()` 是生成器，yield `Event(type, data)`：

```python
from sparrow import Agent

for event in Agent(config).run([{"role": "user", "content": "Weather in Beijing?"}]):
    if event.type == "tool_call":
        print("→", event.data["name"], event.data["arguments"])
    elif event.type == "tool_result":
        print("←", event.data["summary"])
    elif event.type == "final":
        print(event.data["content"], "sources:", event.data["citations"])
```

事件类型全集见 [核心架构 §4a](../architecture/core-and-ports.md#4a-事件流协议)。

## 4. Skill（渐进式披露）

把工具藏在 skill 后面，模型用到才激活：

```python
from sparrow import Skill

finance = Skill(name="finance", when="for interest / investment questions",
                instructions="Use compound_interest; state assumptions.",
                tools=["compound_interest"])
config = AgentConfig(system_prompt="...", tools=[compound_interest], skills=[finance])
```

激活前模型只看到 `activate_skill` 伪工具 + 各 skill 的 `when`；调
`activate_skill("finance")` 后该 skill 的工具与说明才展开。见 `examples/skills_agent.py`。

## 5. 审批 + Checkpoint/Resume（人在环中）

给 `Agent` 配 `approver` + 持久化 `store`，写工具会暂停等批准：

```python
from sparrow import Agent
from sparrow.adapters.sqlite_store import SqliteStore
from sparrow.adapters.interactive_approver import InteractiveApprover

agent = Agent(config, store=SqliteStore("checkpoints.db"), approver=InteractiveApprover())

run_id = None
for event in agent.run(messages, run_id="job-1"):
    if event.type == "awaiting_approval":
        run_id = event.data["run_id"]      # 暂停了,checkpoint 已落盘

# ……拿到批准（甚至进程重启后）……
for event in agent.resume(run_id):         # 从断点续跑
    ...
```

`AutoApprover(policy=...)` 可做非交互的程序化审批。见 `examples/approval_agent.py`。

## 6. 基础工具电池

`builtins()` 给 agent 开箱即用的 fs/glob/grep/bash/http 能力（opt-in、可 `root` 沙箱）：

```python
from sparrow import builtins
config = AgentConfig(
    system_prompt="You are a coding assistant.",
    tools=[*builtins(root="/safe/workdir", allow={"read_file", "grep", "write_file"})],
)
```

危险三件套（`write_file`/`edit_file`/`run_bash`）是 `writes=True`，配上第 5 节的
approver 就会逐次要批准。

## 7. 子 agent 委派 & 结构化输出

```python
# 委派:开启后模型可调 delegate 把子任务丢给隔离子 agent
config = AgentConfig(system_prompt="...", tools=[...], enable_delegation=True)

# 结构化输出:强制最终结果是符合 schema 的 JSON
config = AgentConfig(system_prompt="...", output_schema={"type": "object",
                     "properties": {"answer": {"type": "string"}}})
# final 事件:event.data["structured"] == {"answer": "..."}
```

## 8. 面板即记忆（可选电池）

```python
from sparrow import Memory, panel_tools
mem = Memory("ui.db", transforms={"count": lambda d: {"value": len(next(iter(d.values()), []))}})
config = AgentConfig(system_prompt="...", tools=[*my_tools, *panel_tools(mem)])
```

面板存配方非快照，列表达式走受限引擎。详见 `sparrow/tools/panels.py`。

## 9. 前端聊天组件

`sparrow-chat.js` 对接 `Agent.run()` 的 SSE 事件流。定位资源：

```python
from sparrow.web import asset_path   # -> .../sparrow-chat.js
```

服务端契约、挂载选项与 i18n 见 `sparrow/web/README.md`。

## 10. 跑测试

```bash
pip install -e ".[dev]"
python -m pytest -q          # 纯本地,无网络无 LLM
```
