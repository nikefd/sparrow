# 公共 API 速查

> `from sparrow import ...` 能拿到的全部公共符号（`sparrow/__init__.py:__all__`）。
> 用法见 [如何搭一个 agent](../guides/how-to-build-an-agent.md)，原理见
> [引擎架构](../architecture/engine-architecture.md)。

## 导出符号一览

| 符号 | 类型 | 用途 |
|---|---|---|
| `tool` | 装饰器 | 把函数变成 `Tool` |
| `Tool` | dataclass | 一个工具（callable + 元数据） |
| `ToolRegistry` | class | 工具集合，渲染 OpenAI specs、执行工具 |
| `AgentConfig` | dataclass | 注入面：prompt + tools + 记忆配置 |
| `Harness` | class | ReAct 主循环 |
| `Memory` | class | 三层记忆（对话/面板/流水） |
| `panel_tools` | 工厂函数 | 返回 create/archive/list_panels 三个工具 |
| `panel_data` | 模块 | `resolve(panel_id, memory, registry)` 解析面板 |
| `chat` | 函数 | LLM 调用唯一出口 |
| `configure` | 函数 | 运行时覆盖 LLM 凭证/模型 |
| `LLMError` | 异常 | LLM 调用失败 |
| `safe_eval` / `is_safe_expr` | 函数 | 受限表达式求值 / 静态安全检查 |

## 关键签名

```python
# 工具
@tool(name="", description="", schema=None, label="", source="", writes=False)

# 配置
AgentConfig(system_prompt, tools=[], max_tool_rounds=6,
            tool_result_max_chars=8000, history_turns=20,
            ui_db_path=None, enable_panels=False, enable_journal=True,
            recall_provider=None)

# 主循环
Harness(config, *, journal_fn=None)
Harness.run(user_messages, conversation_id="")  # 生成器，yield 事件 dict

# LLM
chat(messages, tools=None, temperature=0.3, max_tokens=2000,
     response_format=None, on_delta=None, retries=2)
configure(*, base_url=None, api_key=None, model=None)

# 记忆
Memory(db_path, *, builtin_panels=None, transforms=None, tool_names=None)

# 面板
panel_tools(memory)                       # -> [create_panel, archive_panel, list_panels]
panel_data.resolve(panel_id, memory, registry)

# 表达式
safe_eval(expr, row)        # -> 求值结果或 None
is_safe_expr(expr)          # -> bool
```

## `Harness.run()` 事件类型

| `type` | 字段 |
|---|---|
| `tool_call` | `name`, `label`, `arguments` |
| `tool_result` | `name`, `label`, `summary` |
| `panel_created` | `id` |
| `final` | `content`, `citations` |
| `error` | `message` |

## 工具结果约定

工具返回 dict。`Harness` / `Memory` 识别这些特殊 key：

| key | 作用 |
|---|---|
| `source` | citation 来源（缺省时 registry 自动补 `Tool.source`） |
| `error` | 标记失败：不计入 journal、`_summarize` 报错 |
| `_summary` | 覆盖 `_summarize` 的默认一行摘要 |
| `id` | 写工具产生的对象 id → 触发 `panel_created` 事件 |
| `message` | journal detail / 无 list 时的摘要回退 |

## 环境变量

| 变量 | 默认 | 优先级 |
|---|---|---|
| `SPARROW_LLM_API_KEY` / `DEEPSEEK_API_KEY` | （空） | 前者优先 |
| `SPARROW_LLM_BASE_URL` / `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | 前者优先 |
| `SPARROW_LLM_MODEL` / `DEEPSEEK_MODEL` | `deepseek-chat` | 前者优先 |

## 前端组件

| 符号 | 用途 |
|---|---|
| `sparrow.web.asset_path(name="sparrow-chat.js")` | 返回打包内前端资源的绝对路径 |
| `SparrowChat.mount({...})`（JS） | 挂载浮动聊天 dock；选项见 `sparrow/web/README.md` |
