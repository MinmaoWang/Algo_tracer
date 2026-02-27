from typing import Any, Dict, List, Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.validators import validate_numeric_range, validate_string_format

def _normalize_numeric_value(val: Any, default: float=0.0) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def _apply_scaling_factor(num: float, factor: float) -> float:
    if not validate_numeric_range(factor, 0.1, 10.0):
        factor = 1.0
    return num * factor

def transform_coordinate_system(x: float, y: float, scale: float=1.0) -> Dict[str, float]:
    normalized_x = _normalize_numeric_value(x)
    normalized_y = _normalize_numeric_value(y)
    scaled_x = _apply_scaling_factor(normalized_x, scale)
    scaled_y = _apply_scaling_factor(normalized_y, scale)
    return {'x': scaled_x, 'y': scaled_y}

def transform_data_structure(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    transformed = {}
    for key, value in raw_data.items():
        if isinstance(value, str):
            if validate_string_format(value, '^[a-zA-Z0-9_]+$'):
                transformed[key] = value.upper()
        elif isinstance(value, (int, float)):
            transformed[key] = _normalize_numeric_value(value)
        elif isinstance(value, dict):
            transformed[key] = transform_data_structure(value)
        else:
            transformed[key] = value
    return transformed

def aggregate_metrics(values: List[float]) -> Dict[str, float]:
    if not values:
        return {'sum': 0.0, 'avg': 0.0, 'max': 0.0, 'min': 0.0}
    normalized_values = [_normalize_numeric_value(v) for v in values]
    total = sum(normalized_values)
    count = len(normalized_values)
    avg = total / count if count > 0 else 0.0
    return {'sum': total, 'avg': avg, 'max': max(normalized_values), 'min': min(normalized_values)}