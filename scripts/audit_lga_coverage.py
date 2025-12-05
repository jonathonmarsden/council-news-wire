import csv
import json
import os
import re
from pathlib import Path

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
CSV_PATH = PROJECT_ROOT / "_archived_old_code" / "LGA_2025_AUST.csv"
STATES_DIR = PROJECT_ROOT / "states"

# State mapping
STATE_MAP = {
    "New South Wales": "nsw",
    "Victoria": "vic",
    "Queensland": "qld",
    "South Australia": "sa",
    "Western Australia": "wa",
    "Tasmania": "tas",
    "Northern Territory": "nt",
    "Australian Capital Territory": "act",
    "Other Territories": "other" 
}

# Suffixes to remove for normalization
SUFFIXES = [
    " city council", " shire council", " regional council", " district council", 
    " council", " municipality", " town council", " aboriginal shire council",
    " shire", " city", " rural city"
]

# Prefixes to remove
PREFIXES = [
    "city of ", "shire of ", "town of ", "district council of ", 
    "municipality of ", "regional council of ", "corporation of the city of ",
    "corporation of the town of "
]

def normalize_name(name):
    name = name.lower().strip()
    
    # Remove prefixes
    for prefix in PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix):].strip()
            break

    # Remove suffixes - iterate and remove the longest matching suffix first to avoid partial matches
    # Sort suffixes by length descending to handle "City Council" before "Council"
    sorted_suffixes = sorted(SUFFIXES, key=len, reverse=True)
    
    clean_name = name
    for suffix in sorted_suffixes:
        if clean_name.endswith(suffix):
            clean_name = clean_name[:-len(suffix)].strip()
            break # Only remove one suffix type
            
    # Remove hyphens and extra spaces for comparison
    clean_name = clean_name.replace("-", " ").replace("  ", " ")
    return clean_name

def load_csv_lgas():
    lgas = {} # state_code -> set of normalized names
    
    if not CSV_PATH.exists():
        print(f"Error: CSV file not found at {CSV_PATH}")
        return {}

    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, skipinitialspace=True)
        for row in reader:
            lga_name = row['LGA_NAME'].strip()
            state_name = row['STATE_NAME'].strip()
            
            state_code = STATE_MAP.get(state_name)
            if not state_code:
                # print(f"Warning: Unknown state '{state_name}' for LGA '{lga_name}'")
                continue
                
            if state_code not in lgas:
                lgas[state_code] = []
            
            lgas[state_code].append({
                "original": lga_name,
                "normalized": normalize_name(lga_name)
            })
    return lgas

def load_project_councils():
    councils = {} # state_code -> set of normalized names
    
    for state_dir in STATES_DIR.iterdir():
        if state_dir.is_dir():
            state_code = state_dir.name
            config_path = state_dir / "councils.json"
            
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    councils[state_code] = []
                    for council in data.get('councils', []):
                        name = council.get('name', '')
                        councils[state_code].append({
                            "original": name,
                            "normalized": normalize_name(name)
                        })
                except Exception as e:
                    print(f"Error reading {config_path}: {e}")
                    
    return councils

def main():
    print("=== LGA Coverage Audit ===")
    print(f"Reference: {CSV_PATH}")
    
    csv_lgas = load_csv_lgas()
    project_councils = load_project_councils()
    
    total_missing = 0
    total_lgas = 0
    
    for state_name, state_code in STATE_MAP.items():
        if state_code == "other": continue # Skip other territories for now if not in project structure
        
        expected = csv_lgas.get(state_code, [])
        actual = project_councils.get(state_code, [])
        
        actual_normalized = {c['normalized'] for c in actual}
        
        missing = []
        for lga in expected:
            if lga['normalized'] not in actual_normalized:
                missing.append(lga['original'])
        
        # Find unexpected (names in project that didn't match CSV)
        expected_normalized = {c['normalized'] for c in expected}
        unexpected = []
        for council in actual:
            if council['normalized'] not in expected_normalized:
                unexpected.append(council['original'])

        total_lgas += len(expected)
        total_missing += len(missing)
        
        print(f"\nState: {state_name} ({state_code.upper()})")
        print(f"Expected: {len(expected)}, Found: {len(actual)}")
        
        if missing:
            print(f"Missing from Project ({len(missing)}):")
            for m in sorted(missing):
                print(f"  - {m}")
        
        if unexpected:
            print(f"Found in Project but not matched ({len(unexpected)}):")
            for u in sorted(unexpected):
                print(f"  + {u}")
        
        if not missing and not unexpected:
            print("  Perfect match!")

    print("\n=== Summary ===")
    print(f"Total LGAs in CSV: {total_lgas}")
    print(f"Total Missing in Project: {total_missing}")
    print(f"Coverage: {((total_lgas - total_missing) / total_lgas * 100):.1f}%")

if __name__ == "__main__":
    main()
