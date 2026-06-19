# 记忆与面板架构

> 讲 sparrow 的三层记忆、「面板即记忆」的设计，以及受限表达式引擎。模块：
> `memory.py` / `panel_data.py` / `expr.py`。引擎主循环见
> [引擎架构](engine-architecture.md)。

记忆层是**可选**的：没有 dashboard 的宿主可以完全忽略面板，只用对话 + 流水，
甚至彻底不用记忆。

## 1. 三层记忆，一个 SQLite 文件

`Memory` 持有一个 `ui.db`，里面四张表覆盖三类记忆（`memory.py:47` 建表）：

| 层 | 表 | 记什么 |
|---|---|---|
| **对话记忆** | `conversations` / `messages` | 多轮对话历史，按 conversation_id 组织 |
| **物化记忆** | `panels` | 面板配方（声明式 spec，非快照） |
| **情景记忆** | `journal` | append-only 流水：谁、何时、做了什么 |

### 1a. 为什么单独一个 UI db

agent 记忆与宿主的**业务数据物理隔离**。后果很重要：agent 的写权限天然被关在这
个 db 里——查询工具读业务数据，写工具只动 `ui.db`。**LLM 能塑造呈现，永远碰不到
底层真相**（读写分级，见 [引擎信条](engine-architecture.md#1-指导信条llm-只产声明不产代码)）。

### 1b. 情景记忆（journal）

append-only。`Harness` 写 agent 的动作（写工具调用），宿主写用户的动作，可以都写
system 的动作——**记忆覆盖所有 actor**，agent 的世界观才完整。

`journal_summary_for_prompt(limit=12)` 把最近活动压成每行一条的摘要，接到
`AgentConfig.recall_provider` 上，就能注入 system prompt 充当**情景回忆**——agent
于是「记得」上次发生过什么。

## 2. 面板即记忆（materialized memory）

面向 dashboard 类应用。agent 可以把对话中的一个洞察**固化成一个面板**。关键设计：

> **面板存的是配方，不是快照。**

一个面板 spec 是声明式的：`{id, title, viz, query: {tool, args}, transform | columns,
refresh}`。它说的是「用哪个工具拿数据、怎么加工」，不存任何数据。于是每次打开页面
都按**实时数据**重新计算（`panel_data.resolve`，`panel_data.py:39`）。

### 2a. 数据流

```
list_panels() 拿到 spec
   → registry.run(query_tool, query_args)   # 实时取数
   → 有 columns? → _apply_columns（字段直读 / expr 受限求值，逐行）
     否则        → apply_transform（宿主登记的标量后处理，如 count）
   → {id, title, viz, data}
```

`builtin` 类面板是宿主 UI 自己渲染的（如固定看板页），不走 spec 解析，
`resolve` 直接返回占位标记。

### 2b. 面板工具与校验

`panel_tools(memory)`（`__init__.py:37`）是个工厂，返回三个绑定到某个 `Memory` 的
标准工具：`create_panel` / `archive_panel` / `list_panels`，加进
`AgentConfig.tools` 即给 agent「面板即记忆」能力。

`create_panel` 的 description 明确写了「Only call after the user explicitly
agrees」——**新建/归档面板需用户确认**，这是产品约定写进了 prompt。

`validate_spec`（`memory.py:109`）在落库前严格校验：id 必须字母数字/连字符、
viz 必须是 `VIZ_TYPES` 之一、refresh 必须是 `REFRESH_TYPES` 之一、`query.tool`
必须是已注册工具、每个 column 必须有 title 且 **expr 必须通过 `is_safe_expr`**。
archive 是可逆的（`status='archived'`），builtin 面板只读不可归档。

## 3. 受限表达式引擎（expr.py）

面板的自定义计算列（`{"title": "市值", "expr": "current_price * shares"}`）需要让
LLM **声明**一个公式，但绝不能让它执行任意代码。`expr.py` 就是这道安全边界。

**安全模型**：只允许「字段名 + 数字/字符串常量 + 四则运算 + 括号 + 一元正负」。
函数调用、属性访问、下标、推导式等**全部禁止**。实现方式是 `ast.parse` 后只放行
白名单节点（`is_safe_expr`，`expr.py:89`），创建面板时静态校验；`safe_eval`
（`expr.py:76`）逐行求值，并做了几处「不炸」的兜底：

- 缺字段 → 当 0，整列不崩。
- 文本进了算术 → 安全回退 0（文本列原样保留）。
- 除零 → 0；求值失败 → None（渲染层显示占位符）。
- float 结果 round 到 2 位。

这正是「LLM 只产声明，不产代码」在面板列上的落地：模型能组合衍生指标
（`(current_price - avg_cost) / avg_cost * 100`），但 `__import__('os')`、
`shares.__class__`、`open('/etc/passwd')` 一律被拒（见 `tests/test_engine.py` 的
`test_is_safe_expr_blocks_evil`）。

## 4. 配置项速查

| 常量 / 字段 | 值 | 出处 |
|---|---|---|
| `VIZ_TYPES` | metric-card / table / line-chart / bar-chart / markdown | `memory.py:22` |
| `REFRESH_TYPES` | live / daily / static | `memory.py:23` |
| `Memory.transforms` | `{name: fn(data)->dict}` 标量后处理 | 宿主注入 |
| `Memory.builtin_panels` | `[(id, title, tab, note)]` 宿主预登记面板 | 宿主注入 |
| `Memory.tool_names` | 允许作面板数据源的工具名集合（spec 校验用） | 宿主注入 |
