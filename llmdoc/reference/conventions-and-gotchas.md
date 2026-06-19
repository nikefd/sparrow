# 编码约定与已知坑

> 改 sparrow 代码前先扫一眼。约定从现有代码提炼，坑是真实存在的边界与陷阱。

## 编码约定

- **语言**：这是面向全球的开源库。代码、注释、docstring、commit message 一律
  **英文**。README 是中英双语（`README.md` / `README.zh-CN.md`），保持。
  llmdoc 内部文档用中文（给深入者和 AI 看）。
- **核心仅 stdlib**：引擎零运行时三方依赖（`pyproject.toml:dependencies = []`）。
  只用 `urllib` / `sqlite3` / `ast` / `inspect` 等标准库。**新增 import 三方库前
  务必三思**——这是 sparrow 的核心卖点之一，破坏它等于改变项目定位。
- **工具一律返回 dict**：带 `source` 才能溯源；状态写入加 `writes=True`。
- **领域无关**：引擎层（`harness` / `registry` / `llm` / `expr`）不得出现任何具体
  业务概念。所有领域知识只能从 `AgentConfig` 注入。
- **错误不抛给调用方**：工具异常在 `ToolRegistry.run` 兜成 `{"error": ...}`；
  LLM/其它异常在 `Harness.run` 兜成 `error` 事件。保持这个「循环不崩」的契约。
- **可选能力静默降级**：`recall_provider` 失败、journal 写入失败等都被静默吞掉，
  绝不阻塞对话。新增可选钩子时沿用此模式。
- **两处版本号**：`pyproject.toml:version` 与 `sparrow/__init__.py:__version__`
  必须同步，发版前一起改（见 [发布指南](../guides/how-to-release.md)）。

## 已知坑 / 边界

1. **必须配 LLM api key**：没配 `SPARROW_LLM_API_KEY` / `DEEPSEEK_API_KEY` 时
   `chat()` 直接抛 `LLMError`。测试（`tests/test_engine.py`）刻意只测
   registry/expr/memory，**不触网、不调 LLM**，所以无 key 也能跑测试。
2. **context 预算很粗**：只「保留最近 N 条 + 单结果字符截断」，没有 token 级精算。
   超长工具结果会被 `…(truncated)` 粗暴砍掉，可能丢信息——需要时调大
   `tool_result_max_chars`。
3. **`conversation_id` 自动注入只给写工具**：`Harness` 只对 `writes=True` 的工具
   `setdefault("conversation_id", ...)`。读工具想要 conversation_id 得自己从参数拿。
4. **面板 `source` 可信但工具未沙箱**：受限表达式（`expr.py`）是真沙箱；但**工具
   函数本身是宿主写的普通 Python，sparrow 不沙箱它**。别把不可信输入直接喂进会执行
   危险操作的工具。
5. **`is_safe_expr` 只防代码执行，不防逻辑错**：它保证表达式跑不了任意代码，但
   不校验字段是否存在（缺字段当 0）、不防除零（返回 0）。表达式写错只会得到
   静默的兜底值，不会报错。
6. **SQLite 每次操作开新连接**：`Memory._conn()` 每次调用新建连接。简单可靠，但
   高并发写入下要注意 SQLite 的锁行为；当前定位（单用户 dashboard）下无虞。
7. **流式 usage 不准**：`chat(on_delta=...)` 流式模式下 `USAGE_LOG` 记的
   prompt/completion tokens 是 0（流式响应不返回 usage），只有延迟可信。
8. **前端 README 与 i18n**：`sparrow-chat.js` 的全部用户可见文案默认英文，通过
   `mount({i18n: {...}})` 覆盖本地化。挂载选项以 `sparrow/web/README.md` 为准。

## 不要碰什么

- 别给引擎层引入业务逻辑或三方依赖。
- 别破坏「LLM 只产声明，不产代码」的边界——尤其别放宽 `expr.py` 的 AST 白名单
  去支持函数调用/属性访问。
- 完成任务后**是否更新 llmdoc 由用户决定**，不要自动改文档。
- 未经用户要求不要 `git push`。
