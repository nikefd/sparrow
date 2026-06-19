# 七大能力

> 逐个讲成熟 agent 的七大本质能力在 sparrow 里怎么用最小形式实现、落在哪个模块。
> 分流主框架见 [核心与 ports 架构](core-and-ports.md) 第 3 节。

每个能力本质上都是「对 `RunState` 的一次纯变换 + 一次 port 调用」，所以全都收口在
`core/loop.py:step()` 一个 reducer 里。

## 1. Skill —— 渐进式能力披露

**问题**：所有工具 schema 一次性塞进 context，工具一多就线性膨胀。

**机制**：`Skill = {name, when, instructions, tools, active}`。`schema.specs_for()`
对**未激活** skill 只渲染一个 `activate_skill` 伪工具（描述里列出各 skill 的 `name` +
`when` 一行）；skill 拥有的工具在激活前**不进 specs**。模型调 `activate_skill(name)`
→ loop 的 `_activate_skill` 翻 `active=True`、把 `instructions` 当 tool 结果注入、该
skill 的工具进入可见集。

**白名单**：只能激活**已注册**的 skill（`_activate_skill` 找不到就返回 error）——与
受限表达式同一「声明受限」信条。`active` 标志在 `RunState` 里，随 checkpoint 走。

**落点**：`core/schema.py:specs_for` + `core/loop.py:_activate_skill`。约 30 行。

## 2. Compaction —— 上下文压缩

**问题**：旧版 `history_turns` 是硬截断丢弃，长对话直接丢信息。

**机制**：`budget.over_budget()`（`len(json)/4` 近似超阈值）触发 → `split_oldest()`
保留 system + 最近 `keep_recent` 条、取出中间最早块 → `Summarizer.summarize()`（LLM）
压成一条 `role="system"` 摘要 → **替换**（不是丢弃），对话得以无限延续。触发点在
`step` 进 LLM 之前。

**落点**：`core/budget.py` + `core/loop.py:_compact` + `adapters/llm_summarizer.py`。

## 3. Stop-reason 处理

**问题**：旧 `llm.py` 丢弃 `finish_reason`，回复被 `max_tokens` 截断时察觉不到。

**机制**：`OpenAILLM` 把 provider 的 `finish_reason` 带进 `Completion.stop_reason`，
loop 的 E 段四路分流：
- `content_filter` → `status=error`；
- 有 `tool_calls` → 处理工具（不论 stop_reason 细节）；
- `length` → 把半截 content 回写、追加「continue」提示、下一轮续写（续写吃
  `max_rounds`，防死循环）；
- `stop` 且无工具 → finalize。

**落点**：`adapters/openai_llm.py`（保留字段）+ `core/loop.py` E 段。约 20 行。

## 4. Checkpoint / Resume

**问题**：旧 `Harness.run()` 是一次性生成器，崩了不能 resume。

**机制**：`RunState` 全可序列化 → `Agent._drive` 每轮 `Store.save(run_id, state)`；
`resume(run_id)` 走 `Store.load` 读回、翻 `awaiting_approval`→`running`、driver 重入
续跑；`done` 后 `Store.delete` 清盘。`SqliteStore` 跨进程，`MemoryStore` 进程内。

**关键边界**：core 永不持有活对象，工具结果落成字符串（见
[核心架构 §5](core-and-ports.md#5-checkpoint-的序列化边界最大技术风险)）。

**落点**：`app/agent.py` + `adapters/sqlite_store.py` + `core/models.py`
（`state_to_dict`/`state_from_dict`）。

## 5. 子 agent 委派

**机制**：`delegate` 伪工具（仅当 `enable_delegation=True` 时渲染）→
`SubAgentRunner.run(task, tools, skills)`：`app/subagent.py` new 一个上下文隔离的子
`Agent`（独立 `RunState`、独立 `MemoryStore`、父工具/skills 的**受限子集**、**禁用再委派**
防无限递归），跑到 final，把 `final.content` 当 tool_result 回填父 loop。对父 loop 而言
等同一个慢工具，事件流里只多一个 `delegated` 事件。

**落点**：`core/loop.py:_delegate` + `app/subagent.py`。约 25 行。

## 6. 人在环中（审批）

**机制**：loop 处理工具时，若 `deps.approval_required(call, tool)`（默认：配了
approver **且** `tool.writes==True`）→ 写 `pending_approval`、转 `awaiting_approval`
**终态**、落盘暂停、generator 结束。`resume()` 时 loop 的 A 段调 `Approver.review(call)`
拿 `Decision`：`approve`→执行 / `reject`→回填拒绝 tool_result / `edit`→用新参数执行。
同一 assistant 回合里**剩余未答工具**从消息历史推导（`_unanswered_calls`），不重复执行。

**双实现**：`AutoApprover`（默认放行 / 可注入 policy）、`InteractiveApprover`（同步
CLI 或回调）。阻塞发生在 adapter 内，core 只看 `Decision`。

**落点**：`core/loop.py` A+F 段 + `adapters/auto_approver.py` / `interactive_approver.py`。

## 7. 结构化输出

**机制**：`AgentConfig.output_schema` → 进 `RunState` → driver 把 schema 拼进 system
prompt，loop 给 LLM 传 `response_format={"type":"json_object"}`（provider 无关）；
`_finalize` 把 `comp.content` 解析成 dict 放进 `final["structured"]`，解析失败则回退
带 error。

**落点**：`core/loop.py:_finalize` + `app/agent.py:_seed`。约 15 行。

---

## 基础工具电池 × 审批（配套设计）

`tools/builtins.py` 的危险三件套（`write_file` / `edit_file` / `run_bash`）统一
`writes=True`，正好命中能力 6 的审批门。宿主 `tools=[*builtins(root=..., allow=...)]`
opt-in，配 `approver=InteractiveApprover()` 即得「能改文件/跑命令、但每次危险操作要人
点头」的 agent。详见 [如何搭一个 agent](../guides/how-to-build-an-agent.md) 第 5 节。
