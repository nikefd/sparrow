# 如何搭一个 agent

> 端到端走一遍：定义工具 → 组装 config → 跑 Harness → 消费事件流 →（可选）加
> 记忆与面板 →（可选）挂前端聊天组件。背后原理见
> [引擎架构](../architecture/engine-architecture.md)。完整可跑示例：
> `examples/weather_agent.py`。

## 前置：配置 LLM

sparrow 需要一个 OpenAI 兼容端点。env 或 `configure()` 二选一：

```bash
export SPARROW_LLM_API_KEY=sk-...                       # 必填
export SPARROW_LLM_BASE_URL=https://api.deepseek.com    # 可选，默认即此
export SPARROW_LLM_MODEL=deepseek-chat                  # 可选
```

或在代码里（宿主注入自己的凭证，不动 env）：

```python
from sparrow import configure
configure(api_key="sk-...", base_url="https://api.deepseek.com", model="deepseek-chat")
```

没配 api key 时第一次 `chat()` 会抛 `LLMError`。

## 1. 定义工具

工具就是返回 dict 的普通函数，用 `@tool` 装饰。带 `source` 就能自动溯源：

```python
from sparrow import tool

@tool(description="Get current weather", source="demo-weather", label="weather")
def get_weather(city: str) -> dict:
    return {"city": city, "weather": "sunny, 24°C"}
```

- 参数会被自省成 JSON Schema：有类型注解更准，有默认值的参数不进 `required`。
- 也可以用单 `args` dict 风格：`def raw(args): return {...}`。
- **状态写入类**工具加 `writes=True`，会被 `Harness` 记进 journal，并自动注入
  `conversation_id`。

## 2. 组装 AgentConfig

```python
from sparrow import AgentConfig

config = AgentConfig(
    system_prompt=(
        "You are a weather assistant. Always call a tool to get real data; "
        "never invent weather."          # ← 关键：强制「只从工具结果作答」
    ),
    tools=[get_weather],
    max_tool_rounds=6,        # ReAct 最多几轮
    history_turns=20,         # 保留最近多少条消息
)
```

> 想要 citations 名副其实、防住幻觉，system prompt 必须明确要求「答案只能来自工具
> 结果」。这是 sparrow 防幻觉契约的宿主侧责任。

## 3. 跑 Harness，消费事件流

`run()` 是生成器，yield 事件 dict：

```python
from sparrow import Harness

messages = [{"role": "user", "content": "What's the weather in Beijing?"}]
for event in Harness(config).run(messages):
    if event["type"] == "tool_call":
        print(f"→ {event['name']}({event['arguments']})")
    elif event["type"] == "tool_result":
        print(f"← {event['summary']}")
    elif event["type"] == "final":
        print(event["content"], "sources:", event["citations"])
    elif event["type"] == "error":
        print("error:", event["message"])
```

事件类型全集见
[引擎架构 §4a](../architecture/engine-architecture.md#4a-事件流协议)。

## 4.（可选）加记忆与面板

给 dashboard 类应用：用 `Memory` + `panel_tools()` 让 agent 能把洞察固化成实时
面板，并用 journal 注入情景记忆。

```python
from sparrow import Memory, AgentConfig, panel_tools

mem = Memory(
    "ui.db",
    transforms={"count": lambda d: {"value": len(next(iter(d.values()), []))}},
    tool_names={"get_weather"},   # 允许作面板数据源的工具（spec 校验用）
)

config = AgentConfig(
    system_prompt="...",
    tools=[get_weather, *panel_tools(mem)],          # 加 create/archive/list_panels
    recall_provider=mem.journal_summary_for_prompt,  # 注入最近活动作情景记忆
)
```

渲染某个面板（按实时数据重算）：

```python
from sparrow import panel_data
out = panel_data.resolve("my-panel-id", mem, config.registry())
```

面板列可以声明受限表达式：`{"title": "Market Value", "expr": "current_price * shares"}`
安全，`{"expr": "__import__('os')"}` 被拒。原理见
[记忆与面板架构](../architecture/memory-architecture.md)。

要把 agent 动作写进 journal，给 `Harness` 传 `journal_fn`：

```python
Harness(config, journal_fn=mem.journal_append).run(messages, conversation_id="c1")
```

## 5.（可选）挂前端聊天组件

`sparrow-chat.js` 是官方浮动聊天 dock，对接 `Harness.run()` 的 SSE 事件流。宿主只
需把事件流通过 SSE 暴露成一个端点，前端 `SparrowChat.mount({...})` 即可。

定位组件文件（用于 build 时拷进静态目录）：

```python
from sparrow.web import asset_path
import shutil
shutil.copy(asset_path("sparrow-chat.js"), "static/js/")
```

服务端契约（SSE 事件 = `Harness.run()` yield 的事件）、挂载选项与 i18n 见
`sparrow/web/README.md`。

## 6. 跑测试

```bash
pip install -e ".[dev]"
python -m pytest -q          # 纯本地，无网络无 LLM 调用
```
