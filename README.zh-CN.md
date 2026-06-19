# 🐦 sparrow

**一个麻雀虽小、五脏俱全的 agent harness。**

> [English](README.md) | [中文](README.zh-CN.md)

你只需带来自己的工具和一段 system prompt，sparrow 就把它们编排成一个带溯源的
ReAct 循环、三层记忆、以及用于安全计算面板的受限表达式引擎。核心仅依赖标准库，
没有任何重型依赖——不用 LangChain，不用 LangGraph。

## 为什么是 sparrow

大多数 agent 框架都很重。sparrow 反其道而行：一个一下午就能读透的单包，
却五脏俱全：

- **ReAct 工具循环** —— LLM 决定「要什么」，确定性代码决定「怎么做」。
- **工具注入** —— 引擎对业务零假设。你把普通函数注入成工具；金融、新闻、天气，
  同一套引擎。
- **三层记忆** —— 对话、物化面板、append-only 流水，同一个 SQLite 文件，
  与业务数据物理隔离。
- **LLM 只产声明，不产代码** —— 连自定义面板列都是「受限表达式」
  （AST 白名单：字段名 + 数字 + 四则运算），模型能组合衍生指标，却碰不到任意代码。
- **天生带溯源** —— 每个工具结果带 `source`，最终答案自动收集成 citations。

## 安装

```bash
pip install sparrow-agent          # import 名是 sparrow
```

核心引擎零三方依赖（仅 stdlib）。指向任意 OpenAI 兼容端点（默认 DeepSeek），
通过环境变量或 `configure()` 配置：

```bash
export SPARROW_LLM_API_KEY=sk-...
export SPARROW_LLM_BASE_URL=https://api.deepseek.com   # 可选
export SPARROW_LLM_MODEL=deepseek-chat                 # 可选
```

## 快速开始

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
    print(event)   # tool_call / tool_result / final / error
```

完整示例见 [`examples/weather_agent.py`](examples/weather_agent.py)。

## 记忆与面板（可选）

面向 dashboard 类应用，sparrow 提供「面板即记忆」：agent 可以把对话中的洞察
固化成一个实时的、声明式的面板。

```python
from sparrow import Memory, AgentConfig, panel_tools

mem = Memory("ui.db", transforms={"count": lambda d: {"value": len(next(iter(d.values()), []))}})

config = AgentConfig(
    system_prompt="...",
    tools=[*my_query_tools, *panel_tools(mem)],   # 加上 create/archive/list_panels
    recall_provider=mem.journal_summary_for_prompt,  # 注入情景记忆
)
```

面板存的是**配方**（一个工具 + transform/列），不是快照，所以每次都按实时数据
重新计算。table 自定义列用受限表达式引擎：

```python
{"title": "市值", "expr": "current_price * shares"}    # 安全
{"title": "x", "expr": "__import__('os')"}             # 被拒绝
```

## 设计理念

1. **LLM 决定「要什么」，确定性代码决定「怎么做」。** 模型永远只产声明
   （用哪个工具、哪种 transform、哪个列表达式），真正执行都是普通代码。
   防幻觉，且把模型限制在只读、已校验的边界内。
2. **读写分级。** 查询工具读业务数据，写工具只动 agent 自己的记忆库。
   LLM 能塑造呈现，永远碰不到底层真相。
3. **记忆覆盖所有 actor。** 流水记录人做的、AI 做的、系统做的——agent 的
   世界观才完整。

## 文档

本 README 是快速导览。要看全貌——引擎内部、三层记忆模型、受限表达式沙箱、以及
如何扩展或发布 sparrow——见 [`llmdoc/`](llmdoc/index.md)，一套同时面向人和 AI
agent 的文档体系。从 [`llmdoc/index.md`](llmdoc/index.md) 开始。

| 我想... | 从这里开始 |
|---|---|
| 端到端搭一个能跑的 agent | [guides/how-to-build-an-agent.md](llmdoc/guides/how-to-build-an-agent.md) |
| 理解 ReAct 循环与事件流 | [architecture/engine-architecture.md](llmdoc/architecture/engine-architecture.md) |
| 理解记忆与面板 | [architecture/memory-architecture.md](llmdoc/architecture/memory-architecture.md) |
| 查公共 API | [reference/api-reference.md](llmdoc/reference/api-reference.md) |
| 发布到 PyPI | [guides/how-to-release.md](llmdoc/guides/how-to-release.md) |

## 状态

`v0.1` —— 从两个生产 agent（A股量化助手 + AI 前沿追踪）抽取并通用化而来。
`1.0` 前 API 可能调整。

MIT 协议。
