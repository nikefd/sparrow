# 引擎架构

> 讲「sparrow 的 ReAct 循环为什么这样设计」。模块：`harness.py` /
> `registry.py` / `llm.py`。记忆与面板见
> [记忆与面板架构](memory-architecture.md)。

## 1. 指导信条：LLM 只产声明，不产代码

这是贯穿全库的一条线。模型永远只输出**声明**——调用哪个工具、传什么参数、用哪种
transform、哪个列表达式——真正的执行是确定性的普通 Python。好处有三：

- **防幻觉**：最终答案只能从工具结果里来（宿主 system prompt 应强制
  「answer only from tool results」），不是模型凭空编的。
- **限定边界**：模型被关在一个只读、已校验的表达面里。连面板计算列都是
  [受限表达式](memory-architecture.md#3-受限表达式引擎-exprpy)，跑不了任意代码。
- **可溯源**：每个工具结果携带 `source`，`Harness` 自动收集成 citations。

## 2. 三层职责划分

```
AgentConfig (registry.py)   ← 注入面：system prompt + tools + memory 配置
        │
        ▼
   Harness (harness.py)      ← 编排：ReAct 循环、事件流、context 预算、journaling
        │  调用
        ▼
    chat() (llm.py)          ← 传输：OpenAI 兼容 HTTP，流式 + tool-call 聚合
```

引擎本身**领域无关**：所有领域知识都从 `AgentConfig` 来。换个业务，只换工具和
prompt，引擎一行不动。

## 3. 注入面：registry.py

### 3a. `@tool` 装饰器

把一个普通函数变成 `Tool`（`registry.py:73 tool()`）。两种写法都支持：

- **关键字参数风格**：`def get_weather(city: str) -> dict`。装饰器用
  `inspect.signature` 把参数**自省成 JSON Schema**（`_build_schema`，
  `registry.py:53`）——Python 类型映射到 JSON 类型，有默认值的参数不进 `required`。
- **单 `args` dict 风格**：`def raw(args)`。整个参数 dict 原样传入。

无论哪种，`Tool.__call__` 统一以 `fn(args_dict)` 调用（adapter 负责适配，并过滤
掉未知 key，避免多余参数让调用崩溃）。

`@tool` 的元数据字段：`description`（缺省取 docstring 首行）、`label`（UI 短标签）、
`source`（默认 citation 来源）、`writes`（是否状态写入 → 被 journaled）。

### 3b. `ToolRegistry`

持有一个 agent 的全部工具，并：
- `openai_specs()`：渲染成 OpenAI `tools` 数组，喂给 `chat()`。
- `run(name, args)`：执行工具，**自动补 `source`**（工具没设就用 `Tool.source`），
  并把任何异常兜成 `{"error": ...}`——一个工具炸了不会拖垮整个循环。

### 3c. `AgentConfig`

宿主注入的一切，全在这个 dataclass 里（`registry.py:143`）：

| 字段 | 默认 | 作用 |
|---|---|---|
| `system_prompt` | （必填） | agent 的人设与铁律 |
| `tools` | `[]` | `Tool` 列表 |
| `max_tool_rounds` | 6 | ReAct 循环最多几轮 |
| `tool_result_max_chars` | 8000 | 单个工具结果截断阈值 |
| `history_turns` | 20 | context 里保留最近多少条消息 |
| `recall_provider` | None | 返回字符串、拼到 system prompt 末尾（情景记忆钩子） |
| `ui_db_path` / `enable_panels` / `enable_journal` | — | 记忆相关开关 |

## 4. 编排：harness.py 的 ReAct 主循环

`Harness.run(user_messages, conversation_id)` 是一个**生成器**，yield 事件 dict。
一轮循环（`harness.py:52`）：

1. 拼 messages：`[system] + 最近 history_turns 条`。system prompt 由
   `_system_prompt()` 构造，若配了 `recall_provider` 则把情景记忆摘要拼到末尾
   （recall 失败被静默吞掉，**绝不阻塞对话**）。
2. 调 `chat(messages, tools=registry.openai_specs())`。
3. **没有 tool_calls** → 模型给出了最终答案 → yield `final`（带去重排序后的
   `citations`），结束。
4. **有 tool_calls** → 把 assistant 的 tool-call 意图回写进 history（OpenAI 协议
   要求），然后逐个执行：
   - yield `tool_call`（含 `label` 供 UI 展示）。
   - 给写工具（`writes=True`）注入 `conversation_id`（`setdefault`，不覆盖模型
     显式给的）。
   - `registry.run()` 执行；结果里的 `source` 收进 citations。
   - yield `tool_result`（`_summarize` 压成一行人话）。
   - 写工具且无错 → 调 `journal_fn` 记一笔情景记忆；若结果带 `id` → 额外 yield
     `panel_created`。
   - 工具结果（截断到 `tool_result_max_chars`）回写进 history。
5. 轮数耗尽（`max_tool_rounds`）→ 追加一句「limit reached, answer now」强制收口，
   再要一次最终答案。

异常处理：`LLMError` 与其它异常都被兜成 `error` 事件 yield 出去，循环不会把栈抛
给调用方。

### 4a. 事件流协议

`run()` 只 yield 这几类事件，传输层照单序列化即可：

| 事件 | 关键字段 | 含义 |
|---|---|---|
| `tool_call` | `name` / `label` / `arguments` | 模型要调某工具 |
| `tool_result` | `name` / `label` / `summary` | 工具返回（已压成一行） |
| `panel_created` | `id` | 写工具产生了一个带 id 的对象（如面板） |
| `final` | `content` / `citations` | 最终答案 + 溯源列表 |
| `error` | `message` | LLM 或工具异常 |

这层协议是 sparrow 与前端（`sparrow-chat.js` 走 SSE）之间的契约，见
[如何搭一个 agent](../guides/how-to-build-an-agent.md)。

### 4b. context 预算

两道闸：①只保留最近 `history_turns` 条消息；②单个工具结果超过
`tool_result_max_chars` 就截断并加 `…(truncated)`（`_truncate`，`harness.py:25`）。
小而粗暴，但够用。

## 5. 传输：llm.py

唯一的 LLM 出口是 `chat()`（`llm.py:60`），所有调用都经过它，于是 token 用量与
延迟在一处记录（`USAGE_LOG`）。要点：

- **OpenAI 兼容**：POST `{base_url}/v1/chat/completions`，纯 `urllib`，零三方依赖。
- **流式 / 非流式同签名**：传 `on_delta` 就走流式，文本 delta 逐块回调，tool-call
  的分片 delta 自动按 `index` 聚合还原。
- **重试**：网络/解析类异常重试 `retries` 次（默认 2），退避 `1.5 * (attempt+1)` 秒。
- **配置**：env 默认值（`SPARROW_LLM_*` 优先于 `DEEPSEEK_*`），可被
  `configure(base_url=, api_key=, model=)` 运行时覆盖——宿主注入自己的凭证，不必
  动 env 状态。没有 api key 直接抛 `LLMError`。
