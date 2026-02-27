from typing import List, Dict, Tuple, Any
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.transformers import transform_coordinate_system, aggregate_metrics, transform_data_structure
from core.validators import validate_numeric_range

def _compute_euclidean_distance(pt1: Dict[str, float], pt2: Dict[str, float]) -> float:
    dx = pt1.get('x', 0.0) - pt2.get('x', 0.0)
    dy = pt1.get('y', 0.0) - pt2.get('y', 0.0)
    return (dx * dx + dy * dy) ** 0.5

def _calculate_weighted_average(values: List[float], weights: List[float]) -> float:
    if len(values) != len(weights) or not values:
        return 0.0
    metrics = aggregate_metrics(values)
    total_weight = sum(weights)
    if total_weight == 0:
        return metrics['avg']
    weighted_sum = sum((v * w for v, w in zip(values, weights)))
    return weighted_sum / total_weight

def compute_spatial_relationship(point_a: Tuple[float, float], point_b: Tuple[float, float], scale: float=1.0) -> Dict[str, float]:
    coord_a = transform_coordinate_system(point_a[0], point_a[1], scale)
    coord_b = transform_coordinate_system(point_b[0], point_b[1], scale)
    distance = _compute_euclidean_distance(coord_a, coord_b)
    return {'point_a': coord_a, 'point_b': coord_b, 'distance': distance}

def compute_statistical_summary(data_points: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not data_points:
        return {'count': 0, 'metrics': {}}
    transformed_points = [transform_data_structure(dp) for dp in data_points]
    numeric_values = []
    for point in transformed_points:
        for value in point.values():
            if isinstance(value, (int, float)):
                numeric_values.append(float(value))
    metrics = aggregate_metrics(numeric_values)
    weights = [1.0] * len(numeric_values)
    weighted_avg = _calculate_weighted_average(numeric_values, weights)
    return {'count': len(data_points), 'metrics': metrics, 'weighted_average': weighted_avg}