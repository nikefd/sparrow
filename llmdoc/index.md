# sparrow — 文档索引

「麻雀虽小、五脏俱全」的开源 agent harness（PyPI: `sparrow-agent`，import 名
`sparrow`）。你带工具 + system prompt，sparrow 编排成带溯源的 ReAct 循环 + 三层
记忆 + 受限表达式面板。核心仅依赖标准库，零运行时三方依赖。

---

## 快速导航

| 如果你需要... | 从这里开始 |
|---|---|
| 了解项目定位、技术栈、目录结构 | [项目概述](overview/project-overview.md) |
| 第一次上手：搭一个能跑的 agent | [如何搭一个 agent](guides/how-to-build-an-agent.md) |
| 理解 ReAct 主循环怎么转的 | [引擎架构](architecture/engine-architecture.md)（第 4 节） |
| 理解「LLM 只产声明，不产代码」这条信条 | [引擎架构](architecture/engine-architecture.md)（第 1 节） |
| 知道 `Harness.run()` 会 yield 哪些事件 | [引擎架构](architecture/engine-architecture.md)（第 4a 节）、[API 速查](reference/api-reference.md) |
| 用 `@tool` 定义一个工具 / 两种参数风格 | [引擎架构](architecture/engine-architecture.md)（第 3a 节）、[如何搭一个 agent](guides/how-to-build-an-agent.md)（第 1 节） |
| 给工具结果加溯源 citations | [引擎架构](architecture/engine-architecture.md)（第 1、3b 节） |
| 配置 LLM 端点 / 换成非 DeepSeek | [引擎架构](architecture/engine-architecture.md)（第 5 节）、[API 速查](reference/api-reference.md)（环境变量） |
| 理解流式 / tool-call delta 聚合 | [引擎架构](architecture/engine-architecture.md)（第 5 节） |
| 理解三层记忆（对话/面板/流水） | [记忆与面板架构](architecture/memory-architecture.md)（第 1 节） |
| 给 agent 加「面板即记忆」能力 | [记忆与面板架构](architecture/memory-architecture.md)（第 2 节）、[如何搭一个 agent](guides/how-to-build-an-agent.md)（第 4 节） |
| 注入情景记忆（journal recall） | [记忆与面板架构](architecture/memory-architecture.md)（第 1b 节） |
| 理解受限表达式引擎 / 为什么能防代码执行 | [记忆与面板架构](architecture/memory-architecture.md)（第 3 节） |
| 挂前端浮动聊天组件 | [如何搭一个 agent](guides/how-to-build-an-agent.md)（第 5 节）、`sparrow/web/README.md` |
| 发布新版本到 PyPI | [如何发布到 PyPI](guides/how-to-release.md) |
| 跑测试 | [如何搭一个 agent](guides/how-to-build-an-agent.md)（第 6 节） |
| 查公共 API 签名 / 导出符号 | [API 速查](reference/api-reference.md) |
| 查编码约定（语言/stdlib-only/领域无关） | [编码约定与已知坑](reference/conventions-and-gotchas.md) |
| 排查坑（无 key 报错 / context 截断 / 版本号两处） | [编码约定与已知坑](reference/conventions-and-gotchas.md) |

---

## 概述

| 文档 | 描述 |
|---|---|
| [项目概述](overview/project-overview.md) | 定位、技术栈、外部服务、目录结构、核心功能 |

## 架构

| 文档 | 描述 |
|---|---|
| [引擎架构](architecture/engine-architecture.md) | ReAct 循环、事件流协议、工具注入、LLM 层、指导信条 |
| [记忆与面板架构](architecture/memory-architecture.md) | 三层记忆、面板即记忆、受限表达式引擎 |

## 指南

| 文档 | 描述 |
|---|---|
| [如何搭一个 agent](guides/how-to-build-an-agent.md) | 端到端：工具 → config → Harness → 事件流 → 记忆/面板 → 前端 |
| [如何发布到 PyPI](guides/how-to-release.md) | 版本号、CI、tag → PyPI Trusted Publishing |

## 参考

| 文档 | 描述 |
|---|---|
| [API 速查](reference/api-reference.md) | 公共符号、关键签名、事件类型、工具结果约定、环境变量 |
| [编码约定与已知坑](reference/conventions-and-gotchas.md) | 编码约定 + 已知坑/边界 + 别碰什么 |

---

## 维护约定

改了代码，按下表同步文档，并在上面「快速导航」补一行：

| 改了什么 | 更新哪篇 |
|---|---|
| 新增/改公共 API（导出符号、签名） | [API 速查](reference/api-reference.md) + `__init__.py:__all__` |
| 改 ReAct 循环 / 事件类型 / LLM 层 | [引擎架构](architecture/engine-architecture.md) |
| 改记忆表结构 / 面板 / 表达式白名单 | [记忆与面板架构](architecture/memory-architecture.md) |
| 新增工具结果约定 key / 环境变量 | [API 速查](reference/api-reference.md) |
| 发现新坑 / 新边界 | [编码约定与已知坑](reference/conventions-and-gotchas.md) |
| 改发布流程 / CI | [如何发布到 PyPI](guides/how-to-release.md) |
| 改前端组件选项 | `sparrow/web/README.md` |

> 完成任务后**是否更新 llmdoc 由用户决定**，不要自动改。
