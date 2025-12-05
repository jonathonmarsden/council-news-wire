import json
import os
import sys

def check_councils_json():
    states_dir = 'states'
    has_errors = False
    
    for state in os.listdir(states_dir):
        state_path = os.path.join(states_dir, state)
        if not os.path.isdir(state_path):
            continue
            
        json_path = os.path.join(state_path, 'councils.json')
        if not os.path.exists(json_path):
            print(f"WARNING: No councils.json found for state: {state}")
            continue
            
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
                
            if not isinstance(data, dict):
                print(f"ERROR: {json_path} root is not a dictionary")
                has_errors = True
                continue
                
            if 'councils' not in data:
                print(f"ERROR: {json_path} missing 'councils' key")
                has_errors = True
                continue
                
            councils = data['councils']
            if not isinstance(councils, list):
                print(f"ERROR: {json_path} 'councils' is not a list")
                has_errors = True
                continue
                
            enabled_count = sum(1 for c in councils if c.get('enabled', False))
            total_count = len(councils)
            print(f"State {state}: {enabled_count}/{total_count} councils enabled. Valid JSON.")
            
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in {json_path}: {e}")
            has_errors = True
        except Exception as e:
            print(f"ERROR: processing {json_path}: {e}")
            has_errors = True

    if has_errors:
        sys.exit(1)
    else:
        print("\nAll councils.json files are valid.")

if __name__ == "__main__":
    check_councils_json()
