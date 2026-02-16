#!/usr/bin/env python3
"""
Council News Bot - Main Entry Point

Scrapes news articles from Australian council websites and posts them to BlueSky.
Supports multiple states via the --state argument.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import random
import concurrent.futures
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set, Optional

from dotenv import load_dotenv
from dateutil import parser as date_parser

# Optional Discord logging - fails silently if not configured
try:
    from discord_logger import (
        current_run,
        start_run,
        finish_run,
        log_error,
        log_warning,
    )
    DISCORD_LOGGING = True
except ImportError:
    DISCORD_LOGGING = False

from core.scrapers import CardScraper, NewsArticle, InnerWestScraper, RSSScraper, ScraperFactory
from core.poster import BlueSkyPoster
from core.database import Database
from core.utils import setup_logging
from core.timezone_utils import (
    is_morning_window, 
    get_recommended_concurrency,
    STATE_TIMEZONES
)
from core.exceptions import ScrapeError, ConfigurationError

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


def load_hashtag_map() -> Dict[str, str]:
    """Load canonical council hashtags (generated from state configs)."""
    map_path = Path(__file__).parent / 'docs' / 'hashtags_map.json'
    if not map_path.exists():
        return {}
    try:
        with map_path.open() as f:
            data = json.load(f)
            return data.get('councils', {})
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to load hashtag map: {e}")
        return {}

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
            db.record_success(council['id'], articles_found=count)
            duration_ms = int((time.time() - start_time) * 1000)
            status = 'ok' if count > 0 else 'empty'
            db.log_scraper_run(council['id'], count, status, duration_ms)
            
        return articles
    except ScrapeError as e:
        print(f"  Error scraping {council['name']}: {e}")
        if db:
            is_disabled = db.record_failure(council['id'])
            duration_ms = int((time.time() - start_time) * 1000)
            db.log_scraper_run(council['id'], 0, 'error', duration_ms)
            
            if is_disabled:
                print(f"  ⚠️ CRITICAL: {council['name']} has been DISABLED after 5 consecutive failures!")
        if DISCORD_LOGGING:
            try:
                log_error(
                    council['id'],
                    f"Scraper error: {e}",
                    event_type="scrape_error",
                    metadata={"news_url": council.get('news_url')},
                )
            except Exception as log_err:
                print(f"Warning: Failed to log scrape error: {log_err}")
        return []

def scrape_councils(councils: List[Dict], db: Database, enabled_only: bool = True, proxy: Optional[str] = None, max_workers: int = 5) -> List[NewsArticle]:
    """Scrape news from configured councils concurrently."""
    all_articles = []
    
    # Filter enabled councils first
    active_councils = [c for c in councils if not enabled_only or c.get('enabled', False)]
    
    # Shuffle councils to prevent "Starvation" of those late in the alphabet if the run times out
    random.shuffle(active_councils)
    
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

                # Track per-council results for run summary
                if DISCORD_LOGGING:
                    try:
                        current_run.log_council_result(
                            council.get('name', council.get('id')),
                            len(articles)
                        )
                    except Exception as e:
                        print(f"Warning: Failed to log run metrics: {e}")

                # ALERTING: Check for Silent Failures (0 articles found)
                if len(articles) == 0 and council.get('enabled', True):
                    msg = f"⚠️ Silent Failure: {council['name']} returned 0 articles."
                    print(msg)
                    if DISCORD_LOGGING and db:
                        try:
                            # Check consecutive failures from DB to avoid flapping alerts
                            health = db.get_council_health(council['id'])
                            empty_runs = health.get('consecutive_empty_runs', 0)

                            # Only alert if persistent (>= 3 runs) to reduce false positives
                            if empty_runs >= 3:
                                log_warning(
                                    council['id'],
                                    f"Silent Failure (x{empty_runs}): Scraper returned 0 articles for {empty_runs} consecutive runs.",
                                    event_type="silent_failure",
                                    metadata={"news_url": council.get('news_url')},
                                )
                        except (KeyError, AttributeError) as e:
                            print(f"Warning: Failed to check health/log to discord: {e}")
            except Exception as e:
                print(f"  Unhandled error scraping {council['name']}: {e}")
                # Still count error councils in accumulator
                if DISCORD_LOGGING:
                    try:
                        current_run.log_council_result(council.get('name', council.get('id')), 0)
                    except Exception as discord_err:
                        print(f"Warning: Failed to log discord stats: {discord_err}")
            
    return all_articles

from core.constants import GARBAGE_TITLES, GENERIC_TITLES, ADDRESS_MARKERS

def is_valid_article(article_obj) -> bool:
    """
    Check if article content looks like a real news item.
    Accepts NewsArticle object or Dictionary.
    """
    # Handle access for both Object and Dict types
    if isinstance(article_obj, dict):
        title = article_obj.get('title')
    else:
        title = getattr(article_obj, 'title', None)
        
    if not title or not title.strip():
        return False
        
    title = title.strip()
    
    # reject too short
    if len(title) < 5:
        return False
        
    # reject purely numeric (e.g. "2026", "6175")
    if title.replace('-', '').replace(' ', '').isdigit():
        return False
        
    # reject generic site navigation
    if title.lower() in GENERIC_TITLES:
        return False
        
    # reject address-like titles (e.g. "Lot 112 Smith St")
    # Simple heuristic: Starts with digit, contains "Street", "Road", "Lot"
    if title[0].isdigit() and any(x in title.lower() for x in ADDRESS_MARKERS):
        return False

    # reject metadata titles (e.g. "Posted 04 December 2025")
    if title.lower().startswith('posted ') and any(c.isdigit() for c in title):
        return False
        
    # reject copyright footers (e.g. "© 2025 Shire of ...")
    if title.startswith('©') or title.startswith('&copy;'):
        return False

    # reject common garbage and non-news items
    if title.lower() in GARBAGE_TITLES:
        return False

    return True

def process_articles(articles: List[NewsArticle], db: Database, state_code: str, force_fresh: bool = False) -> List[Dict]:
    """
    Process scraped articles:
    1. Filter by age and CONTENT QUALITY
    2. Add to database (if new)
    3. Return list of unposted articles
    """
    now = datetime.now()
    cutoff_date = now - timedelta(days=MAX_ARTICLE_AGE_DAYS)
    fresh_articles = []
    archived_articles = []
    
    # Filter out garbage
    valid_articles = [a for a in articles if is_valid_article(a)]
    rejected_count = len(articles) - len(valid_articles)
    if rejected_count > 0:
        print(f"  Rejected {rejected_count} articles as invalid garbage content.")

    for article in valid_articles:
        # Only post items with a scraped date inside the freshness window
        is_fresh = False
        if force_fresh:
            is_fresh = True
        elif article.date:
            # Handle timezone awareness mismatch
            check_date = article.date
            check_cutoff = cutoff_date
            if check_date.tzinfo is not None and check_date.tzinfo.utcoffset(check_date) is not None:
                check_cutoff = datetime.now(check_date.tzinfo) - timedelta(days=MAX_ARTICLE_AGE_DAYS)
            is_fresh = check_date >= check_cutoff
        
        if is_fresh:
            fresh_articles.append(article)
        else:
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
                  council_hashtag_map: Dict[str, str],
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
            except (ValueError, TypeError) as e:
                print(f"Warning: Failed to parse date '{article.get('date')}': {e}")
        
        # VALIDATION CHECK: Prevent posting malformed/garbage articles
        if not is_valid_article(article):
            print(f"⚠️ Skipping invalid article (metadata/garbage): {article.get('title', 'Unknown')}")
            # Mark as posted to prevent retry loop
            db.mark_as_posted(article['url'], "REJECTED_VALIDATION")
            continue

        council_config = council_lookup.get(c_id, {})
        council_name = council_config.get('name', c_id)
        council_tag = council_hashtag_map.get(c_id)
        
        # Check if excerpt should be skipped
        excerpt = article['excerpt']
        if council_config.get('skip_excerpt'):
            excerpt = None

        # Build hashtag list per article: base state tags + canonical council tag
        tags_for_post = list(hashtags) if hashtags else []
        if council_tag and council_tag not in tags_for_post:
            tags_for_post.append(council_tag)
        
        post_uri = poster.post_article(
            council_name,
            article['title'],
            article['url'],
            date=article_date,
            excerpt=excerpt,
            hashtags=tags_for_post,
            council_hashtag=council_tag
        )
        if post_uri:
            db.mark_as_posted(article['url'], poster.handle)
            posted_count += 1
            council_counts[c_id] = council_counts.get(c_id, 0) + 1
            print(f"✅ Posted: {article['title'][:50]}...")
            
            # Update run summary stats (Discord summaries are periodic)
            if DISCORD_LOGGING:
                try:
                    current_run.log_posted(1)
                except (AttributeError, KeyError, TypeError) as log_err:
                    print(f"Warning: Failed to log run post stats: {log_err}")
            
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
    parser.add_argument('--force-fresh', action='store_true', help='Bypass 7-day freshness check (force post old articles)')
    parser.add_argument('--time-window', type=str, choices=['morning', 'evening'], 
                        help='Times window for dynamic concurrency reduction (passed by cron)')
    
    args = parser.parse_args()
    
    # Determine proxy: CLI arg > Env Var > None
    proxy_url = args.proxy or os.environ.get('COUNCIL_BOT_PROXY')
    
    state_code = args.state.upper()
    
    # Determine if currently in morning window and apply dynamic concurrency
    is_morning = False
    if args.time_window == 'morning':
        # Explicitly flagged as morning (from cron)
        is_morning = True
    elif args.time_window == 'evening':
        # Explicitly flagged as evening (from cron)
        is_morning = False
    else:
        # Auto-detect: check current time in state's timezone
        if state_code in STATE_TIMEZONES:
            tz = STATE_TIMEZONES[state_code]
            now_local = datetime.now(tz)
            is_morning = is_morning_window(now_local.hour, now_local.minute)
    
    # Apply dynamic concurrency if needed
    if is_morning and args.concurrency == 5:  # Only override if using default concurrency
        recommended = get_recommended_concurrency(state_code, is_morning=True)
        args.concurrency = recommended
        print(f"🕐 Morning window detected: Reducing concurrency from 5 to {recommended} to manage load")
    elif is_morning:
        print(f"🕐 Morning window detected: Using requested concurrency {args.concurrency}")
    

    # Auto-detect state if council is specified but not found in default state
    if args.council:
        # First try the requested/default state
        try:
            state_data = load_state_config(state_code)
            found = False
            for c in state_data['councils']:
                if c['id'] == args.council:
                    found = True
                    break
            
            if not found:
                raise ConfigurationError(f"Council '{args.council}' not found in {state_code}")
                
        except ConfigurationError:
            # Not found in default state, search others
            found_state = None
            print(f"Council '{args.council}' not found in {state_code}, searching other states...")
            
            states_dir = Path(__file__).parent / 'states'
            for state_dir in states_dir.iterdir():
                if not state_dir.is_dir() or state_dir.name.startswith('_'):
                    continue
                    
                s_code = state_dir.name.upper()
                if s_code == state_code:
                    continue
                    
                try:
                    s_data = load_state_config(s_code)
                    for c in s_data['councils']:
                        if c['id'] == args.council:
                            found_state = s_code
                            print(f"Found '{args.council}' in {found_state}")
                            break
                except (ConfigurationError, IOError) as e:
                    print(f"Debug: Could not load {s_code}: {e}")
                    continue
                
                if found_state:
                    break
            
            if found_state:
                state_code = found_state
                state_data = load_state_config(state_code)
            else:
                print(f"Error: Council '{args.council}' not found in any state configuration.")
                sys.exit(1)
    else:
        # Standard load
        try:
            state_data = load_state_config(state_code)
        except ConfigurationError as e:
            print(f"Error: {e}")
            sys.exit(1)
            
    print(f"=== Council News Bot: {state_data['config']['state_name']} ===")
    
    # Start a new run tracker after state is finalized
    if DISCORD_LOGGING:
        start_run(state_code)

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
    council_hashtag_map = load_hashtag_map()
    
    # Scrape (unless post-only)
    if not args.post_only:
        articles = scrape_councils(councils_to_scrape, db=db, proxy=proxy_url, max_workers=args.concurrency)
        unposted = process_articles(articles, db, state_code)
    else:
        print("Skipping scrape, checking backlog...")
        unposted = db.get_unposted_articles(state_code)
        
    # Post
    if not args.scrape_only:
        post_articles(unposted, poster, db, council_lookup, hashtags, council_hashtag_map,
                  limit=args.limit, 
                  dry_run=args.dry_run,
                  max_per_council=args.max_per_council)

    # Persist run summary at the end of run
    if DISCORD_LOGGING and not args.council: # Don't log summary for single council runs
        finish_run()

if __name__ == "__main__":
    main()
