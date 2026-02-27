#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from processors.pipeline import process_data_pipeline
from processors.exporters import export_processing_results
from core.validators import validate_numeric_range

def main():
    input_data = {'points': [{'coords': [1.0, 2.0], 'label': 'point_a'}, {'coords': [4.0, 6.0], 'label': 'point_b'}], 'data_points': [{'value': 10.5, 'category': 'A'}, {'value': 20.3, 'category': 'B'}, {'value': 15.7, 'category': 'A'}]}
    config = {'scale': 1.5, 'precision': 2, 'output_format': 'detailed'}
    if validate_numeric_range(config['scale'], 0.1, 10.0):
        processed = process_data_pipeline(input_data, config)
        output = export_processing_results(processed, format_type=config.get('output_format', 'summary'))
        print('=== Processing Complete ===')
        print(output)
    else:
        print('Invalid configuration')
if __name__ == '__main__':
    main()