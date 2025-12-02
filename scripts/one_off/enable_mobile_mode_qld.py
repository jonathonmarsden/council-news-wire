import json
import os

def enable_mobile_mode():
    file_path = 'states/qld/councils.json'
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    targets = ['barcoo', 'hinchinbrook', 'lockyer-valley']
    count = 0
    
    for council in data['councils']:
        if council['id'] in targets:
            council['mobile_mode'] = True
            print(f"Enabled mobile_mode for {council['name']}")
            count += 1
            
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)
        
    print(f"Updated {count} councils.")

if __name__ == "__main__":
    enable_mobile_mode()
