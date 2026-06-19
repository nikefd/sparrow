# 项目概述

## 定位

**sparrow** 是一个「麻雀虽小、五脏俱全」的 agent harness——一个开源 Python 库
（PyPI 包名 `sparrow-agent`，import 名 `sparrow`）。你只需带来自己的工具
（普通函数）和一段 system prompt，sparrow 就把它们编排成一个带溯源（citations）
的 ReAct 循环，外加三层记忆和一个用于安全计算面板的受限表达式引擎。

它的反面是 LangChain / LangGraph 这类「重」框架。sparrow 的目标是：**一个一下午
就能读透的单包**，核心仅依赖标准库（`urllib` / `sqlite3` / `ast`），零运行时三方
依赖，却具备一个真实 agent 的全部「器官」。

## 总体描述

sparrow 由两个生产 agent（一个 A 股量化助手、一个 AI 前沿追踪器）抽取并通用化
而来。它对业务**零假设**：金融、新闻、天气都用同一套引擎，全部领域知识通过
`AgentConfig`（system prompt + 工具 + 记忆路径）注入。

一次典型调用：宿主用 `@tool` 把若干函数登记成工具，组装一个 `AgentConfig`，交给
`Harness(cfg).run(messages)`，得到一个**事件流**（`tool_call` / `tool_result` /
`final` / `error`）。传输层（SSE / CLI）只负责把事件序列化，编排与传输解耦。

核心设计信条：**LLM 只产声明，不产代码**——模型只决定「用哪个工具、哪种
transform、哪个列表达式」，真正的执行永远是确定性的普通 Python。这从根本上杜绝
幻觉数据，并把模型限制在只读、已校验的边界内。

## 技术栈

| 维度 | 选型 | 说明 |
|---|---|---|
| 语言 | Python ≥ 3.9 | 见 `pyproject.toml:requires-python` |
| LLM 客户端 | `urllib`（stdlib） | OpenAI 兼容协议，默认指向 DeepSeek |
| 存储 | `sqlite3`（stdlib） | 单文件 `ui.db`，与业务数据物理隔离 |
| 表达式沙箱 | `ast`（stdlib） | AST 白名单，受限表达式求值 |
| 前端组件 | 原生 JS（无框架） | `sparrow-chat.js`，零依赖浮动聊天 dock |
| 打包 | setuptools + `pyproject.toml` | Trusted Publishing 发到 PyPI |
| 测试 | pytest | `tests/test_engine.py`，纯本地无网络 |
| CI/CD | GitHub Actions | CI 跑测试；tag `v*` → PyPI |
| 运行时依赖 | **无** | 核心引擎仅 stdlib |

## 关键外部服务

- **OpenAI 兼容 LLM 端点**：唯一的外部依赖。默认 `https://api.deepseek.com`、
  模型 `deepseek-chat`。通过环境变量（`SPARROW_LLM_*` 或 `DEEPSEEK_*`）或
  `configure()` 配置。没有配置 api key 时 `chat()` 直接抛 `LLMError`。
- **PyPI**：发布目标。通过 GitHub Actions OIDC Trusted Publishing，仓库不存
  API token。

## 目录结构

| 路径 | 职责 |
|---|---|
| `sparrow/__init__.py` | 包出口：导出公共 API + `panel_tools()` 工厂 |
| `sparrow/registry.py` | 工具注册表与 `AgentConfig`——sparrow 的注入面 |
| `sparrow/harness.py` | ReAct 主循环、事件流协议、context 预算、journaling |
| `sparrow/llm.py` | LLM 客户端层（OpenAI 兼容，含流式 + tool-call） |
| `sparrow/memory.py` | 三层记忆（对话 / 面板 / 流水），单 SQLite 文件 |
| `sparrow/expr.py` | 受限表达式引擎（AST 白名单），用于面板计算列 |
| `sparrow/panel_data.py` | 面板 spec → 渲染数据的解析器 |
| `sparrow/web/sparrow-chat.js` | 官方前端聊天 dock 组件（原生 JS） |
| `sparrow/web/__init__.py` | `asset_path()`——定位前端资源 |
| `examples/weather_agent.py` | ~30 行端到端最小示例 |
| `tests/test_engine.py` | 引擎冒烟测试（registry / expr / memory） |
| `.github/workflows/` | `ci.yml`（测试）+ `release.yml`（tag → PyPI） |
| `README.md` / `README.zh-CN.md` | 双语 README，面向首次接触者 |

## 核心功能

1. **ReAct 工具循环**——模型决定「要什么」，确定性代码决定「怎么做」。
2. **工具注入**——`@tool` 装饰普通函数即成工具；引擎对业务零假设。
3. **天生带溯源**——每个工具结果带 `source`，最终答案自动收集成 citations。
4. **三层记忆**——对话（conversations）、物化面板（panels）、append-only 流水
   （journal），同一个 SQLite 文件，与业务数据物理隔离。
5. **面板即记忆**——agent 可把对话洞察固化成实时、声明式的面板（存配方非快照）。
6. **受限表达式引擎**——面板计算列只允许「字段名 + 数字 + 四则运算」，模型能组合
   衍生指标却碰不到任意代码。
7. **前端 dock 组件**——`sparrow-chat.js`，对接 `Harness.run()` 的 SSE 事件流。
