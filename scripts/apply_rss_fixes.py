import json
import os

def load_rss_discoveries():
    discoveries = []
    if not os.path.exists("rss_discoveries.txt"):
        return discoveries
        
    with open("rss_discoveries.txt", "r") as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) == 3:
                discoveries.append({
                    "state": parts[0],
                    "id": parts[1],
                    "rss_url": parts[2]
                })
    return discoveries

def apply_fixes(discoveries):
    # Group by state to minimize file I/O
    by_state = {}
    for d in discoveries:
        if d["state"] not in by_state:
            by_state[d["state"]] = []
        by_state[d["state"]].append(d)
        
    for state, items in by_state.items():
        filepath = f"states/{state}/councils.json"
        if not os.path.exists(filepath):
            print(f"Warning: {filepath} not found.")
            continue
            
        print(f"Updating {state} with {len(items)} RSS fixes...")
        
        with open(filepath, "r") as f:
            data = json.load(f)
            
        councils = data.get("councils", [])
        updated_count = 0
        
        for item in items:
            council_id = item["id"]
            rss_url = item["rss_url"]
            
            found = False
            for council in councils:
                if council["id"] == council_id:
                    print(f"  - Updating {council_id} -> {rss_url}")
                    council["scraper"] = "rss_scraper"
                    council["news_url"] = rss_url
                    council["enabled"] = True
                    # Clean up selector fields if they exist, as RSS doesn't need them
                    keys_to_remove = ["item_selector", "title_selector", "date_selector", "link_selector", "use_curl"]
                    for k in keys_to_remove:
                        if k in council:
                            del council[k]
                    found = True
                    updated_count += 1
                    break
            
            if not found:
                print(f"  - Warning: Council {council_id} not found in {filepath}")
                
        if updated_count > 0:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            print(f"Saved {filepath}")

def main():
    discoveries = load_rss_discoveries()
    if not discoveries:
        print("No discoveries found in rss_discoveries.txt")
        return
        
    print(f"Applying {len(discoveries)} RSS fixes...")
    apply_fixes(discoveries)
    print("Done.")

if __name__ == "__main__":
    main()
