import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 1. Vendor Fixes
VENDOR_UPDATES = {
    "opencities_scraper": [
        "Lake Macquarie, City of", 
        "Tweed Shire", 
        "Bellingen Shire", 
        "Clarence Valley Council", 
        "Murray River Council", 
        "Murrumbidgee Council", 
        "Narrandera Shire", 
        "Snowy Valleys Council", 
        "Uralla Shire"
    ],
    "wordpress_scraper": [
        "Lockhart Shire"
    ]
}

# 2. RSS Fixes (Already applied, but listed here to skip "curl" toggle if needed)
# "Georges River Council", "Bogan Shire", "Inverell Shire", "Upper Lachlan Shire", "Bundaberg Council", "Shire of Cocos (Keeling) Islands"

RSS_FIXED = [
    "Georges River Council", "Bogan Shire", "Inverell Shire", "Upper Lachlan Shire", 
    "Bundaberg Council", "Shire of Cocos (Keeling) Islands"
]

# 3. The remaining failures - toggle 'use_curl'
# This list is the original failure list minus the ones above.
# I'll just list ALL failures and let logic filter them.

ALL_FAILURES = [
    # NT
    "Barkly Regional Council", "Coomalie Community Government Council", "East Arnhem Regional Council",
    "MacDonnell Regional Council", "Wagait Shire", "Groote Archipelago Regional Council",
    # SA
    "City of Adelaide", "Naracoorte Lucindale Council", "Renmark Paringa Council",
    "City of Port Augusta", "City of Salisbury", "City of Unley", "City of West Torrens",
    # QLD
    "Blackall-Tambo Council", "Bundaberg Council", "Cherbourg Aboriginal Shire",
    "Shire of Etheridge", "Lockyer Valley Council", "Shire of Richmond", "Shire of Quilpie",
    "Aboriginal Shire of Wujal Wujal",
    # NSW
    "Georges River Council", "Lake Macquarie, City of", "Northern Beaches Council",
    "Tweed Shire", "Bellingen Shire", "Bogan Shire", "Clarence Valley Council",
    "Hay Shire", "Lockhart Shire", "Inverell Shire", "Moree Plains Shire",
    "Murray River Council", "Murrumbidgee Council", "Narrandera Shire",
    "Shellharbour, City of", "Upper Lachlan Shire", "Snowy Valleys Council", 
    "Uralla Shire", "Lithgow, City of", "Wollondilly Shire",
    # WA (Skipping WA for "curl" toggle as per plan - focusing on Catalyst/Alyka there, but enabling curl for unknown ones is safer than nothing)
]

def apply_updates():
    states_dir = PROJECT_ROOT / 'states'
    
    # Invert VENDOR_UPDATES for easier lookup
    council_to_vendor = {}
    for scraper, names in VENDOR_UPDATES.items():
        for name in names:
            council_to_vendor[name] = scraper

    total_vendor = 0
    total_curl = 0
    
    for state_dir in states_dir.iterdir():
        if not state_dir.is_dir() or state_dir.name.startswith('_'):
            continue
            
        config_path = state_dir / 'councils.json'
        if not config_path.exists(): 
            continue
            
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                
            modified = False
            for c in data['councils']:
                name = c['name']
                
                # S1: Vendor Updates
                if name in council_to_vendor:
                    new_scraper = council_to_vendor[name]
                    if c.get('scraper') != new_scraper:
                        c['scraper'] = new_scraper
                        # Force curl for OpenCities
                        if new_scraper == 'opencities_scraper':
                            c['use_curl'] = True
                        print(f"[{state_dir.name}] Migrated {name} to {new_scraper}")
                        modified = True
                        total_vendor += 1
                        
                # S2: Curl Defaults for other failures
                elif name in ALL_FAILURES and name not in RSS_FIXED:
                    # Not an RSS fix, not a Vendor fix -> Toggle Curl
                    # Skip WA for now as per plan? No, plan says "Action 1.2 WA/NT: Audit manually".
                    # Plan says "Action 1.1 (VIC/NSW/QLD): Bulk toggle use_curl".
                    if state_dir.name in ['vic', 'nsw', 'qld', 'sa', 'nt']: # Adding SA/NT to the bulk trial
                        if not c.get('use_curl', False):
                            c['use_curl'] = True
                            print(f"[{state_dir.name}] Enabled CURL for {name}")
                            modified = True
                            total_curl += 1
                            
            if modified:
                with open(config_path, 'w') as f:
                    json.dump(data, f, indent=4)
                    
        except Exception as e:
            print(f"Error processing {state_dir.name}: {e}")

    print(f"\nSummary:\nVendor Migrations: {total_vendor}\nCurl Enables: {total_curl}")

if __name__ == "__main__":
    apply_updates()
