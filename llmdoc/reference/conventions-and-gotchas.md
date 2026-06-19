# 编码约定与已知坑

> 改 sparrow 代码前先扫一眼。约定从现有代码提炼，坑是真实存在的边界与陷阱。

## 编码约定

- **语言**：面向全球的开源库。代码、注释、docstring、commit message 一律**英文**。
  README 中英双语（`README.md` / `README.zh-CN.md`）。llmdoc 内部文档用中文。与用户
  对话用简体中文。
- **核心仅 stdlib**：`core` / `ports` 零运行时三方依赖（`pyproject.toml:dependencies=[]`）。
  只用 `urllib` / `sqlite3` / `ast` / `inspect` 等。**新增三方依赖前务必三思**——零依赖是
  sparrow 卖点。
- **分层纪律（ports & adapters）**：
  - `core/` 不得 import `adapters` / `app`，不得做任何 I/O；只依赖 `ports` 的 Protocol。
  - 外部副作用（HTTP/sqlite/subprocess/clock）只能在 `adapters/`。
  - 立 port 守则：**两个 adapter 才算一个真 seam**，别造单实现的假 port。
- **领域无关**：`core` 不得出现具体业务概念，全部从 `AgentConfig` 注入。
- **错误不抛给调用方**：工具异常在 `ToolRegistry.run` 兜成 `{"error":...}`；LLM/其它
  异常在 `step` 兜成 `error` 事件。保持「循环不崩」契约。
- **工具一律返回 JSON-able dict**：带 `source` 才溯源；写工具加 `writes=True`。
- **`step` 保持纯**：`core/loop.py:step` 无 I/O，副作用全走 `deps` 的 port。新增能力
  也收口进这个 reducer，别在 driver 里塞业务逻辑。
- **两处版本号**：`pyproject.toml:version` 与 `sparrow/__init__.py:__version__` 必须同步，
  发版前一起改（见 [发布指南](../guides/how-to-release.md)）。

## 已知坑 / 边界

1. **必须配 LLM api key**：没配 `SPARROW_LLM_API_KEY` / `DEEPSEEK_API_KEY` 时
   `OpenAILLM.complete()` 抛 `LLMError`。测试全程注 fake、**不触网**，所以无 key 也能跑。
2. **token 估算是粗近似**：`len(json)/4`，偏离真实 tokenizer。压缩阈值（`token_budget`）
   要留余量（按真实窗口 ~80% 设）。流式拿不到 usage 时回退近似，别让 0 污染 budget。
3. **`length` 续写可能多耗轮次**：被 `max_tokens` 截断会触发续写，续写吃 `max_rounds`
   预算防死循环——但模型反复截断会更快耗尽轮次后被强制 finalize。需要时调大 `max_tokens`。
4. **checkpoint 序列化边界**：`RunState` 只含纯数据，core 永不持有活对象，工具结果落成
   字符串。**工具若返回不可 JSON 序列化的对象，resume 会坏**。ports 是 `Deps`、不进
   RunState，resume 时由 driver 重新注入——所以 `Agent` 的 adapter 装配在 resume 前必须
   一致。
5. **审批暂停是「终态 + checkpoint」**：命中写工具且配了 approver → generator 结束、落盘。
   必须 `resume(run_id)` 才续。**没配 `store` 也能跑，但 `MemoryStore` 进程内**，进程退出
   后无法 resume——要跨进程恢复得用 `SqliteStore`。
6. **`needs_approval` 默认只看 `writes` 且需 approver**：不配 `approver` 时**完全不审批**
   （`approval_required` 直接返回 False）。想门控就传 `approver=...`。
7. **子 agent 共享父的 LLM/clock/approver，但 store 独立**：`SubAgentRunner` 给子 agent
   一个全新 `MemoryStore`（隔离），并**禁用再委派**防无限递归。子 agent 的 checkpoint 不
   与父混。
8. **受限表达式只防代码执行，不防逻辑错**：`expr.py` 保证跑不了任意代码，但缺字段当 0、
   除零返回 0、写错只得静默兜底值。AST 白名单**一行不放宽**。
9. **`Harness` 已 deprecated**：`sparrow.Harness` 是转调 `Agent` 的薄 shim，构造时发
   `DeprecationWarning`，yield 旧式 dict 事件。新代码用 `Agent`。
10. **前端 i18n**：`sparrow-chat.js` 文案默认英文，`mount({i18n})` 覆盖。挂载选项以
    `sparrow/web/README.md` 为准。

## 不要碰什么

- 别给 `core`/`ports` 引入业务逻辑或三方依赖。
- 别破坏「LLM 只产声明，不产代码」边界——尤其别放宽 `expr.py` 的 AST 白名单。
- 别在 `step` 里做 I/O，别让 ports 进 `RunState`（会坏 checkpoint）。
- 完成任务后**是否更新 llmdoc 由用户决定**，不要自动改。
- 未经用户要求不要 `git push`。
