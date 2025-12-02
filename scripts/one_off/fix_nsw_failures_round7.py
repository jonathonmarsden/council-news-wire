import json
import os

def fix_nsw_councils():
    config_path = 'states/nsw/councils.json'
    
    with open(config_path, 'r') as f:
        data = json.load(f)
    
    councils_list = data.get('councils', [])
    
    # List of councils getting 403 Forbidden that need curl_scraper
    councils_to_switch_to_curl = [
        "Berrigan Shire Council",
        "Bland Shire Council",
        "Broken Hill City Council",
        "Central Darling Shire Council",
        "Clarence Valley Council",
        "Cowra Council",
        "Edward River Council",
        "Federation Council",
        "Glen Innes Severn Council",
        "Goulburn Mulwaree Council",
        "Greater Hume Council",
        "Liverpool Plains Shire Council",
        "Murray River Council",
        "Nambucca Valley Council",
        "Snowy Valleys Council",
        "Wingecarribee Shire Council",
        "Yass Valley Council"
    ]
    
    updated_count = 0
    
    for council in councils_list:
        if council['name'] in councils_to_switch_to_curl:
            print(f"Switching {council['name']} to curl_scraper...")
            council['scraper'] = 'curl_scraper'
            updated_count += 1
            
    with open(config_path, 'w') as f:
        json.dump(data, f, indent=4)
        
    print(f"\nUpdated {updated_count} councils to use curl_scraper.")

if __name__ == "__main__":
    fix_nsw_councils()
