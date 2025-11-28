#!/usr/bin/env python3
"""
Council News Bot - Main Entry Point

Scrapes news articles from Victorian council websites and posts them to BlueSky.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set

from scrapers.base_scraper import CardScraper, NewsArticle
from poster import BlueSkyPoster


# Path to data files
DATA_DIR = Path(__file__).parent / 'data'
POSTED_FILE = DATA_DIR / 'posted_articles.json'
CONFIG_DIR = Path(__file__).parent / 'config'
COUNCILS_FILE = CONFIG_DIR / 'councils.json'

# Maximum age for articles (in days) - Chris wants fresh content only
MAX_ARTICLE_AGE_DAYS = 7


def load_councils() -> List[Dict]:
    """Load council configuration from JSON file."""
    with open(COUNCILS_FILE, 'r') as f:
        data = json.load(f)
    return data.get('councils', [])


def load_bot_state() -> Dict:
    """
    Load the bot's persistent state.
    
    State includes:
    - posted_urls: Set of URLs already posted
    - last_post_time: ISO timestamp of last post (for 15-min gap)
    - known_urls: URLs seen in previous scrapes (for prioritizing new discoveries)
    """
    if not POSTED_FILE.exists():
        return {
            'posted_urls': [],
            'last_post_time': None,
            'known_urls': []
        }
    
    with open(POSTED_FILE, 'r') as f:
        data = json.load(f)
    
    # Handle legacy format (just posted_urls list)
    if isinstance(data.get('posted_urls'), list) and 'last_post_time' not in data:
        return {
            'posted_urls': data.get('posted_urls', []),
            'last_post_time': None,
            'known_urls': data.get('posted_urls', [])  # Treat posted as known
        }
    
    # Ensure known_urls exists
    if 'known_urls' not in data:
        data['known_urls'] = data.get('posted_urls', [])
    
    return data


def save_bot_state(state: Dict) -> None:
    """Save the bot's persistent state."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(POSTED_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def load_posted_articles() -> Set[str]:
    """Load the set of previously posted article URLs (legacy helper)."""
    state = load_bot_state()
    return set(state.get('posted_urls', []))


def save_posted_articles(posted_urls: Set[str]) -> None:
    """Save the set of posted article URLs (legacy helper)."""
    state = load_bot_state()
    state['posted_urls'] = list(posted_urls)
    save_bot_state(state)


def get_scraper(council: Dict) -> CardScraper:
    """
    Get the appropriate scraper for a council.
    
    Args:
        council: Council configuration dictionary
        
    Returns:
        Configured scraper instance
    """
    scraper_type = council.get('scraper', 'card_scraper')
    use_curl = scraper_type == 'curl_scraper'
    
    return CardScraper(
        council_id=council['id'],
        council_name=council['name'],
        news_url=council['news_url'],
        use_curl=use_curl
    )


def scrape_all_councils(councils: List[Dict], enabled_only: bool = True) -> List[NewsArticle]:
    """
    Scrape news from all configured councils.
    
    Args:
        councils: List of council configurations
        enabled_only: Only scrape enabled councils
        
    Returns:
        List of all scraped articles
    """
    all_articles = []
    
    for council in councils:
        if enabled_only and not council.get('enabled', False):
            continue
        
        print(f"Scraping {council['name']}...")
        
        try:
            scraper = get_scraper(council)
            articles = scraper.scrape()
            all_articles.extend(articles)
            print(f"  Found {len(articles)} articles")
        except Exception as e:
            print(f"  Error: {e}")
    
    return all_articles


def filter_fresh_articles(articles: List[NewsArticle], max_age_days: int = MAX_ARTICLE_AGE_DAYS) -> List[NewsArticle]:
    """
    Filter articles to only include those within the freshness window.
    
    Articles without a date are assumed to be fresh (included).
    
    Args:
        articles: List of articles to filter
        max_age_days: Maximum age in days (default: 7)
        
    Returns:
        List of fresh articles
    """
    cutoff_date = datetime.now() - timedelta(days=max_age_days)
    fresh = []
    stale_count = 0
    
    for article in articles:
        if article.date is None:
            # No date - assume fresh
            fresh.append(article)
        else:
            # Handle timezone-aware dates by comparing naive
            article_date = article.date
            if hasattr(article_date, 'tzinfo') and article_date.tzinfo is not None:
                article_date = article_date.replace(tzinfo=None)
            
            if article_date >= cutoff_date:
                fresh.append(article)
            else:
                stale_count += 1
    
    if stale_count > 0:
        print(f"  Filtered out {stale_count} articles older than {max_age_days} days")
    
    return fresh


def post_new_articles(
    articles: List[NewsArticle],
    posted_urls: Set[str],
    dry_run: bool = False,
    limit: int = 0
) -> Set[str]:
    """
    Post new articles to BlueSky.
    
    Prioritizes newly discovered articles (not seen in previous scrapes)
    over backlog items.
    
    Args:
        articles: List of scraped articles
        posted_urls: Set of already posted URLs
        dry_run: If True, don't actually post
        limit: Maximum number of articles to post (0 = no limit)
        
    Returns:
        Updated set of posted URLs
    """
    # Filter to fresh articles only (max 7 days old)
    fresh_articles = filter_fresh_articles(articles)
    
    # Load state for known URLs tracking
    state = load_bot_state()
    known_urls = set(state.get('known_urls', []))
    
    # Separate into newly discovered vs backlog
    new_articles = [a for a in fresh_articles if a.url not in posted_urls]
    newly_discovered = [a for a in new_articles if a.url not in known_urls]
    backlog = [a for a in new_articles if a.url in known_urls]
    
    # Prioritize newly discovered, then backlog
    prioritized = newly_discovered + backlog
    
    if limit > 0:
        prioritized = prioritized[:limit]
    
    if not prioritized:
        print("No new articles to post")
        # Still update known_urls with all scraped URLs
        all_scraped_urls = [a.url for a in fresh_articles]
        state['known_urls'] = list(set(known_urls) | set(all_scraped_urls))
        save_bot_state(state)
        return posted_urls
    
    print(f"\nFound {len(prioritized)} new articles ({len(newly_discovered)} newly discovered, {len(backlog)} backlog)")
    
    if dry_run:
        print("\nDry run - would post:")
        for article in prioritized:
            marker = "🆕" if article.url not in known_urls else "📰"
            print(f"  {marker} {article.council_name}: {article.title[:50]}...")
        return posted_urls
    
    last_post_time = state.get('last_post_time')
    
    # Check 15-minute gap requirement
    if last_post_time:
        last_post_dt = datetime.fromisoformat(last_post_time)
        time_since_last = datetime.now() - last_post_dt
        min_gap = timedelta(minutes=15)
        
        if time_since_last < min_gap:
            wait_seconds = (min_gap - time_since_last).total_seconds()
            print(f"\n⏳ Must wait {int(wait_seconds)}s before next post (15-min gap)")
            print(f"   Last post: {last_post_dt.strftime('%H:%M:%S')}")
            return posted_urls
    
    # Initialize poster
    poster = BlueSkyPoster()
    if not poster.authenticate():
        print("Failed to authenticate with BlueSky")
        return posted_urls
    
    # Post only ONE article (respect 15-min gap by posting one at a time)
    article = prioritized[0]
    is_new = article.url not in known_urls
    
    if poster.post_article(
        article.council_name, 
        article.title, 
        article.url,
        date=article.date,
        excerpt=article.excerpt
    ):
        posted_urls.add(article.url)
        # Update state
        state['posted_urls'] = list(posted_urls)
        state['last_post_time'] = datetime.now().isoformat()
        # Add all scraped URLs to known_urls
        all_scraped_urls = [a.url for a in fresh_articles]
        state['known_urls'] = list(set(known_urls) | set(all_scraped_urls))
        save_bot_state(state)
        
        marker = "🆕 NEW" if is_new else "📰 BACKLOG"
        print(f"\n✅ Posted 1 {marker} article. {len(prioritized) - 1} remaining.")
    
    return posted_urls


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Council News Bot - Scrapes and posts Victorian council news'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Scrape but do not post to BlueSky'
    )
    parser.add_argument(
        '--council',
        type=str,
        help='Scrape only a specific council (by ID)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Include disabled councils'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test BlueSky connection'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=0,
        help='Maximum number of articles to post (0 = no limit)'
    )
    
    args = parser.parse_args()
    
    # Test mode
    if args.test:
        poster = BlueSkyPoster()
        if poster.test_connection():
            print("BlueSky connection successful!")
            sys.exit(0)
        else:
            print("BlueSky connection failed!")
            sys.exit(1)
    
    # Load configuration
    councils = load_councils()
    posted_urls = load_posted_articles()
    
    print(f"Loaded {len(councils)} councils, {len(posted_urls)} previously posted articles")
    
    # Filter to specific council if requested
    if args.council:
        councils = [c for c in councils if c['id'] == args.council]
        if not councils:
            print(f"Council '{args.council}' not found")
            sys.exit(1)
    
    # Scrape articles
    articles = scrape_all_councils(councils, enabled_only=not args.all)
    
    print(f"\nTotal: {len(articles)} articles scraped")
    
    # Post new articles
    posted_urls = post_new_articles(articles, posted_urls, dry_run=args.dry_run, limit=args.limit)
    
    # Save updated posted list
    if not args.dry_run:
        save_posted_articles(posted_urls)
        print(f"\nSaved {len(posted_urls)} posted URLs")


if __name__ == '__main__':
    main()
