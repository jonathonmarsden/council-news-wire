import sys
import os
import argparse
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import load_state_config, get_scraper

def check_health(state_code):
    print(f"[Health Check] Checking Scraper Health for {state_code.upper()}...")
    
    try:
        state_data = load_state_config(state_code)
    except ValueError as e:
        print(f"Error: {e}")
        return

    councils = state_data['councils']
    
    print(f"{'Council':<30} | {'Articles':<8} | {'Dated':<8} | {'Health':<10}")
    print("-" * 65)
    
    for council in councils:
        if not council.get('enabled', True):
            continue
            
        try:
            scraper = get_scraper(council)
            articles = scraper.scrape()
            
            total = len(articles)
            dated = sum(1 for a in articles if a.date)
            
            health = "[OK]"
            if total == 0:
                health = "[EMPTY]"
            elif dated == 0:
                health = "[BROKEN]"
            elif dated < total:
                health = "[PARTIAL]"
                
            print(f"{council['name'][:30]:<30} | {total:<8} | {dated:<8} | {health:<10}")
            
        except Exception as e:
            print(f"{council['name'][:30]:<30} | {'ERR':<8} | {'-':<8} | [ERROR]")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', type=str, default='vic')
    args = parser.parse_args()
    
    check_health(args.state)
