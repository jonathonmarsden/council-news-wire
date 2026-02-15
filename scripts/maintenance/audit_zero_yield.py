
import json
import os
import sys
from pathlib import Path
from sqlalchemy import select, func

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from core.database import Database
from core.models import Article

def audit_zero_yield():
    print("Starting Zero-Yield Audit...")
    
    # 1. Load all enabled councils
    enabled_councils = []
    states_dir = project_root / 'states'
    
    for state_dir in states_dir.iterdir():
        if not state_dir.is_dir() or state_dir.name.startswith('.'):
            continue
            
        config_path = state_dir / 'councils.json'
        if not config_path.exists():
            continue
            
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                for council in data.get('councils', []):
                    if council.get('enabled', False):
                        enabled_councils.append({
                            'id': council['id'],
                            'name': council['name'],
                            'state': state_dir.name,
                            'url': council.get('news_url', 'N/A')
                        })
        except Exception as e:
            print(f"Error reading {config_path}: {e}")

    print(f"Found {len(enabled_councils)} enabled councils.")

    # 2. Check database
    db = Database()
    session = db.get_session()
    
    zero_yield_councils = []
    
    for council in enabled_councils:
        count_stmt = select(func.count(Article.id)).where(Article.council_id == council['id'])
        count = session.execute(count_stmt).scalar() or 0
        
        if count == 0:
            zero_yield_councils.append(council)

    session.close()

    # 3. Report
    print(f"\nFound {len(zero_yield_councils)} enabled councils with 0 articles in DB:")
    print("-" * 80)
    print(f"{'State':<6} | {'ID':<30} | {'Name':<30} | {'URL'}")
    print("-" * 80)
    
    for c in sorted(zero_yield_councils, key=lambda x: (x['state'], x['id'])):
        print(f"{c['state']:<6} | {c['id']:<30} | {c['name']:<30} | {c['url']}")

if __name__ == "__main__":
    audit_zero_yield()
