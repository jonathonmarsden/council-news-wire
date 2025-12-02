#!/usr/bin/env python3
"""
Validate council configuration files.
Checks for required fields and valid JSON structure.
"""

import json
import os
import sys
from typing import List, Dict

REQUIRED_FIELDS = ['id', 'name', 'news_url', 'scraper']
OPTIONAL_FIELDS = ['enabled', 'proxy', 'use_rotating_proxy', 'selectors']

def validate_council(council: Dict, index: int, filename: str) -> List[str]:
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in council:
            errors.append(f"Council #{index} ({council.get('name', 'Unknown')}) missing required field: '{field}'")
            
    if 'id' in council and ' ' in council['id']:
        errors.append(f"Council #{index} ({council.get('name', 'Unknown')}) id '{council['id']}' contains spaces (should be kebab-case)")
        
    return errors

def validate_file(filepath: str) -> List[str]:
    errors = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if 'councils' not in data:
            errors.append(f"{filepath}: Missing top-level 'councils' list")
            return errors
            
        councils = data['councils']
        if not isinstance(councils, list):
            errors.append(f"{filepath}: 'councils' must be a list")
            return errors
            
        seen_ids = set()
        for i, council in enumerate(councils):
            council_errors = validate_council(council, i, filepath)
            errors.extend(council_errors)
            
            if 'id' in council:
                if council['id'] in seen_ids:
                    errors.append(f"{filepath}: Duplicate council ID found: '{council['id']}'")
                seen_ids.add(council['id'])
                
    except json.JSONDecodeError as e:
        errors.append(f"{filepath}: Invalid JSON - {e}")
    except Exception as e:
        errors.append(f"{filepath}: Error reading file - {e}")
        
    return errors

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    states_dir = os.path.join(root_dir, 'states')
    
    all_errors = []
    
    print(f"Scanning {states_dir}...")
    
    for state in os.listdir(states_dir):
        state_path = os.path.join(states_dir, state)
        if os.path.isdir(state_path):
            config_path = os.path.join(state_path, 'councils.json')
            if os.path.exists(config_path):
                print(f"Validating {state}...")
                errors = validate_file(config_path)
                all_errors.extend(errors)
    
    if all_errors:
        print("\n❌ Validation Failed:")
        for error in all_errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("\n✅ All configurations valid.")
        sys.exit(0)

if __name__ == "__main__":
    main()
