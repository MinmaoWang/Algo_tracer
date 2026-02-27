from typing import Dict, Any, List
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.transformers import aggregate_metrics
from core.computations import compute_statistical_summary

def _format_numeric_value(value: float, precision: int=2) -> str:
    return f'{value:.{precision}f}'

def _format_dict_structure(data: Dict[str, Any], indent: int=0) -> str:
    lines = []
    prefix = '  ' * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f'{prefix}{key}:')
            lines.append(_format_dict_structure(value, indent + 1))
        elif isinstance(value, (int, float)):
            lines.append(f'{prefix}{key}: {_format_numeric_value(float(value))}')
        elif isinstance(value, list):
            lines.append(f'{prefix}{key}: [{len(value)} items]')
        else:
            lines.append(f'{prefix}{key}: {str(value)}')
    return '\n'.join(lines)

def format_output_summary(processed_data: Dict[str, Any]) -> str:
    summary_parts = []
    if 'statistics' in processed_data:
        stats = processed_data['statistics']
        if 'metrics' in stats:
            metrics = stats['metrics']
            summary_parts.append('Metrics:')
            for key, value in metrics.items():
                formatted = _format_numeric_value(value)
                summary_parts.append(f'  {key}: {formatted}')
    if 'spatial' in processed_data:
        spatial = processed_data['spatial']
        if 'distance' in spatial:
            distance_str = _format_numeric_value(spatial['distance'])
            summary_parts.append(f'Distance: {distance_str}')
    return '\n'.join(summary_parts)

def format_detailed_report(data: Dict[str, Any]) -> str:
    report_lines = ['=== Detailed Processing Report ===']
    if 'statistics' in data:
        stats_summary = format_output_summary({'statistics': data['statistics']})
        report_lines.append('\nStatistics:')
        report_lines.append(stats_summary)
    report_lines.append('\nFull Data Structure:')
    formatted_structure = _format_dict_structure(data, indent=1)
    report_lines.append(formatted_structure)
    return '\n'.join(report_lines)