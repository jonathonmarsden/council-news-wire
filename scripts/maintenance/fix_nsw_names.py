
import json
import os

def fix_nsw_names():
    filepath = 'states/nsw/councils.json'
    
    with open(filepath, 'r') as f:
        data = json.load(f)
        councils = data['councils']
    
    changes = []
    
    for council in councils:
        old_name = council['name']
        new_name = old_name
        
        if ", City of" in old_name:
            # "Orange, City of" -> "Orange City Council"
            base = old_name.replace(", City of", "").strip()
            new_name = f"{base} City Council"
            
        elif ", Municipality of" in old_name:
            base = old_name.replace(", Municipality of", "").strip()
            cid = council['id']
            
            if "municipal-council" in cid:
                new_name = f"{base} Municipal Council"
            else:
                new_name = f"{base} Council"
                
        if new_name != old_name:
            council['name'] = new_name
            changes.append(f"{old_name} -> {new_name}")
            
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)
        
    print(f"Fixed {len(changes)} names:")
    for change in changes:
        print(change)

if __name__ == "__main__":
    fix_nsw_names()
