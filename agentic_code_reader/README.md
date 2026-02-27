# Agentic Code Reader

智能代码理解工具 - 模块化版本

## 目录结构

```
agentic_code_reader/
├── __init__.py          # 模块导出
├── utils.py             # 工具函数（文件读写、字符串处理等）
├── models.py            # 数据模型（Action, PlannerOutput, SymbolDef, Evidence）
├── indexer.py           # 代码索引（RepoIndex, AST 解析）
├── search.py            # 搜索引擎（SearchEngine, 符号解析、grep）
├── blackboard.py        # 黑板数据结构（blackboard 操作函数）
├── llm_client.py        # LLM 客户端（OpenAI/DeepSeek API 封装）
├── agents.py            # 代理（Planner, Executor, Synthesizer）
├── orchestrator.py      # 主协调逻辑（run 函数）
├── cli.py               # 命令行入口
└── README.md            # 本文件
```

## 模块说明

### utils.py
- 文件读写工具函数
- 字符串处理（clip_lines, contains_forbidden_words）
- 路径处理（safe_relpath）

### models.py
- `Action`: 规划动作模型
- `PlannerOutput`: Planner 输出模型
- `SymbolDef`: 符号定义数据类
- `Evidence`: 证据数据类

### indexer.py
- `RepoIndex`: 代码仓库索引类
- AST 解析和符号提取
- 导入关系分析

### search.py
- `SearchEngine`: 搜索引擎类
- 符号解析和查找
- 代码片段提取
- grep 搜索

### blackboard.py
- `new_blackboard`: 创建新黑板
- `bb_add_evidence`: 添加证据
- `bb_mark_unresolved`: 标记未解析符号
- `apply_patch`: 应用补丁

### llm_client.py
- `LLM`: LLM 客户端类
- 结构化输出解析
- 文本生成

### agents.py
- `PlannerAgent`: 规划代理
- `ExecutorAgent`: 执行代理
- `SynthesizerAgent`: 综合代理
- 相关的 prompt 和格式化函数

### orchestrator.py
- `run`: 主运行函数
- 协调 Planner、Executor、Synthesizer 的工作流程

### cli.py
- 命令行参数解析
- 调用 orchestrator.run



## 使用方法

先export一个api，在终端中运行：export DEEPSEEK_API_KEY=sk-xxxxxx

之后参考bash脚本