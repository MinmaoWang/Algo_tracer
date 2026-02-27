# Agentic Code Reader 模块说明

本文档简要介绍 `agentic_code_reader` 项目中每个 Python 模块的作用。

## 核心模块

### `cli.py` - 命令行接口
- **作用**: 提供命令行入口，解析用户输入的参数
- **主要功能**:
  - 使用 `argparse` 定义命令行参数（`--repo`, `--target`, `--hint-file` 等）
  - 调用 `orchestrator.run()` 启动主流程
  - 处理导入路径，支持直接运行和作为模块运行

### `orchestrator.py` - 主协调器
- **作用**: 系统的核心控制模块，协调各个组件的工作流程
- **主要功能**:
  - 初始化代码索引（`RepoIndex`）和搜索引擎（`SearchEngine`）
  - 初始化 LLM 客户端和三个代理（Planner、Executor、Synthesizer）
  - 执行主循环：Planner 规划 → Executor 执行 → 迭代更新
  - 调用 Synthesizer 生成最终解释
  - 保存结果到 `blackboard.json` 和 `final_explanation.md`

### `indexer.py` - 代码索引器
- **作用**: 构建全局代码符号索引
- **主要功能**:
  - 遍历代码库中的所有 Python 文件
  - 使用 AST 解析提取函数、类、方法定义
  - 构建符号字典（`symbols`）、短名映射（`shortname_map`）和导入映射（`import_map`）
  - 为每个符号生成 `SymbolDef` 对象，包含限定名、文件路径、行号范围等信息

### `search.py` - 搜索引擎
- **作用**: 实现符号解析和代码搜索功能
- **主要功能**:
  - `resolve_symbol()`: 多策略符号解析（精确匹配、后缀匹配、两段式匹配、三段式匹配、短名匹配）
  - `open_symbol()`: 打开符号定义，读取代码片段并提取函数调用
  - `extract_calls_from_def()`: 从代码中提取函数调用
  - `find_usages()`: 使用 grep 搜索符号的使用位置
  - `hybrid_search()`: 混合搜索，结合符号解析和文本搜索

### `agents.py` - 代理模块
- **作用**: 定义三个智能代理（Planner、Executor、Synthesizer）
- **主要功能**:
  - **PlannerAgent**: 规划代理
    - 分析 blackboard 状态，决定需要探索哪些符号
    - 生成 `Action` 列表（`OPEN_SYMBOL`, `HYBRID_SEARCH`, `FIND_USAGES`）
    - 判断是否停止迭代
  - **ExecutorAgent**: 执行代理
    - 执行 Planner 规划的动作
    - 调用 `SearchEngine` 的方法获取证据
    - 更新 blackboard 状态
  - **SynthesizerAgent**: 综合代理
    - 基于 blackboard 中的所有证据生成最终的人类可读解释
  - `format_blackboard_summary()`: 格式化 blackboard 摘要供 Planner 使用

### `blackboard.py` - 黑板数据结构
- **作用**: 定义共享数据结构和更新机制
- **主要功能**:
  - `new_blackboard()`: 创建新的黑板实例
  - `bb_add_evidence()`: 添加符号证据到黑板
  - `bb_mark_unresolved()`: 标记未解析的符号
  - `bb_log()`: 记录日志消息
  - `apply_patch()`: 应用 Planner 的补丁更新

### `models.py` - 数据模型
- **作用**: 定义系统中使用的数据结构（使用 Pydantic）
- **主要类型**:
  - `Action`: 表示 Planner 规划的动作（OPEN_SYMBOL、HYBRID_SEARCH、FIND_USAGES）
  - `PlannerOutput`: Planner 的输出，包含动作列表、停止标志、原因和补丁
  - `SymbolDef`: 符号定义，包含限定名、类型、文件路径、行号范围
  - `Evidence`: 证据对象，包含符号定义、代码片段和提取的调用列表

### `llm_client.py` - LLM 客户端
- **作用**: 封装与大语言模型的交互
- **主要功能**:
  - 初始化 OpenAI 客户端（连接到 DeepSeek API）
  - `parse()`: 调用 LLM 并解析结构化输出（使用 Pydantic schema）
  - `chat()`: 简单的聊天接口
  - 处理 JSON schema 验证和错误重试

### `utils.py` - 工具函数
- **作用**: 提供通用的工具函数
- **主要功能**:
  - `read_text()` / `write_text()`: 文件读写
  - `write_json()`: JSON 文件写入
  - `clip_lines()`: 截断过长的文本
  - `contains_forbidden_words()`: 检查是否包含不确定词汇
  - `safe_relpath()`: 安全地计算相对路径
  - `RunLogger`: 运行日志记录器类

### `__init__.py` - 包初始化文件
- **作用**: 将目录标记为 Python 包，可能包含包的元信息或导出主要接口

## 模块依赖关系

```
cli.py
  └─> orchestrator.py
        ├─> indexer.py ──> models.py
        ├─> search.py ──> models.py, indexer.py
        ├─> blackboard.py ──> models.py
        ├─> agents.py ──> models.py, search.py, blackboard.py, llm_client.py
        ├─> llm_client.py
        └─> utils.py
```

## 工作流程

1. **初始化阶段** (`orchestrator.py`):
   - `indexer.py` 构建代码索引
   - 初始化 `SearchEngine`、`LLM` 和三个代理

2. **Bootstrap 阶段** (`orchestrator.py`):
   - 打开目标符号，提取初始调用列表

3. **迭代阶段** (`orchestrator.py` + `agents.py`):
   - Planner 分析 blackboard，规划动作
   - Executor 执行动作，更新 blackboard
   - 重复直到 Planner 决定停止

4. **综合阶段** (`orchestrator.py` + `agents.py`):
   - Synthesizer 基于所有证据生成最终解释

5. **输出阶段** (`orchestrator.py`):
   - 保存 `blackboard.json` 和 `final_explanation.md`

## 设计模式

- **黑板模式**: `blackboard.py` 作为共享数据结构，三个代理通过它通信
- **策略模式**: `search.py` 中的多策略符号解析
- **代理模式**: `agents.py` 中的三个代理各司其职
- **工厂模式**: `models.py` 中的 Pydantic 模型用于数据验证和序列化
