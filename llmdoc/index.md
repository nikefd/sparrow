# sparrow — 文档索引

「麻雀虽小、五脏俱全」的开源 agent harness（PyPI: `sparrow-agent`，import 名
`sparrow`）。你带工具 + system prompt，sparrow 编排成带溯源的 agent 循环，并用最小
形式补齐七大本质能力：**skill / 压缩 / stop-reason / checkpoint / 子 agent / 审批 /
结构化输出**。clean architecture（ports & adapters），核心仅依赖标准库。

---

## 快速导航

| 如果你需要... | 从这里开始 |
|---|---|
| 了解项目定位、技术栈、目录结构 | [项目概述](overview/project-overview.md) |
| 第一次上手：搭一个能跑的 agent | [如何搭一个 agent](guides/how-to-build-an-agent.md) |
| 理解 hexagonal 分层（core/ports/adapters/app） | [核心与 ports 架构](architecture/core-and-ports.md)（第 1-2 节） |
| 读懂 `step()` 纯状态机 reducer 怎么转 | [核心与 ports 架构](architecture/core-and-ports.md)（第 3 节） |
| 知道 `Agent.run()` 会 yield 哪些事件 | [核心与 ports 架构](architecture/core-and-ports.md)（第 4a 节）、[API 速查](reference/api-reference.md) |
| 理解 checkpoint 为什么能跨进程 resume | [核心与 ports 架构](architecture/core-and-ports.md)（第 5 节） |
| 理解审批暂停为什么不破坏生成器流 | [核心与 ports 架构](architecture/core-and-ports.md)（第 6 节） |
| 搞清七大能力各自怎么实现、落在哪 | [七大能力](architecture/capabilities.md) |
| 用 skill 做渐进式能力披露 | [七大能力](architecture/capabilities.md)（第 1 节）、[搭 agent](guides/how-to-build-an-agent.md)（第 4 节） |
| 加上下文压缩 / 理解触发时机 | [七大能力](architecture/capabilities.md)（第 2 节） |
| 处理被 max_tokens 截断的回复（stop-reason） | [七大能力](architecture/capabilities.md)（第 3 节） |
| 让 agent 可中断、可恢复（checkpoint/resume） | [七大能力](architecture/capabilities.md)（第 4 节）、[搭 agent](guides/how-to-build-an-agent.md)（第 5 节） |
| 加人在环中审批门控 | [七大能力](architecture/capabilities.md)（第 6 节）、[搭 agent](guides/how-to-build-an-agent.md)（第 5 节） |
| 委派子任务给隔离子 agent | [七大能力](architecture/capabilities.md)（第 5 节）、[搭 agent](guides/how-to-build-an-agent.md)（第 7 节） |
| 强制结构化（JSON schema）输出 | [七大能力](architecture/capabilities.md)（第 7 节）、[搭 agent](guides/how-to-build-an-agent.md)（第 7 节） |
| 给 agent 开箱即用的 fs/bash/http 能力 | [搭 agent](guides/how-to-build-an-agent.md)（第 6 节）、[API 速查](reference/api-reference.md)（builtins） |
| 写自定义 adapter（换 LLM/存储/审批） | [核心与 ports 架构](architecture/core-and-ports.md)（第 2 节）、[API 速查](reference/api-reference.md)（ports） |
| 配置 LLM 端点 / 换非 DeepSeek | [搭 agent](guides/how-to-build-an-agent.md)（前置）、[API 速查](reference/api-reference.md)（环境变量） |
| 用面板即记忆（可选电池） | [搭 agent](guides/how-to-build-an-agent.md)（第 8 节） |
| 挂前端浮动聊天组件 | [搭 agent](guides/how-to-build-an-agent.md)（第 9 节）、`sparrow/web/README.md` |
| 发布新版本到 PyPI | [如何发布到 PyPI](guides/how-to-release.md) |
| 查公共 API 签名 / 事件类型 / ports | [API 速查](reference/api-reference.md) |
| 查编码约定（stdlib-only/分层纪律） | [编码约定与已知坑](reference/conventions-and-gotchas.md) |
| 排查坑（无 key / token 近似 / checkpoint 边界 / 审批暂停） | [编码约定与已知坑](reference/conventions-and-gotchas.md) |

---

## 概述

| 文档 | 描述 |
|---|---|
| [项目概述](overview/project-overview.md) | 定位、七大能力、技术栈、外部服务、目录结构 |

## 架构

| 文档 | 描述 |
|---|---|
| [核心与 ports 架构](architecture/core-and-ports.md) | hexagonal 分层、`step()` reducer、Deps、checkpoint 边界、审批暂停模型 |
| [七大能力](architecture/capabilities.md) | skill/压缩/stop-reason/checkpoint/子 agent/审批/结构化输出 逐个落点 |

## 指南

| 文档 | 描述 |
|---|---|
| [如何搭一个 agent](guides/how-to-build-an-agent.md) | 端到端：工具→config→Agent→事件流→各能力→builtins→前端 |
| [如何发布到 PyPI](guides/how-to-release.md) | 版本号、CI、tag → PyPI Trusted Publishing |

## 参考

| 文档 | 描述 |
|---|---|
| [API 速查](reference/api-reference.md) | 公共符号、签名、事件类型、工具结果约定、ports、builtins、环境变量 |
| [编码约定与已知坑](reference/conventions-and-gotchas.md) | 编码约定 + 分层纪律 + 已知坑/边界 + 别碰什么 |

---

## 维护约定

改了代码，按下表同步文档，并在「快速导航」补一行：

| 改了什么 | 更新哪篇 |
|---|---|
| 新增/改公共 API（导出符号、签名） | [API 速查](reference/api-reference.md) + `__init__.py:__all__` |
| 改 `step` 分流 / 事件类型 / 分层 | [核心与 ports 架构](architecture/core-and-ports.md) |
| 改某个能力的实现 | [七大能力](architecture/capabilities.md) |
| 新增/改 port 或 adapter | [核心与 ports 架构](architecture/core-and-ports.md)（第 2 节）+ [API 速查](reference/api-reference.md) |
| 新增工具结果约定 key / 环境变量 / builtins | [API 速查](reference/api-reference.md) |
| 发现新坑 / 新边界 | [编码约定与已知坑](reference/conventions-and-gotchas.md) |
| 改发布流程 / CI | [如何发布到 PyPI](guides/how-to-release.md) |
| 改前端组件选项 | `sparrow/web/README.md` |

> 完成任务后**是否更新 llmdoc 由用户决定**，不要自动改。
