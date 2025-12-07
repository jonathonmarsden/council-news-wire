#!/usr/bin/env python3
"""
Council News Bot - Main Entry Point

Scrapes news articles from Australian council websites and posts them to BlueSky.
Supports multiple states via the --state argument.
"""

import argparse
import json
import os
import sys
import time
import concurrent.futures
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set, Optional

from dotenv import load_dotenv
from dateutil import parser as date_parser

# Optional Discord logging - fails silently if not configured
try:
    from discord_logger import log_post_success, log_error
    DISCORD_LOGGING = True
except ImportError:
    DISCORD_LOGGING = False

from core.scrapers import CardScraper, NewsArticle, InnerWestScraper, RSSScraper, ScraperFactory
from core.poster import BlueSkyPoster
from core.database import Database
from core.utils import setup_logging

# Constants
MAX_ARTICLE_AGE_DAYS = 7
DEFAULT_STATE = 'vic'

def load_state_config(state_code: str) -> Dict:
    """Load configuration for a specific state."""
    base_path = Path(__file__).parent / 'states' / state_code.lower()
    config_file = base_path / 'config.json'
    councils_file = base_path / 'councils.json'
    
    if not config_file.exists():
        raise ValueError(f"State configuration not found: {state_code}")
        
    with open(config_file, 'r') as f:
        config = json.load(f)
        
    with open(councils_file, 'r') as f:
        councils_data = json.load(f)
        
    return {
        'config': config,
        'councils': councils_data.get('councils', [])
    }

def get_scraper(council: Dict, proxy: Optional[str] = None) -> CardScraper:
    """Get the appropriate scraper for a council."""
    return ScraperFactory.create_scraper(council, proxy)

def scrape_single_council(council: Dict, proxy: Optional[str] = None, db: Optional[Database] = None) -> List[NewsArticle]:
    """Helper to scrape a single council."""
    start_time = time.time()
    
    # Check Circuit Breaker
    if db:
        health = db.get_council_health(council['id'])
        if health.get('is_disabled'):
            print(f"Skipping {council['name']} (DISABLED due to {health.get('consecutive_failures')} failures)")
            return []
            
    print(f"Scraping {council['name']}...")
    
    # Check for rotating proxy requirement
    if council.get('use_rotating_proxy'):
        rotating_proxy = os.environ.get('COUNCIL_BOT_ROTATING_PROXY')
        if rotating_proxy:
            proxy = rotating_proxy
            print(f"  Using rotating proxy for {council['name']}")
        else:
            print(f"  Warning: {council['name']} requests rotating proxy but COUNCIL_BOT_ROTATING_PROXY is not set.")
            
    try:
        scraper = get_scraper(council, proxy=proxy)
        articles = scraper.scrape()
        count = len(articles)
        print(f"  {council['name']}: Found {count} articles")
        
        if db:
            db.record_success(council['id'])
            duration_ms = int((time.time() - start_time) * 1000)
            status = 'ok' if count > 0 else 'empty'
            db.log_scraper_run(council['id'], count, status, duration_ms)
            
        return articles
    except Exception as e:
        print(f"  Error scraping {council['name']}: {e}")
        if db:
            is_disabled = db.record_failure(council['id'])
            duration_ms = int((time.time() - start_time) * 1000)
            db.log_scraper_run(council['id'], 0, 'error', duration_ms)
            
            if is_disabled:
                print(f"  ⚠️ CRITICAL: {council['name']} has been DISABLED after 5 consecutive failures!")
        return []

def scrape_councils(councils: List[Dict], db: Database, enabled_only: bool = True, proxy: Optional[str] = None, max_workers: int = 5) -> List[NewsArticle]:
    """Scrape news from configured councils concurrently."""
    all_articles = []
    
    # Filter enabled councils first
    active_councils = [c for c in councils if not enabled_only or c.get('enabled', False)]
    
    print(f"Scraping {len(active_councils)} councils with {max_workers} workers...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_council = {
            executor.submit(scrape_single_council, council, proxy, db): council 
            for council in active_councils
        }
        
        for future in concurrent.futures.as_completed(future_to_council):
            council = future_to_council[future]
            try:
                articles = future.result()
                all_articles.extend(articles)
            except Exception as e:
                print(f"  Unhandled error scraping {council['name']}: {e}")
            
    return all_articles

def process_articles(articles: List[NewsArticle], db: Database, state_code: str) -> List[Dict]:
    """
    Process scraped articles:
    1. Filter by age
    2. Add to database (if new)
    3. Return list of unposted articles
    """
    cutoff_date = datetime.now() - timedelta(days=MAX_ARTICLE_AGE_DAYS)
    fresh_articles = []
    archived_articles = []
    
    for article in articles:
        # Filter by age if date is available
        if article.date:
            # Handle timezone awareness mismatch
            # If article.date is aware, we need an aware cutoff
            check_date = article.date
            check_cutoff = cutoff_date
            
            if check_date.tzinfo is not None and check_date.tzinfo.utcoffset(check_date) is not None:
                # Article is aware, make cutoff aware using same timezone
                check_cutoff = datetime.now(check_date.tzinfo) - timedelta(days=MAX_ARTICLE_AGE_DAYS)
            
            if check_date < check_cutoff:
                archived_articles.append(article)
            else:
                fresh_articles.append(article)
        else:
            # Skip articles with no date to prevent "ghost" articles
            # We can't verify freshness without a date, so we archive them to be safe
            # but we still record them to know the scraper is working
            archived_articles.append(article)
            
    # Bulk insert fresh articles
    fresh_data = [a.to_dict() for a in fresh_articles]
    new_fresh_count = db.add_articles_bulk(fresh_data, state_code, status='new')
    
    # Bulk insert archived articles
    archived_data = [a.to_dict() for a in archived_articles]
    new_archived_count = db.add_articles_bulk(archived_data, state_code, status='archived')
    
    total_found = len(articles)
    total_new_db = new_fresh_count + new_archived_count
    duplicates = total_found - total_new_db
            
    print(f"Processing Summary: Found {total_found} total")
    print(f"  - {new_fresh_count} new fresh articles (queued)")
    print(f"  - {new_archived_count} new archived articles (too old)")
    print(f"  - {duplicates} duplicates (already known)")
    
    # Return unposted articles from DB
    return db.get_unposted_articles(state_code)

def post_articles(articles: List[Dict], poster: BlueSkyPoster, db: Database, 
                  council_lookup: Dict[str, Dict], hashtags: List[str],
                  limit: int = 0, dry_run: bool = False, max_per_council: int = 5):
    """Post articles to BlueSky."""
    if not articles:
        print("No articles to post")
        return

    print(f"Found {len(articles)} unposted articles")
    
    if limit > 0:
        articles = articles[:limit]
        print(f"Limiting to {limit} posts total")
        
    if dry_run:
        print("\nDry run - would post:")
        council_counts = {}
        for article in articles:
            c_id = article['council_id']
            if council_counts.get(c_id, 0) >= max_per_council:
                continue
            council_counts[c_id] = council_counts.get(c_id, 0) + 1
            
            council_config = council_lookup.get(c_id, {})
            council_name = council_config.get('name', c_id)
            print(f"  📰 {council_name}: {article['title']}")
        return

    # Authenticate
    if not poster.authenticate():
        print("Failed to authenticate with BlueSky")
        return

    posted_count = 0
    council_counts = {}
    
    for article in articles:
        # Check per-council limit
        c_id = article['council_id']
        if council_counts.get(c_id, 0) >= max_per_council:
            print(f"  ⚠️ Skipping {article['title'][:30]}... (Max {max_per_council} posts reached for {c_id})")
            continue

        # Parse date string back to datetime if needed
        article_date = None
        if article.get('date'):
            try:
                article_date = date_parser.parse(article['date'])
            except Exception:
                pass
        
        council_config = council_lookup.get(c_id, {})
        council_name = council_config.get('name', c_id)
        
        # Check if excerpt should be skipped
        excerpt = article['excerpt']
        if council_config.get('skip_excerpt'):
            excerpt = None
        
        post_uri = poster.post_article(
            council_name,
            article['title'],
            article['url'],
            date=article_date,
            excerpt=excerpt,
            hashtags=hashtags
        )
        if post_uri:
            db.mark_as_posted(article['url'], poster.handle)
            posted_count += 1
            council_counts[c_id] = council_counts.get(c_id, 0) + 1
            print(f"✅ Posted: {article['title'][:50]}...")
            
            # Log to Discord for real-time monitoring
            if DISCORD_LOGGING:
                try:
                    log_post_success(council_name, article['title'], article['url'], post_uri)
                except Exception as log_err:
                    print(f"Discord log failed: {log_err}")
            
            # Rate limiting delay
            if posted_count < len(articles):
                time.sleep(2)
                
    print(f"\n✅ Posted {posted_count} articles")

def main():
    # Load environment variables
    load_dotenv()
    
    parser = argparse.ArgumentParser(description='Council News Bot')
    parser.add_argument('--state', type=str, default=DEFAULT_STATE, help='State code (vic, nsw, etc)')
    parser.add_argument('--dry-run', action='store_true', help='Scrape but do not post')
    parser.add_argument('--limit', type=int, default=0, help='Max posts total')
    parser.add_argument('--max-per-council', type=int, default=5, help='Max posts per council per run')
    parser.add_argument('--post-only', action='store_true', help='Skip scrape, post from backlog')
    parser.add_argument('--scrape-only', action='store_true', help='Scrape and save to DB, but do not post')
    parser.add_argument('--proxy', type=str, help='Proxy URL (e.g. http://user:pass@host:port)')
    parser.add_argument('--concurrency', type=int, default=5, help='Number of concurrent scrapers')
    parser.add_argument('--council', type=str, help='Run for a specific council ID only')
    
    args = parser.parse_args()
    
    # Determine proxy: CLI arg > Env Var > None
    proxy_url = args.proxy or os.environ.get('COUNCIL_BOT_PROXY')
    
    state_code = args.state.upper()
    
    try:
        state_data = load_state_config(state_code)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
        
    print(f"=== Council News Bot: {state_data['config']['state_name']} ===")
    
    # Initialize DB
    db = Database()
    
    # Initialize Poster
    handle = os.environ.get(state_data['config']['bluesky_handle_env'])
    password = os.environ.get(state_data['config']['bluesky_password_env'])
    poster = BlueSkyPoster(handle, password)
    
    # Prepare council lookup and hashtags
    councils_to_scrape = state_data['councils']
    if args.council:
        councils_to_scrape = [c for c in councils_to_scrape if c['id'] == args.council]
        if not councils_to_scrape:
            print(f"Error: Council '{args.council}' not found in {state_code} configuration.")
            sys.exit(1)
            
    council_lookup = {c['id']: c for c in state_data['councils']}
    hashtags = state_data['config'].get('hashtags', [])
    
    # Scrape (unless post-only)
    if not args.post_only:
        articles = scrape_councils(councils_to_scrape, db=db, proxy=proxy_url, max_workers=args.concurrency)
        unposted = process_articles(articles, db, state_code)
    else:
        print("Skipping scrape, checking backlog...")
        unposted = db.get_unposted_articles(state_code)
        
    # Post
    if not args.scrape_only:
        post_articles(unposted, poster, db, council_lookup, hashtags, 
                      limit=args.limit, 
                      dry_run=args.dry_run,
                      max_per_council=args.max_per_council)

if __name__ == "__main__":
    main()
