import json
import os
import sys
import time
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Any
import traceback

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from core.scrapers import ScraperFactory
from dotenv import load_dotenv

load_dotenv()

REPORT_FILE = PROJECT_ROOT / "HEALTH_CHECK_REPORT_2026.md"

def load_all_councils() -> Dict[str, List[Dict]]:
    """Load all councils from all states."""
    all_councils = {}
    states_dir = PROJECT_ROOT / 'states'
    
    for state_dir in states_dir.iterdir():
        if not state_dir.is_dir() or state_dir.name.startswith('_'):
            continue
            
        state_code = state_dir.name
        councils_file = state_dir / 'councils.json'
        
        if councils_file.exists():
            try:
                with open(councils_file, 'r') as f:
                    data = json.load(f)
                    all_councils[state_code] = data.get('councils', [])
            except Exception as e:
                print(f"Error loading {state_code}: {e}")
                
    return all_councils

def check_council(council: Dict, state_code: str) -> Dict[str, Any]:
    """Run a health check on a single council."""
    result = {
        "council": council['name'],
        "state": state_code,
        "status": "fail",
        "articles_found": 0,
        "error": None,
        "duration": 0
    }
    
    start_time = time.time()
    try:
        scraper = ScraperFactory.create_scraper(council)
        # We assume scrapers have a .scrape() method returning list of articles
        # Even if they need a db, most accept None for dry runs if written well,
        # but let's check ScraperFactory.
        
        # Scrapers in this codebase usually are: scraper.extract_articles() or similar.
        # Let's verify commonly used interface in main.py -> scrape_single_council uses .scrape() if it's a BaseScraper?
        # Actually in main.py:
        # scraper = get_scraper(council, proxy=proxy)
        # new_articles = scraper.scrape()
        
        articles = scraper.scrape()
        result["articles_found"] = len(articles)
        result["status"] = "ok" if len(articles) > 0 else "warning_zero_articles"
        
    except Exception as e:
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
    finally:
        result["duration"] = time.time() - start_time
        
    return result

def generate_report(results: List[Dict]):
    """Generate a markdown report."""
    
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "ok")
    warnings = sum(1 for r in results if r["status"] == "warning_zero_articles")
    failed = sum(1 for r in results if r["status"] == "fail")
    
    with open(REPORT_FILE, 'w') as f:
        f.write("# Australian Council News Health Check Report\n\n")
        f.write(f"**Date:** {time.strftime('%Y-%m-%d')}\n")
        f.write(f"**Total Councils Checked:** {total}\n")
        f.write(f"**Healthy (Found Articles):** {passed} ({(passed/total)*100:.1f}%)\n")
        f.write(f"**Warning (Zero Articles):** {warnings} ({(warnings/total)*100:.1f}%)\n")
        f.write(f"**Failed (Exception):** {failed} ({(failed/total)*100:.1f}%)\n\n")
        
        f.write("## State Breakdown\n\n")
        f.write("| State | Total | Healthy | Warning | Failed | Success Rate |\n")
        f.write("|-------|-------|---------|---------|--------|--------------|\n")
        
        by_state = {}
        for r in results:
            s = r["state"]
            if s not in by_state:
                by_state[s] = {"total": 0, "ok": 0, "warn": 0, "fail": 0}
            by_state[s]["total"] += 1
            if r["status"] == "ok": by_state[s]["ok"] += 1
            if r["status"] == "warning_zero_articles": by_state[s]["warn"] += 1
            if r["status"] == "fail": by_state[s]["fail"] += 1

        for state, stats in sorted(by_state.items()):
            rate = (stats["ok"] / stats["total"]) * 100 if stats["total"] > 0 else 0
            f.write(f"| {state.upper()} | {stats['total']} | {stats['ok']} | {stats['warn']} | {stats['fail']} | {rate:.1f}% |\n")
            
        f.write("\n## Failures\n\n")
        for r in results:
            if r["status"] == "fail":
                f.write(f"- **{r['council']} ({r['state'].upper()})**: {r['error']}\n")

        f.write("\n## Zero Articles Found (Possible Issues)\n\n")
        for r in results:
            if r["status"] == "warning_zero_articles":
                f.write(f"- {r['council']} ({r['state'].upper()})\n")
                
    print(f"Report generated at {REPORT_FILE}")

def main():
    print("Starting Comprehensive Health Check...")
    all_councils = load_all_councils()
    
    tasks = []
    results = []
    
    # Flatten list for processing
    council_list = []
    for state, councils in all_councils.items():
        for council in councils:
            council_list.append((council, state))
            
    print(f"Found {len(council_list)} councils to check.")
    
    # Use concurrent futures to speed this up
    # Be careful not to DDoS, but most are different domains
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_council = {executor.submit(check_council, c, s): c['name'] for c, s in council_list}
        
        completed = 0
        for future in concurrent.futures.as_completed(future_to_council):
            completed += 1
            name = future_to_council[future]
            try:
                res = future.result()
                results.append(res)
                print(f"[{completed}/{len(council_list)}] {name}: {res['status']}")
            except Exception as exc:
                print(f"[{completed}/{len(council_list)}] {name} generated an exception: {exc}")
                
    generate_report(results)

if __name__ == "__main__":
    main()
