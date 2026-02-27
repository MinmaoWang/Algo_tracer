from typing import Dict, Any, Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from processors.formatters import format_detailed_report, format_output_summary
from core.computations import compute_statistical_summary

def _serialize_to_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    serialized = {}
    for key, value in data.items():
        if isinstance(value, dict):
            serialized[key] = _serialize_to_dict(value)
        elif isinstance(value, (int, float, str, bool, type(None))):
            serialized[key] = value
        elif isinstance(value, list):
            serialized[key] = [_serialize_to_dict(item) if isinstance(item, dict) else item for item in value]
        else:
            serialized[key] = str(value)
    return serialized

def _validate_export_data(data: Dict[str, Any]) -> bool:
    if not isinstance(data, dict):
        return False
    if 'statistics' in data:
        stats = data['statistics']
        if not isinstance(stats, dict) or 'count' not in stats:
            return False
    return True

def export_processing_results(processed_data: Dict[str, Any], format_type: str='summary') -> str:
    if not _validate_export_data(processed_data):
        return 'Invalid data for export'
    if format_type == 'summary':
        return format_output_summary(processed_data)
    elif format_type == 'detailed':
        detailed_report = format_detailed_report(processed_data)
        serialized = _serialize_to_dict(processed_data)
        return f'{detailed_report}\n\nSerialized Data:\n{serialized}'
    else:
        serialized = _serialize_to_dict(processed_data)
        return str(serialized)