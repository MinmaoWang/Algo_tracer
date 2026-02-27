from typing import Dict, List, Any, Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.validators import create_validation_context, validate_numeric_range
from core.computations import compute_spatial_relationship, compute_statistical_summary
from core.transformers import transform_data_structure

def _initialize_processing_state(config: Dict[str, Any]) -> Dict[str, Any]:
    validation_results = create_validation_context(config)
    state = {'config': config, 'validated': all(validation_results.values()), 'validation_details': validation_results, 'step_count': 0}
    return state

def _execute_transformation_phase(raw_input: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    if not state.get('validated', False):
        return raw_input
    transformed = transform_data_structure(raw_input)
    state['step_count'] += 1
    return transformed

def _execute_computation_phase(transformed_data: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    if 'points' in transformed_data and isinstance(transformed_data['points'], list):
        points = transformed_data['points']
        if len(points) >= 2:
            point_a = tuple(points[0].get('coords', [0.0, 0.0]))
            point_b = tuple(points[1].get('coords', [0.0, 0.0]))
            scale = state.get('config', {}).get('scale', 1.0)
            spatial_result = compute_spatial_relationship(point_a, point_b, scale)
            transformed_data['spatial'] = spatial_result
    if 'data_points' in transformed_data:
        summary = compute_statistical_summary(transformed_data['data_points'])
        transformed_data['statistics'] = summary
    state['step_count'] += 1
    return transformed_data

def process_data_pipeline(input_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    state = _initialize_processing_state(config)
    transformed = _execute_transformation_phase(input_data, state)
    result = _execute_computation_phase(transformed, state)
    result['processing_metadata'] = {'steps_completed': state['step_count'], 'validation_passed': state['validated']}
    return result