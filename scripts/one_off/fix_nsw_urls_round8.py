import json
import os

def fix_nsw_urls():
    config_path = 'states/nsw/councils.json'
    
    with open(config_path, 'r') as f:
        data = json.load(f)
    
    councils_list = data.get('councils', [])
    
    updates = {
        "Bourke Shire Council": "https://bourke.nsw.gov.au/council/media-release/",
        "Coonamble Shire Council": "https://www.coonambleshire.nsw.gov.au/council/news",
        "Kyogle Council": "https://www.kyogle.nsw.gov.au/council-engagement/jobs-news-community-feedback/",
        "Moree Plains Shire Council": "https://www.mpsc.nsw.gov.au/hot-topics/media-releases",
        "Muswellbrook Shire Council": "https://www.muswellbrook.nsw.gov.au/latest-news/",
        "Narromine Shire Council": "https://www.narromine.nsw.gov.au/council/media-releases",
        "Tenterfield Shire Council": "https://www.tenterfield.nsw.gov.au/news-events/media-releases",
        "Warren Shire Council": "https://www.warren.nsw.gov.au/council/media-releases"
    }
    
    updated_count = 0
    
    for council in councils_list:
        if council['name'] in updates:
            print(f"Updating URL for {council['name']}...")
            council['news_url'] = updates[council['name']]
            # Also switch to curl_scraper to be safe, as many NSW sites are strict
            council['scraper'] = 'curl_scraper'
            updated_count += 1
            
    with open(config_path, 'w') as f:
        json.dump(data, f, indent=4)
        
    print(f"\nUpdated {updated_count} councils with new URLs and curl_scraper.")

if __name__ == "__main__":
    fix_nsw_urls()
