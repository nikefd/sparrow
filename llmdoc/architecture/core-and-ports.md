# 核心与 ports 架构

> 讲 sparrow v2 的 hexagonal（ports & adapters）分层、纯状态机 `step()` reducer、
> 以及 checkpoint 的序列化边界。模块：`core/` + `ports/` + `adapters/` + `app/`。
> 七大能力各自怎么实现见 [七大能力](capabilities.md)。

## 1. 分层：ports & adapters

```
AgentConfig (app/config.py)   ← 注入面：system prompt + tools + skills + 审批/记忆配置
        │
        ▼
   Agent (app/agent.py)        ← 装配 + driver：调 step、每轮 checkpoint、resume
        │  持有 Deps（注入袋）
        ▼
   step() (core/loop.py)       ← 纯状态机 reducer，无 I/O，只认 ports
        │  通过 ports 调用
        ▼
   adapters/*                  ← 外部世界（HTTP/sqlite/subprocess/clock）都关在这
```

四层职责：

- **`core/`**——纯领域。零 I/O、零三方依赖、全可序列化、全可单测。只通过
  `ports` 的 Protocol 跟外界打交道。包含 `models`（dataclass）、`loop`（reducer）、
  `budget`（token 估算）、`schema`（自省/渲染/消息互转）。
- **`ports/`**——抽象接口（`typing.Protocol`）。core 只依赖这些。
- **`adapters/`**——port 的具体实现。所有外部副作用（urllib、sqlite、subprocess）
  都在这。
- **`app/`**——装配层。把 core 跟具体 adapter 接起来，驱动 loop。

引擎本身**领域无关**：换个业务只换 `AgentConfig` 里的工具和 prompt，core 一行不动。

## 2. 六个 ports

每个都是 `typing.Protocol`（结构化鸭子类型，零依赖、不强制继承、最易 fake）。
立 port 的守则：**两个 adapter 才算一个真 seam**——给 core 注 fake 来单测，算第二个
实现。

| Port | 方法 | 真实现 / fake |
|---|---|---|
| `LLM` | `complete(messages, *, tools, response_format, ...) -> Completion` | `OpenAILLM` / 测试 fake |
| `Store` | `save / load / delete` | `SqliteStore` / `MemoryStore` |
| `Approver` | `review(call) -> Decision` | `AutoApprover` / `InteractiveApprover` |
| `Clock` | `now() / new_id()` | `SystemClock` / 测试 fake |
| `Summarizer` | `summarize(messages) -> Message` | `LLMSummarizer` / 测试 fake |
| `SubAgentRunner` | `run(task, *, tools, skills) -> str` | `app.SubAgentRunner` / 测试 fake |

**刻意不立**的 port：LLMRouter、RetryPolicy、Tracer、PermissionPolicy——这些是
规模化产物，非本质，砍掉。**工具执行也不是 port**：工具是宿主普通函数，
`ToolRegistry.run` 已兜异常，包 port 是为分层而分层。

`LLM.complete` 必须把 provider 的 `finish_reason` 带进 `Completion.stop_reason`
——旧客户端把它丢了，导致截断回复无人察觉。这是 v2 的一处必修。

## 3. 纯状态机：`step(state, deps)`

`core/loop.py` 的 `step` 是设计的灵魂：

```python
def step(state: RunState, deps: Deps) -> tuple[RunState, list[Event]]:
    ...
```

它对一个 `RunState` 施加**一步变换**，返回新 state + 本步事件。**自身无 I/O**，
所有副作用走 `deps` 里的 port。七大能力的分流全部收口在这一个函数里：

```
step(state, deps):
  A. 若 pending_approval → 调 Approver.review → approve执行/reject回填/edit改参（resume 重入点）
  B. 若 over_budget(messages) → split_oldest → Summarizer.summarize → 替换为摘要
  C. 若 round >= max_rounds → 强制 finalize
  D. specs = schema.specs_for(skills)；comp = llm.complete(messages, tools=specs, response_format)
  E. stop_reason 分流：
       content_filter → status=error
       有 tool_calls  → 回写 assistant 意图,逐个处理（F）
       length         → 续写（吃 round 防死循环）
       stop & 无 tool → finalize
  F. 逐个 tool_call：
       activate_skill → 翻 active=True,展开 instructions+tools（白名单校验）
       delegate       → SubAgentRunner.run → 结果当 tool_result 回填
       writes 且有 approver → 写 pending_approval、status=awaiting_approval、return（落盘暂停）
       普通工具 → registry.run → 截断后回填 tool_result
```

### 3a. `Deps` 注入袋

`Deps`（`core/loop.py`）装着 live ports + 工具 registry + 调参（token_budget /
keep_recent / tool_result_max_chars / needs_approval）。**它绝不进 `RunState`**——
driver 每步重新注入。这是 checkpoint 能跨进程 resume 的关键边界（见第 5 节）。

## 4. driver 与 checkpoint：`Agent`

`app/agent.py` 的 `Agent` 是公共门面。`run()` / `resume()` 都是生成器：

```python
def _drive(self, state):
    while state.status == "running":
        state, events = step(state, self.deps)
        self.store.save(state.run_id, state)   # ★ 每轮 checkpoint
        yield from events
    if state.status == "done":
        self.store.delete(state.run_id)        # 成功清盘
    # awaiting_approval：暂停事件已发出,checkpoint 留着等 resume()
```

`resume(run_id)` 从 store 读回 state、把 `awaiting_approval` 翻回 `running`，让 driver
重入 → `step` 的 A 分支处理审批结果。

### 4a. 事件流协议

`run()`/`resume()` 只 yield 这些事件，传输层照单序列化：

| 事件 | 关键字段 | 含义 |
|---|---|---|
| `tool_call` | name / label / arguments | 模型要调某工具 |
| `tool_result` | name / summary | 工具返回（已压成一行） |
| `skill_activated` | name | 某 skill 被激活 |
| `compacted` | freed | 发生了一次上下文压缩 |
| `awaiting_approval` | run_id / call | 暂停等审批（generator 随后结束） |
| `delegated` | task | 委派给子 agent |
| `final` | content / citations（或 structured） | 最终答案 + 溯源 |
| `error` | error | LLM 或内容过滤异常 |

这层协议是 sparrow 与前端（`sparrow-chat.js` 走 SSE）之间的契约。

## 5. Checkpoint 的序列化边界（最大技术风险）

`RunState` 是**唯一被持久化的东西**，且**只含纯数据**：无函数、无连接、无 registry。
要点：

- 工具结果可能含不可序列化对象（datetime、自定义类）。loop 在 `_append_tool_result`
  时就 `json.dumps(out, default=str)` 落成 `Message.content` **字符串**——**core 永不
  持有活对象**。约定沿用「工具必须返回 JSON-able dict」。
- ports 是 `Deps`，**不进 RunState**，driver 每步重新注入。所以一个 run 可以存盘、
  在另一进程读回、继续跑。
- `MemoryStore` 也走 `state_to_dict`/`state_from_dict` 往返，故意暴露同一条序列化边界，
  能尽早抓出「不小心存了活对象」的 bug。

## 6. 审批暂停为什么不破坏生成器流

把「暂停」建模成**一个普通终态 + checkpoint**，而非生成器里 yield 后阻塞等输入。
生成器只 push 事件、绝不 pull 外部输入；需要外部输入（审批）时就**结束生成器、落盘、
靠 `resume()` 重入**。子 agent 是同步嵌套调用，对父 loop 等同一个慢工具。于是事件流
始终单向、可序列化、可重放。
