import re
from typing import Any, Dict, List, Optional

def _chk_datatype_consistency(raw_val: Any, expected_type: type) -> bool:
    if expected_type == str:
        return isinstance(raw_val, str) and len(raw_val) > 0
    elif expected_type == int:
        return isinstance(raw_val, int) and raw_val >= 0
    elif expected_type == float:
        return isinstance(raw_val, (int, float)) and raw_val >= 0.0
    elif expected_type == list:
        return isinstance(raw_val, list) and len(raw_val) > 0
    return False

def _sanitize_input_string(dirty_str: str) -> str:
    if not isinstance(dirty_str, str):
        return ''
    cleaned = re.sub('[^\\w\\s-]', '', dirty_str)
    return cleaned.strip()

def validate_numeric_range(value: float, min_val: float, max_val: float) -> bool:
    if not _chk_datatype_consistency(value, float):
        return False
    return min_val <= value <= max_val

def validate_string_format(text: str, pattern: str) -> bool:
    sanitized = _sanitize_input_string(text)
    if not sanitized:
        return False
    return bool(re.match(pattern, sanitized))

def validate_list_structure(data_list: List[Any], min_length: int=1) -> bool:
    if not _chk_datatype_consistency(data_list, list):
        return False
    return len(data_list) >= min_length

def create_validation_context(fields: Dict[str, Any]) -> Dict[str, bool]:
    results = {}
    for field_name, field_value in fields.items():
        if isinstance(field_value, str):
            results[field_name] = bool(_sanitize_input_string(field_value))
        elif isinstance(field_value, (int, float)):
            results[field_name] = isinstance(field_value, (int, float))
        elif isinstance(field_value, list):
            results[field_name] = validate_list_structure(field_value)
        else:
            results[field_name] = False
    return results