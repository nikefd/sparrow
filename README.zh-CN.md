# 🐦 sparrow

**一个麻雀虽小、五脏俱全的 agent harness。**

> [English](README.md) | [中文](README.zh-CN.md)

你只需带来自己的工具和一段 system prompt，sparrow 就把它们编排成一个带溯源的 agent
循环，并补齐一个真实 agent 的全部「器官」——**skill、上下文压缩、stop-reason 处理、
checkpoint/resume、子 agent 委派、人在环中审批、结构化输出**——每样都用最小形式实现。
核心仅依赖标准库，没有任何重型依赖——不用 LangChain，不用 LangGraph。

## 为什么是 sparrow

大多数 agent 框架都很重。sparrow 反其道而行：一个一下午就能读透的库，用 **clean
architecture（ports & adapters）** 组织，却五脏俱全：

- **Skill** —— 渐进式披露：工具藏在 skill 后面，模型激活才展开，能力再多 context 也不膨胀。
- **上下文压缩** —— 窗口将满时把最早的对话摘要（而非丢弃），对话无限延续。
- **stop-reason 处理** —— 被截断的回复会续写、要调工具就调、该停才停。`finish_reason`
  绝不丢弃。
- **checkpoint / resume** —— 运行状态是纯数据，每轮持久化；崩溃或暂停后可跨进程恢复续跑。
- **子 agent 委派** —— 把子任务丢给上下文隔离的子 agent。
- **人在环中** —— `writes=True` 的工具暂停等审批，拿到结果再 resume。
- **结构化输出** —— 可强制最终答案是符合 JSON schema 的对象。
- **天生带溯源** —— 每个工具结果带 `source`，最终答案自动收集成 citations。

核心信条：**LLM 只产声明，不产代码。** 模型只决定用哪个工具、激活哪个 skill、哪个列
表达式，真正执行都是普通 Python。

## 安装

```bash
pip install sparrow-agent          # import 名是 sparrow
```

指向任意 OpenAI 兼容端点（默认 DeepSeek），通过环境变量或 `configure()` 配置：

```bash
export SPARROW_LLM_API_KEY=sk-...
export SPARROW_LLM_BASE_URL=https://api.deepseek.com   # 可选
export SPARROW_LLM_MODEL=deepseek-chat                 # 可选
```

## 快速开始

```python
from sparrow import tool, AgentConfig, Agent

@tool(description="查天气", source="demo")
def get_weather(city: str) -> dict:
    return {"city": city, "weather": "晴, 24°C"}

config = AgentConfig(
    system_prompt="你是天气助手，必须调工具拿真实数据，绝不编造。",
    tools=[get_weather],
)

for event in Agent(config).run([{"role": "user", "content": "北京天气？"}]):
    print(event)   # Event(type=tool_call | tool_result | final | ...)
```

完整示例见 [`examples/`](examples/)：`weather_agent.py`、`skills_agent.py`（渐进披露）、
`approval_agent.py`（审批 + checkpoint/resume）。

## 几个「器官」速览

```python
from sparrow import Skill, builtins
from sparrow.adapters.sqlite_store import SqliteStore
from sparrow.adapters.interactive_approver import InteractiveApprover

config = AgentConfig(
    system_prompt="你是编码助手。",
    tools=[*builtins(root="/safe/workdir")],   # opt-in 的 fs/glob/grep/bash/http 电池
    skills=[Skill(name="refactor", when="用户要重构代码时",
                  instructions="...", tools=["edit_file"])],
    output_schema={"type": "object"},          # 强制结构化最终结果（可选）
    enable_delegation=True,                     # 允许 delegate 给子 agent
)

agent = Agent(config, store=SqliteStore("ck.db"), approver=InteractiveApprover())
for event in agent.run(messages, run_id="job-1"):
    if event.type == "awaiting_approval":
        ...                                     # 已暂停并落盘；稍后 resume(run_id)
```

基础工具里危险的三件套（`write_file`/`edit_file`/`run_bash`）是 `writes=True`，会经过
审批门——基础工具集和人在环中天生配套。

## 记忆与面板（可选电池）

```python
from sparrow import Memory, panel_tools
mem = Memory("ui.db", transforms={"count": lambda d: {"value": len(next(iter(d.values()), []))}})
config = AgentConfig(system_prompt="...", tools=[*my_tools, *panel_tools(mem)])
```

面板存的是**配方**不是快照，每次按实时数据重算。自定义列用受限表达式引擎
（`current_price * shares` 安全；`__import__('os')` 被拒）。

## 架构

hexagonal：纯 `core`（loop + 领域模型，零 I/O）只依赖 `sparrow.ports` 的 Protocol；
具体 `adapters`（OpenAI 客户端、sqlite 存储…）由 `app` 层注入；可选电池放
`sparrow.tools`。整个循环是一个纯 `step()` reducer，注 fake 即可全测、不触网。

## 文档

要看全貌——`step` reducer、ports & adapters、七大能力、checkpoint——见
[`llmdoc/`](llmdoc/index.md)，一套同时面向人和 AI agent 的文档体系。从
[`llmdoc/index.md`](llmdoc/index.md) 开始。

| 我想... | 从这里开始 |
|---|---|
| 端到端搭一个能跑的 agent | [guides/how-to-build-an-agent.md](llmdoc/guides/how-to-build-an-agent.md) |
| 理解核心循环与 ports/adapters | [architecture/core-and-ports.md](llmdoc/architecture/core-and-ports.md) |
| 看每个能力怎么实现 | [architecture/capabilities.md](llmdoc/architecture/capabilities.md) |
| 查公共 API | [reference/api-reference.md](llmdoc/reference/api-reference.md) |
| 发布到 PyPI | [guides/how-to-release.md](llmdoc/guides/how-to-release.md) |

## 状态

`v0.3` —— clean-slate 重写为 hexagonal 核心 + 上述七大能力。旧的 `Harness` 是转调
`Agent` 的 deprecated shim。`1.0` 前 API 可能调整。

MIT 协议。
