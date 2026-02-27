# 测试代码库

这是一个专门设计用于测试LLM代码理解能力的复杂代码库。

## 结构说明

### 核心模块 (`core/`)
- `validators.py`: 数据验证工具
- `transformers.py`: 数据转换工具
- `computations.py`: 计算模块

### 处理器模块 (`processors/`)
- `pipeline.py`: 处理管道
- `formatters.py`: 格式化模块
- `exporters.py`: 导出模块

## 函数调用链

### 最长调用链（10层）
```
main() 
  -> process_data_pipeline()
    -> _initialize_processing_state()
      -> create_validation_context()
        -> _sanitize_input_string()
    -> _execute_transformation_phase()
      -> transform_data_structure()
        -> validate_string_format()
          -> _sanitize_input_string()
    -> _execute_computation_phase()
      -> compute_spatial_relationship()
        -> transform_coordinate_system()
          -> _normalize_numeric_value()
          -> _apply_scaling_factor()
        -> _compute_euclidean_distance()
      -> compute_statistical_summary()
        -> transform_data_structure()
          -> ...
        -> aggregate_metrics()
          -> _normalize_numeric_value()
        -> _calculate_weighted_average()
          -> aggregate_metrics()
  -> export_processing_results()
    -> _validate_export_data()
    -> format_detailed_report()
      -> format_output_summary()
        -> _format_numeric_value()
      -> _format_dict_structure()
        -> _format_numeric_value()
    -> _serialize_to_dict()
      -> _serialize_to_dict() (递归)
```

## 命名规则

函数名虽然晦涩，但遵循一定模式：
- `_` 前缀：内部/私有函数
- `chk_`: check（检查）
- `sanitize_`: 清理/净化
- `normalize_`: 规范化
- `transform_`: 转换
- `compute_`: 计算
- `aggregate_`: 聚合
- `format_`: 格式化
- `export_`: 导出
- `serialize_`: 序列化

## 测试场景

1. **函数调用链追踪**: 追踪从 `main()` 到最深层的调用路径
2. **跨文件依赖分析**: 理解模块间的导入和调用关系
3. **数据流分析**: 追踪数据在函数间的流转
4. **函数职责理解**: 理解每个函数的作用和职责

## 运行示例

```bash
python main.py
```
