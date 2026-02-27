# LLM代码理解测试指南

## 仓库概述

这是一个专门设计的复杂测试代码库，用于评估LLM对Python代码的理解能力。代码库包含：

- **10层深度的函数调用链**
- **跨多个文件的函数依赖**
- **晦涩但逻辑一致的函数命名**
- **复杂的数据流转和处理逻辑**

## 目录结构

```
test_repo/
├── __init__.py
├── main.py                    # 主入口，包含最长调用链
├── core/                      # 核心模块
│   ├── validators.py         # 数据验证
│   ├── transformers.py       # 数据转换
│   └── computations.py       # 计算模块
├── processors/                # 处理器模块
│   ├── pipeline.py           # 处理管道
│   ├── formatters.py         # 格式化
│   └── exporters.py          # 导出（最长链终点）
└── utils/                     # 工具模块
    └── helpers.py            # 辅助函数
```

## 测试场景

### 1. 函数调用链追踪
**问题**: "从`main()`函数开始，追踪到最深层的函数调用，列出完整的10层调用路径"

**答案要点**:
- main() → process_data_pipeline() → _execute_computation_phase() 
- → compute_statistical_summary() → export_processing_results()
- → format_detailed_report() → _format_dict_structure() 
- → _format_numeric_value() → _serialize_to_dict() (递归)

### 2. 跨文件依赖分析
**问题**: "`process_data_pipeline`函数依赖哪些其他模块？列出所有导入的函数"

**答案要点**:
- core.validators: create_validation_context, validate_numeric_range
- core.computations: compute_spatial_relationship, compute_statistical_summary
- core.transformers: transform_data_structure

### 3. 函数命名模式理解
**问题**: "为什么函数名使用`chk`而不是`check`？这种命名模式有什么规律？"

**答案要点**:
- `chk_` = check（检查类函数）
- `_`前缀表示内部/私有函数
- 命名遵循缩写模式：sanitize, normalize, transform, compute, aggregate等

### 4. 数据流分析
**问题**: "数据从`input_data`到最终`output`经过了哪些转换步骤？"

**答案要点**:
1. 输入验证 (create_validation_context)
2. 数据转换 (transform_data_structure)
3. 空间计算 (compute_spatial_relationship)
4. 统计汇总 (compute_statistical_summary)
5. 格式化输出 (format_detailed_report)
6. 序列化 (serialize_to_dict)

### 5. 递归调用识别
**问题**: "找出所有递归调用的函数，并说明递归的终止条件"

**答案要点**:
- `_serialize_to_dict()`: 递归处理嵌套字典和列表
- 终止条件: 当值不是dict或list时返回

### 6. 模块职责理解
**问题**: "core模块、processors模块、utils模块各自负责什么功能？"

**答案要点**:
- core: 基础功能（验证、转换、计算）
- processors: 高级处理流程（管道、格式化、导出）
- utils: 通用辅助工具

## 运行测试

```bash
cd test_repo
python3 main.py
```

## 预期输出

程序会输出完整的数据处理结果，包括：
- 统计指标（sum, avg, max, min）
- 空间关系计算结果
- 详细的数据结构
- 序列化后的数据

## 评估标准

评估LLM理解能力时，关注：

1. **准确性**: 能否正确追踪函数调用链
2. **完整性**: 是否识别所有相关函数和依赖
3. **逻辑性**: 是否理解函数间的逻辑关系
4. **模式识别**: 是否识别出命名模式和代码结构
5. **上下文理解**: 是否理解代码的整体目的和设计意图

## 注意事项

- 函数名虽然晦涩，但遵循一定模式，不应误导LLM
- 所有函数都有实际功能，不是无意义的占位符
- 调用链是真实的，不是人为构造的虚假依赖
- 代码可以实际运行，验证逻辑正确性
