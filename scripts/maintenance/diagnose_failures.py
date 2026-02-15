import json
import os
import sys
import glob
import concurrent.futures
import subprocess
import time
from datetime import datetime
from sqlalchemy import select

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.database import Database
from core.models import Article
from core.scrapers import ScraperFactory

def get_never_seen_councils(target_ids=None):
    # Load all configs
    councils = []
    state_files = glob.glob("states/*/councils.json")
    for fpath in state_files:
        try:
            with open(fpath, 'r') as f:
                data = json.load(f)
                for c in data.get('councils', []):
                    if c.get('enabled', True):
                        c['state'] = os.path.basename(os.path.dirname(fpath))
                        if target_ids:
                            if c['id'] in target_ids:
                                councils.append(c)
                        else:
                            councils.append(c)
        except Exception as e:
            print(f"Error loading {fpath}: {e}")

    if target_ids:
        return councils

    # Check DB for success history
    db = Database()
    seen_ids = set()
    # We can check the 'scraper_logs' table if it exists, or just 'articles'
    # But 'articles' only tells us if we found something.
    # Let's assume if it's not in 'articles', it's "Never Seen" or "Empty"
    # For diagnosis, we want to run anything that hasn't posted recently.
    
    # Actually, let's just use the list from the previous health check output if possible, 
    # or just run for all and filter by "last_success" if I had that metric.
    # Since I don't have easy access to "last_success" without querying the DB complexly,
    # I will try to run a quick check on a subset.
    
    # Let's filter for councils that have 0 articles in the DB.
    with db.get_session() as session:
        rows = session.execute(select(Article.council_id).distinct()).all()
        seen_ids = {row[0] for row in rows}
        
    never_seen = [c for c in councils if c['id'] not in seen_ids]
    return never_seen

def main():
    target_ids = sys.argv[1:] if len(sys.argv) > 1 else None
    councils = get_never_seen_councils(target_ids)
    print(f"Diagnosing {len(councils)} councils...")

def test_council(council):
    """Run a dry-run scrape for a single council."""
    try:
        # We use a subprocess to isolate the run and capture output/errors easily
        # Or we can use the ScraperFactory directly.
        # Using Factory is faster.
        
        start_time = time.time()
        scraper = ScraperFactory.create_scraper(council)
        articles = scraper.scrape()
        duration = time.time() - start_time
        
        if articles:
            return {
                'id': council['id'],
                'status': 'SUCCESS',
                'count': len(articles),
                'duration': duration,
                'error': None
            }
        else:
            return {
                'id': council['id'],
                'status': 'EMPTY',
                'count': 0,
                'duration': duration,
                'error': None
            }
    except Exception as e:
        return {
            'id': council['id'],
            'status': 'ERROR',
            'count': 0,
            'duration': 0,
            'error': str(e)
        }

def main():
    never_seen = get_never_seen_councils()
    print(f"Found {len(never_seen)} councils with no history.")
    
    # Limit for testing
    # never_seen = never_seen[:20] 
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_council = {executor.submit(test_council, c): c for c in never_seen}
        for future in concurrent.futures.as_completed(future_to_council):
            council = future_to_council[future]
            try:
                data = future.result()
                results.append(data)
                print(f"[{data['status']}] {council['id']}: {data['error'] or data['count']} items")
            except Exception as exc:
                print(f"[CRASH] {council['id']}: {exc}")

    # Analyze results
    print("\n=== Diagnosis Report ===")
    success = [r for r in results if r['status'] == 'SUCCESS']
    empty = [r for r in results if r['status'] == 'EMPTY']
    errors = [r for r in results if r['status'] == 'ERROR']
    
    print(f"Success: {len(success)}")
    print(f"Empty: {len(empty)}")
    print(f"Errors: {len(errors)}")
    
    # Group errors
    error_types = {}
    for r in errors:
        msg = r['error']
        # Simplify error message
        if "403" in msg: cat = "403 Forbidden"
        elif "404" in msg: cat = "404 Not Found"
        elif "Connection" in msg: cat = "Connection Error"
        elif "Selector" in msg or "NoneType" in msg: cat = "Selector/Parsing Error"
        else: cat = "Other"
        
        if cat not in error_types: error_types[cat] = []
        error_types[cat].append(r['id'])
        
    for cat, ids in error_types.items():
        print(f"\n{cat} ({len(ids)}):")
        print(", ".join(ids[:10]) + ("..." if len(ids) > 10 else ""))

if __name__ == "__main__":
    main()
