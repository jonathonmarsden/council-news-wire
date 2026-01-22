import json
import os
from pathlib import Path
from urllib.parse import urlparse

def load_all_councils():
    """Load councils from all state config files."""
    root_dir = Path(os.getcwd())
    states_dir = root_dir / 'states'
    
    all_councils = []
    
    if not states_dir.exists():
        print(f"Error: States directory not found at {states_dir}")
        return []
        
    for state_path in states_dir.iterdir():
        if not state_path.is_dir() or state_path.name.startswith('.'):
            continue
            
        councils_file = state_path / 'councils.json'
        if councils_file.exists():
            try:
                with open(councils_file, 'r') as f:
                    data = json.load(f)
                    councils = data.get('councils', [])
                    # Enrich with state info
                    for c in councils:
                        c['_state'] = state_path.name.upper()
                    all_councils.extend(councils)
            except Exception as e:
                print(f"Error reading {councils_file}: {e}")
                
    return all_councils

def build_domain_map(councils):
    """Map unique domains to Council Names."""
    domain_map = {}
    
    for c in councils:
        url = c.get('news_url')
        name = c.get('name')
        
        if not url or not name:
            continue
            
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith('www.'):
                domain = domain[4:]
                
            # Store map
            domain_map[domain] = name
            
            # --- OVERRIDES for known cloud hosts ---
            if domain == 'townsville.qld.gov.au':
                domain_map['tcc-search.funnelback.squiz.cloud'] = name
            # ---------------------------------------
            
        except:
            continue
            
    return domain_map

def main():
    councils = load_all_councils()
    print(f"Loaded {len(councils)} council configs.")
    
    domain_map = build_domain_map(councils)
    print(f"Mapped {len(domain_map)} unique domains.")
    
    # Save the map for the fixer script to use
    with open('scripts/council_domain_map.json', 'w') as f:
        json.dump(domain_map, f, indent=2)
        
    print("Saved domain map to scripts/council_domain_map.json")
    
    # Test a few
    print("\nSample lookups:")
    samples = ['albany.wa.gov.au', 'darwin.nt.gov.au', 'townsville.qld.gov.au']
    for s in samples:
        print(f"  {s}: {domain_map.get(s, 'NOT FOUND')}")

if __name__ == "__main__":
    main()
