import json

FILE_PATH = "states/wa/councils.json"

TARGETS = [
    "bassendean", 
    "beverley", 
    "bruce-rock", 
    "cunderdin", 
    "derby-west-kimberley", 
    "exmouth", 
    "kalgoorlie-boulder", 
    "kellerberrin", 
    "koorda", 
    "menzies", 
    "mukinbudin", 
    "mundaring", 
    "nedlands"
]

def update_councils():
    with open(FILE_PATH, 'r') as f:
        data = json.load(f)

    updated_count = 0
    for council in data['councils']:
        if council['id'] in TARGETS:
            print(f"Updating {council['id']}...")
            council['scraper'] = "curl_scraper"
            council['item_selector'] = ".module-list .row"
            council['title_selector'] = "span.h4"
            council['date_selector'] = "span.h5"
            council['link_selector'] = "a.btn"
            council['use_curl'] = True
            council['enabled'] = True
            
            # Remove disabled reasons and old notes if they conflict
            if 'disabled_reason' in council:
                del council['disabled_reason']
            
            updated_count += 1

    with open(FILE_PATH, 'w') as f:
        json.dump(data, f, indent=4)
        
    print(f"✅ Successfully enabled and updated {updated_count} councils in WA.")

if __name__ == "__main__":
    update_councils()
