from typing import List, Dict, Any, Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.validators import validate_list_structure, validate_numeric_range

def _merge_dict_recursive(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    result = base.copy()
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dict_recursive(result[key], value)
        else:
            result[key] = value
    return result

def combine_multiple_datasets(datasets: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not validate_list_structure(datasets, min_length=1):
        return {}
    combined = {}
    for dataset in datasets:
        combined = _merge_dict_recursive(combined, dataset)
    return combined

def filter_data_by_threshold(data: List[float], threshold: float) -> List[float]:
    if not validate_list_structure(data):
        return []
    if not validate_numeric_range(threshold, 0.0, 1000.0):
        threshold = 0.0
    return [value for value in data if value >= threshold]

def calculate_batch_statistics(batches: List[List[float]]) -> Dict[str, float]:
    from core.transformers import aggregate_metrics
    if not validate_list_structure(batches):
        return {}
    all_values = []
    for batch in batches:
        if validate_list_structure(batch):
            all_values.extend(batch)
    if not all_values:
        return {}
    metrics = aggregate_metrics(all_values)
    return metrics