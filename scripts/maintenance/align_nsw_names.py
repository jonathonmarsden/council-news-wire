
import json
import os
import difflib

# Source: https://lgnsw.org.au/Public/public/NSW-Councils/NSW-Council-Links.aspx (23 Jan 2026)
OFFICIAL_NAMES = [
    "Albury City Council", "Armidale Regional Council", "Ballina Shire Council", "Balranald Shire Council", 
    "Bathurst Regional Council", "Bayside Council", "Bega Valley Shire Council", "Bellingen Shire Council", 
    "Berrigan Shire Council", "Blacktown City Council", "Bland Shire Council", "Blayney Shire Council", 
    "Blue Mountains City Council", "Bogan Shire Council", "Bourke Shire Council", "Brewarrina Shire Council", 
    "Broken Hill City Council", "Burwood Council", "Byron Shire Council", "Cabonne Council", "Camden Council", 
    "Campbelltown City Council", "Carrathool Shire Council", "Central Coast Council", "Central Darling Shire Council", 
    "Cessnock City Council", "City of Canada Bay Council", "City of Canterbury Bankstown", 
    "City of Parramatta Council", "City of Ryde", "City of Sydney", "Clarence Valley Council", 
    "Cobar Shire Council", "Coffs Harbour City Council", "Coolamon Shire Council", "Coonamble Shire Council", 
    "Cootamundra-Gundagai Council", "Cowra Council", "Cumberland City Council", "Dubbo Regional Council", 
    "Dungog Shire Council", "Edward River Council", "Eurobodalla Shire Council", "Fairfield City Council", 
    "Federation Council", "Forbes Shire Council", "Georges River Council", "Gilgandra Shire Council", 
    "Glen Innes Severn Council", "Goulburn Mulwaree Council", "Greater Hume Shire Council", "Griffith City Council", 
    "Gunnedah Shire Council", "Gwydir Shire Council", "Hawkesbury City Council", "Hay Shire Council", 
    "Hilltops Council", "Hornsby Shire Council", "Hunter's Hill Council", "Inner West Council", 
    "Inverell Shire Council", "Junee Shire Council", "Kempsey Shire Council", "Kiama Municipal Council", 
    "Ku-ring-gai Council", "Kyogle Council", "Lachlan Shire Council", "Lake Macquarie City Council", 
    "Lane Cove Council", "Leeton Shire Council", "Lismore City Council", "Lithgow City Council", 
    "Liverpool City Council", "Liverpool Plains Shire Council", "Lockhart Shire Council", "Maitland City Council", 
    "MidCoast Council", "Mid-Western Regional Council", "Moree Plains Shire Council", "Mosman Municipal Council", 
    "Murray River Council", "Murrumbidgee Council", "Muswellbrook Shire Council", "Nambucca Valley Council", 
    "Narrabri Shire Council", "Narrandera Shire Council", "Narromine Shire Council", "City of Newcastle", 
    "North Sydney Council", "Northern Beaches Council", "Oberon Council", "Orange City Council", 
    "Parkes Shire Council", "Penrith City Council", "Port Macquarie-Hastings Council", "Port Stephens Council", 
    "Queanbeyan-Palerang Regional Council", "Randwick City Council", "Richmond Valley Council", 
    "Shellharbour City Council", "Shoalhaven City Council", "Singleton Council", "Snowy Monaro Regional Council", 
    "Snowy Valleys Council", "Strathfield Council", "Sutherland Shire Council", "Tamworth Regional Council", 
    "Temora Shire Council", "Tenterfield Shire Council", "The Hills Shire Council", "Tweed Shire Council", 
    "Upper Lachlan Shire Council", "Upper Hunter Shire Council", "Uralla Shire Council", "Wagga Wagga City Council", 
    "Walcha Council", "Walgett Shire Council", "Warren Shire Council", "Warrumbungle Shire Council", 
    "Waverley Council", "Weddin Shire Council", "Wentworth Shire Council", "Willoughby City Council", 
    "Wingecarribee Shire Council", "Wollondilly Shire Council", "Wollongong City Council", 
    "Woollahra Municipal Council", "Yass Valley Council"
]

def align_nsw_names():
    filepath = 'states/nsw/councils.json'
    
    with open(filepath, 'r') as f:
        data = json.load(f)
        councils = data['councils']
        
    changes = []
    
    # Create lookup map for loose matching
    # Key: Simplified lower case name (removed 'shire', 'council', 'city', 'of')
    # Value: Official Name
    
    def simplify(name):
        return name.lower().replace('council', '').replace('shire', '').replace('city', '').replace('of', '').replace('-', ' ').replace(',', '').strip()

    official_map = {simplify(name): name for name in OFFICIAL_NAMES}
    
    # Manual overwrites for tricky ones
    official_map['canterbury bankstown'] = "City of Canterbury Bankstown"
    official_map['canada bay'] = "City of Canada Bay Council"
    official_map['sydney'] = "City of Sydney"
    official_map['parramatta'] = "City of Parramatta Council"
    official_map['newcastle'] = "City of Newcastle"
    official_map['ryde'] = "City of Ryde"
    official_map['hunters hill'] = "Hunter's Hill Council"
    official_map['upper hunter'] = "Upper Hunter Shire Council"
    official_map['greater hume'] = "Greater Hume Shire Council"
    official_map['mosman'] = "Mosman Municipal Council"
    official_map['queanbeyan–palerang regional'] = "Queanbeyan-Palerang Regional Council" # Handle en-dash
    
    for council in councils:
        current_name = council['name']
        simple = simplify(current_name)
        
        match = official_map.get(simple)
        
        # Try finding standard match if exact simple match fail
        if not match:
             # Try containing match
             for k, v in official_map.items():
                 if k in simple or simple in k:
                     # Check high similarity
                     if difflib.SequenceMatcher(None, k, simple).ratio() > 0.8:
                         match = v
                         break
        
        if match and match != current_name:
            council['name'] = match
            changes.append(f"{current_name} -> {match}")
        elif not match:
            print(f"WARNING: Could not find official match for '{current_name}' (Simplified: '{simple}')")
            
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)
        
    print(f"\nAligned {len(changes)} council names to LGNSW standard.")
    for change in changes:
        print(change)

if __name__ == "__main__":
    align_nsw_names()
