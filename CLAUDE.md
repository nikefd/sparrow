<always-step-one>
**STEP ONE IS ALWAYS: READ LLMDOC!**

Before doing ANYTHING else in this repo, you MUST:

1. Check that `llmdoc/` exists, then read `llmdoc/index.md` first.
2. Read ALL documents in `llmdoc/overview/`.
3. Read the relevant `architecture/` / `guides/` / `reference/` docs before
   touching code.

This is NON-NEGOTIABLE. Documentation first, code second.
</always-step-one>

<llmdoc-structure>

- `llmdoc/index.md` — 主索引与快速导航表，永远先读这个（入口）。
- `llmdoc/overview/` — 「这是什么项目」：定位、技术栈、目录结构。该目录全部必读。
- `llmdoc/guides/` — 「我该怎么做 X」：分步操作（搭 agent、发布）。
- `llmdoc/architecture/` — 「它是怎么实现的」：引擎循环、记忆与面板设计。
- `llmdoc/reference/` — 「X 的细节是什么」：API 速查、编码约定、已知坑。

</llmdoc-structure>

<project-constraints>

sparrow 是一个**面向全球的开源 Python 库**（PyPI: `sparrow-agent`，import 名
`sparrow`）。一个「麻雀虽小、五脏俱全」的 agent harness。铁律：

- **语言**：代码、注释、docstring、commit message 一律**英文**。README 是中英双语
  （`README.md` / `README.zh-CN.md`），保持其双语策略。llmdoc 内部文档用中文。
  与用户对话用简体中文。
- **核心仅 stdlib**：引擎零运行时三方依赖（`urllib`/`sqlite3`/`ast`）。**新增三方
  依赖前必须三思**——零依赖是 sparrow 的核心卖点，破坏它等于改变项目定位。
- **领域无关**：引擎层（`harness`/`registry`/`llm`/`expr`）不得出现具体业务概念。
  领域知识只能从 `AgentConfig` 注入。改这些模块前先读
  `llmdoc/architecture/engine-architecture.md`。
- **别破坏安全边界**：「LLM 只产声明，不产代码」是全库信条。尤其**不要放宽
  `expr.py` 的 AST 白名单**去支持函数调用/属性访问。
- **两处版本号**：`pyproject.toml:version` 与 `sparrow/__init__.py:__version__`
  必须同步，发版前一起改。
- **怎么跑测试**：`pip install -e ".[dev]"` 然后 `python -m pytest -q`（纯本地，
  无网络、无 LLM 调用）。
- **怎么跑示例**：`export SPARROW_LLM_API_KEY=sk-...` 后 `python examples/weather_agent.py`。
- 测试或构建失败时，**原样报告错误输出**，不要掩盖或淡化。

</project-constraints>

<doc-maintenance>

完成代码改动后，检查 llmdoc 是否需要同步（新公共 API → `reference/api-reference.md`；
改循环/事件 → `architecture/engine-architecture.md`；新坑 →
`reference/conventions-and-gotchas.md`；并在 `index.md` 快速导航补一行）。
**是否真的更新文档由用户决定，先征求同意，不要自动改。**

</doc-maintenance>

<git-conventions>

- commit message 格式：`<scope>: <中文描述>`，scope 用英文小写
  （如 `engine` / `memory` / `web` / `docs` / `ci` / `chore` / `fix`）。
- 一次 commit 只做一件事；提交前用 `git diff` 确认改动范围。
- **未经用户要求不要 `git push`。**

</git-conventions>
