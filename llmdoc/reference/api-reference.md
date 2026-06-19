# 公共 API 速查

> `from sparrow import ...` 能拿到的公共符号（`sparrow/__init__.py:__all__`）。
> 用法见 [如何搭一个 agent](../guides/how-to-build-an-agent.md)，原理见
> [核心与 ports 架构](../architecture/core-and-ports.md)。

## 导出符号一览

| 符号 | 类型 | 用途 |
|---|---|---|
| `Agent` | class | agent 门面：`run()` / `resume()` |
| `AgentConfig` | dataclass | 注入面：prompt + tools + skills + 配置 |
| `Event` | dataclass | 事件流元素 `(type, data)` |
| `RunState` | dataclass | checkpoint 载体（一般不手构） |
| `Skill` | dataclass | 渐进披露的能力单元 |
| `Message` / `Completion` / `ToolCall` / `Decision` | dataclass | 领域模型 |
| `tool` | 装饰器 | 把函数变成 `Tool` |
| `Tool` / `ToolRegistry` | class | 工具与注册表 |
| `builtins` | 工厂 | 基础工具电池（fs/glob/grep/bash/http） |
| `safe_eval` / `is_safe_expr` | 函数 | 受限表达式求值 / 静态检查 |
| `OpenAILLM` / `configure` / `LLMError` | adapter | LLM 客户端 / 配置 / 异常 |
| `ports` | module | 6 个 Protocol（写自定义 adapter 用） |
| `Memory` / `panel_tools` | class / 工厂 | 面板即记忆（懒加载电池） |
| `Harness` | class | **deprecated**，转调 `Agent` |

## 关键签名

```python
# 门面
Agent(config, *, llm=None, store=None, approver=None, clock=None,
      summarizer=None, subagent=None)
Agent.run(user_messages, run_id=None)   # 生成器,yield Event
Agent.resume(run_id)                     # 从 checkpoint 续跑

# 配置
AgentConfig(system_prompt, tools=[], skills=[], output_schema=None,
            max_rounds=8, token_budget=12000, keep_recent=6,
            tool_result_max_chars=8000, enable_delegation=False, needs_approval=None)

# 工具
@tool(name="", description="", schema=None, label="", source="", writes=False)
builtins(root=None, *, allow=None)       # -> list[Tool]

# LLM
OpenAILLM(*, retries=2)                   # 实现 LLM port
configure(*, base_url=None, api_key=None, model=None)

# 表达式
safe_eval(expr, row)                      # -> 值或 None
is_safe_expr(expr)                        # -> bool
```

## 事件类型（`Event.type` → `Event.data`）

| type | data 字段 |
|---|---|
| `tool_call` | name / label / arguments |
| `tool_result` | name / summary |
| `skill_activated` | name |
| `compacted` | freed |
| `awaiting_approval` | run_id / call |
| `delegated` | task |
| `final` | content / citations（或 structured / citations） |
| `error` | error |

## 工具结果约定

工具返回 dict。引擎识别这些特殊 key：

| key | 作用 |
|---|---|
| `source` | citation 来源（缺省时 registry 自动补 `Tool.source`） |
| `error` | 标记失败：`_summarize` 报错 |
| `_summary` | 覆盖默认一行摘要 |
| `message` | 无 list 时的摘要回退 |

> 工具**必须返回 JSON-able dict**——checkpoint 把工具结果落成字符串，不可序列化对象会
> 坏掉 resume。

## ports（`sparrow.ports`）

| Protocol | 方法 | 默认 adapter |
|---|---|---|
| `LLM` | `complete(...) -> Completion` | `OpenAILLM` |
| `Store` | `save / load / delete` | `MemoryStore`（默认）/ `SqliteStore` |
| `Approver` | `review(call) -> Decision` | 无（不配则不审批）/ `AutoApprover` / `InteractiveApprover` |
| `Clock` | `now / new_id` | `SystemClock` |
| `Summarizer` | `summarize(messages) -> Message` | `LLMSummarizer` |
| `SubAgentRunner` | `run(task, *, tools, skills) -> str` | `app.SubAgentRunner` |

adapter 在 `sparrow.adapters.*`，按需 import 注入 `Agent(...)`。

## 基础工具电池（`builtins`）

| 工具 | 类别 | writes |
|---|---|---|
| `read_file` / `list_dir` / `glob` / `grep` | 文件读取 | 否 |
| `write_file` / `edit_file` | 文件写入 | **是（走审批）** |
| `run_bash` | 执行 | **是（走审批）** |
| `http_fetch` | 网络 | 否 |

`builtins(root=...)` 限定文件根目录防越界；`allow={...}` 挑子集。

## 环境变量

| 变量 | 默认 | 优先级 |
|---|---|---|
| `SPARROW_LLM_API_KEY` / `DEEPSEEK_API_KEY` | （空） | 前者优先 |
| `SPARROW_LLM_BASE_URL` / `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | 前者优先 |
| `SPARROW_LLM_MODEL` / `DEEPSEEK_MODEL` | `deepseek-chat` | 前者优先 |
