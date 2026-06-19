# 项目概述

## 定位

**sparrow** 是一个「麻雀虽小、五脏俱全」的 agent harness——一个开源 Python 库
（PyPI 包名 `sparrow-agent`，import 名 `sparrow`）。你只需带来自己的工具（普通函数）
和一段 system prompt，sparrow 就把它们编排成一个带溯源的 agent 循环，并补齐成熟
agent 的**七大本质能力**，每样都用最小形式实现：

1. **Skill** —— 能力渐进式披露，不一次性塞满 context。
2. **Compaction** —— 上下文将满时摘要前文，让对话无限延续。
3. **Stop-reason 处理** —— 正确区分该停 / 该续写 / 该调工具。
4. **Checkpoint / Resume** —— 执行状态可持久化、可恢复、跨进程续跑。
5. **子 agent 委派** —— 把子任务丢给上下文隔离的 sub-agent。
6. **人在环中（审批）** —— 危险/写操作前暂停等批准。
7. **结构化输出** —— 可强制按 JSON schema 返回。

它的反面是 LangChain / LangGraph 这类「重」框架。sparrow 的目标是：**一个一下午
就能读透的库**，核心仅依赖标准库（`urllib` / `sqlite3` / `ast`），零运行时三方依赖，
却用 **clean architecture（ports & adapters）** 把这七大能力组织得清清楚楚。

## 总体描述

sparrow 由两个生产 agent（一个 A 股量化助手、一个 AI 前沿追踪器）抽取并通用化而来，
v2 起做了 clean-slate 重写。它对业务**零假设**：金融、新闻、天气都用同一套引擎，全部
领域知识通过 `AgentConfig`（system prompt + 工具 + skills + 记忆/审批配置）注入。

一次典型调用：宿主用 `@tool` 把若干函数登记成工具，组装一个 `AgentConfig`，交给
`Agent(cfg).run(messages)`，得到一个**事件流**（`tool_call` / `tool_result` /
`skill_activated` / `compacted` / `awaiting_approval` / `delegated` / `final` /
`error`）。传输层（SSE / CLI）只负责把事件序列化，编排与传输解耦。

核心设计信条：**LLM 只产声明，不产代码**——模型只决定「用哪个工具、激活哪个 skill、
哪个列表达式」，真正的执行永远是确定性的普通 Python。这从根本上杜绝幻觉数据，并把
模型限制在只读、已校验的边界内。

## 架构一句话

**hexagonal（ports & adapters）**：一个纯 `core`（loop + 领域模型，零 I/O）只依赖
`ports` 里的 Protocol；具体 `adapters`（OpenAI 客户端、sqlite 存储…）由 `app` 层注入；
可选电池放 `tools`。详见 [核心与 ports 架构](../architecture/core-and-ports.md)。

## 技术栈

| 维度 | 选型 | 说明 |
|---|---|---|
| 语言 | Python ≥ 3.9 | `from __future__ import annotations` 兼容老版本类型语法 |
| 架构 | ports & adapters | 纯 core + Protocol 接口 + 可替换 adapter |
| LLM 客户端 | `urllib`（stdlib） | OpenAI 兼容协议，默认指向 DeepSeek |
| Checkpoint 存储 | `sqlite3` / 内存（stdlib） | `SqliteStore` / `MemoryStore` 两实现 |
| 表达式沙箱 | `ast`（stdlib） | 受限表达式，面板计算列用 |
| 前端组件 | 原生 JS（无框架） | `sparrow-chat.js`，对接 Agent 事件流 |
| 打包 | setuptools + `pyproject.toml` | Trusted Publishing 发到 PyPI |
| 测试 | pytest | 全程不触网,fake 注入测 core |
| 运行时依赖 | **无** | 核心仅 stdlib |

## 关键外部服务

- **OpenAI 兼容 LLM 端点**：唯一外部依赖。默认 `https://api.deepseek.com`、模型
  `deepseek-chat`。通过环境变量（`SPARROW_LLM_*` 或 `DEEPSEEK_*`）或 `configure()`
  配置。没配 api key 时 `OpenAILLM.complete()` 抛 `LLMError`。
- **PyPI**：发布目标，GitHub Actions OIDC Trusted Publishing，仓库不存 token。

## 目录结构

| 路径 | 职责 |
|---|---|
| `sparrow/core/models.py` | 全部领域 dataclass；`RunState` 是 checkpoint 唯一载体 |
| `sparrow/core/loop.py` | `step()` 纯状态机 reducer + `Deps` 注入袋（设计灵魂） |
| `sparrow/core/budget.py` | token 近似估算 + 压缩选段 |
| `sparrow/core/schema.py` | 函数自省、skill 门控 specs 渲染、OpenAI 消息互转 |
| `sparrow/ports/__init__.py` | 6 个 Protocol：LLM/Store/Approver/Clock/Summarizer/SubAgentRunner |
| `sparrow/adapters/` | 6 个 port 的具体实现（openai_llm / sqlite_store / …） |
| `sparrow/app/agent.py` | `Agent` 门面：`run()`/`resume()` driver + checkpoint |
| `sparrow/app/config.py` | 瘦身版 `AgentConfig` |
| `sparrow/app/subagent.py` | `SubAgentRunner`：隔离子 agent 跑委派任务 |
| `sparrow/tools/registry.py` | `@tool` / `ToolRegistry` |
| `sparrow/tools/builtins.py` | 基础工具电池（fs/glob/grep/bash/http，opt-in） |
| `sparrow/tools/expr.py` | 受限表达式引擎 |
| `sparrow/tools/panels.py` | 面板即记忆 + 对话/流水（可选电池） |
| `sparrow/harness.py` | **deprecated** `Harness` 薄 shim（转调 `Agent`） |
| `sparrow/web/sparrow-chat.js` | 前端浮动聊天 dock |
| `examples/` | weather / skills / approval 三个最小示例 |
| `tests/` | core loop / agent / adapters / tools 四组,全程不触网 |

## 核心功能

见顶部「七大本质能力」。此外保留 sparrow 一贯的：**天生带溯源**（工具结果带 `source`，
final 自动收集 citations）、**面板即记忆**（可选电池，存配方非快照）、**受限表达式**
（面板列只允许字段名+数字+四则运算）。
