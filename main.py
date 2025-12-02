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

from core.scraper import CardScraper, NewsArticle, InnerWestScraper, RSSScraper
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
    
    scraper_type = council.get('scraper', 'card_scraper')
    use_curl = scraper_type == 'curl_scraper'
    mobile_mode = council.get('mobile_mode', False)
    limit = council.get('limit')
    
    selectors = {
        'item_selector': council.get('item_selector'),
        'title_selector': council.get('title_selector'),
        'link_selector': council.get('link_selector'),
        'date_selector': council.get('date_selector'),
        'content_selector': council.get('content_selector')
    }
    
    # Registry of custom scrapers
    # TODO: Move this to a separate registry file if it grows
    scraper_classes = {
        'inner_west_scraper': InnerWestScraper,
        'card_scraper': CardScraper,
        'curl_scraper': CardScraper, # curl_scraper is just CardScraper with use_curl=True
        'rss_scraper': RSSScraper,
    }
    
    scraper_class = scraper_classes.get(scraper_type, CardScraper)
    
    # Use CLI proxy if provided, otherwise check council config
    use_proxy = proxy or council.get('proxy')
    
    return scraper_class(
        council_id=council['id'],
        council_name=council['name'],
        news_url=council['news_url'],
        use_curl=use_curl,
        mobile_mode=mobile_mode,
        selectors=selectors,
        limit=limit,
        proxy=use_proxy
    )

def scrape_single_council(council: Dict, proxy: Optional[str] = None) -> List[NewsArticle]:
    """Helper to scrape a single council."""
    print(f"Scraping {council['name']}...")
    try:
        scraper = get_scraper(council, proxy=proxy)
        articles = scraper.scrape()
        print(f"  {council['name']}: Found {len(articles)} articles")
        return articles
    except Exception as e:
        print(f"  Error scraping {council['name']}: {e}")
        return []

def scrape_councils(councils: List[Dict], enabled_only: bool = True, proxy: Optional[str] = None, max_workers: int = 5) -> List[NewsArticle]:
    """Scrape news from configured councils concurrently."""
    all_articles = []
    
    # Filter enabled councils first
    active_councils = [c for c in councils if not enabled_only or c.get('enabled', False)]
    
    print(f"Scraping {len(active_councils)} councils with {max_workers} workers...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_council = {
            executor.submit(scrape_single_council, council, proxy): council 
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
    filtered_articles = []
    skipped_count = 0
    
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
                skipped_count += 1
                continue
            
            filtered_articles.append(article)
        else:
            # Skip articles with no date to prevent "ghost" articles
            # We can't verify freshness without a date
            skipped_count += 1
            continue
            
    if skipped_count > 0:
        print(f"Skipped {skipped_count} articles older than {MAX_ARTICLE_AGE_DAYS} days")
    
    new_count = 0
    for article in filtered_articles:
        # Convert NewsArticle to dict for DB
        article_data = article.to_dict()
        
        # Add to DB (returns ID if new, or existing ID)
        # We ignore the return value for now, just ensuring it's in the DB
        if not db.article_exists(article.url):
            db.add_article(article_data, state_code)
            new_count += 1
            
    print(f"Added {new_count} new articles to database")
    
    # Return unposted articles from DB
    return db.get_unposted_articles(state_code)

def post_articles(articles: List[Dict], poster: BlueSkyPoster, db: Database, 
                  council_lookup: Dict[str, str], hashtags: List[str],
                  limit: int = 0, dry_run: bool = False):
    """Post articles to BlueSky."""
    if not articles:
        print("No articles to post")
        return

    print(f"Found {len(articles)} unposted articles")
    
    if limit > 0:
        articles = articles[:limit]
        print(f"Limiting to {limit} posts")
        
    if dry_run:
        print("\nDry run - would post:")
        for article in articles:
            council_name = council_lookup.get(article['council_id'], article['council_id'])
            print(f"  📰 {council_name}: {article['title']}")
        return

    # Authenticate
    if not poster.authenticate():
        print("Failed to authenticate with BlueSky")
        return

    posted_count = 0
    for article in articles:
        # Parse date string back to datetime if needed
        article_date = None
        if article.get('date'):
            try:
                article_date = date_parser.parse(article['date'])
            except Exception:
                pass
        
        council_name = council_lookup.get(article['council_id'], article['council_id'])
        
        if poster.post_article(
            council_name,
            article['title'],
            article['url'],
            date=article_date,
            excerpt=article['excerpt'],
            hashtags=hashtags
        ):
            db.mark_as_posted(article['url'], poster.handle)
            posted_count += 1
            print(f"✅ Posted: {article['title'][:50]}...")
            
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
    parser.add_argument('--limit', type=int, default=0, help='Max posts')
    parser.add_argument('--post-only', action='store_true', help='Skip scrape, post from backlog')
    parser.add_argument('--scrape-only', action='store_true', help='Scrape and save to DB, but do not post')
    parser.add_argument('--proxy', type=str, help='Proxy URL (e.g. http://user:pass@host:port)')
    parser.add_argument('--concurrency', type=int, default=5, help='Number of concurrent scrapers')
    
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
    # Allow DB path to be overridden by env var (useful for Docker)
    default_db_path = os.path.join(os.path.dirname(__file__), 'bot.db')
    db_path = os.environ.get('DB_PATH', default_db_path)
    
    # Ensure directory exists if using a custom path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    db = Database(db_path)
    
    # Initialize Poster
    handle = os.environ.get(state_data['config']['bluesky_handle_env'])
    password = os.environ.get(state_data['config']['bluesky_password_env'])
    poster = BlueSkyPoster(handle, password)
    
    # Prepare council lookup and hashtags
    council_lookup = {c['id']: c['name'] for c in state_data['councils']}
    hashtags = state_data['config'].get('hashtags', [])
    
    # Scrape (unless post-only)
    if not args.post_only:
        articles = scrape_councils(state_data['councils'], proxy=proxy_url, max_workers=args.concurrency)
        unposted = process_articles(articles, db, state_code)
    else:
        print("Skipping scrape, checking backlog...")
        unposted = db.get_unposted_articles(state_code)
        
    # Post
    if not args.scrape_only:
        post_articles(unposted, poster, db, council_lookup, hashtags, limit=args.limit, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
