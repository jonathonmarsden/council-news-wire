#!/usr/bin/env python3
"""
Council News Bot - Main Entry Point

Scrapes news articles from Victorian council websites and posts them to BlueSky.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set

from scrapers.base_scraper import CardScraper, NewsArticle
from poster import BlueSkyPoster


# Path to data files
DATA_DIR = Path(__file__).parent / 'data'
POSTED_FILE = DATA_DIR / 'posted_articles.json'
CONFIG_DIR = Path(__file__).parent / 'config'
COUNCILS_FILE = CONFIG_DIR / 'councils.json'


def load_councils() -> List[Dict]:
    """Load council configuration from JSON file."""
    with open(COUNCILS_FILE, 'r') as f:
        data = json.load(f)
    return data.get('councils', [])


def load_posted_articles() -> Set[str]:
    """Load the set of previously posted article URLs."""
    if not POSTED_FILE.exists():
        return set()
    
    with open(POSTED_FILE, 'r') as f:
        data = json.load(f)
    
    return set(data.get('posted_urls', []))


def save_posted_articles(posted_urls: Set[str]) -> None:
    """Save the set of posted article URLs."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(POSTED_FILE, 'w') as f:
        json.dump({'posted_urls': list(posted_urls)}, f, indent=2)


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


def post_new_articles(
    articles: List[NewsArticle],
    posted_urls: Set[str],
    dry_run: bool = False
) -> Set[str]:
    """
    Post new articles to BlueSky.
    
    Args:
        articles: List of scraped articles
        posted_urls: Set of already posted URLs
        dry_run: If True, don't actually post
        
    Returns:
        Updated set of posted URLs
    """
    new_articles = [a for a in articles if a.url not in posted_urls]
    
    if not new_articles:
        print("No new articles to post")
        return posted_urls
    
    print(f"\nFound {len(new_articles)} new articles")
    
    if dry_run:
        print("\nDry run - would post:")
        for article in new_articles:
            print(f"  📰 {article.council_name}: {article.title[:50]}...")
        return posted_urls
    
    # Initialize poster
    poster = BlueSkyPoster()
    if not poster.authenticate():
        print("Failed to authenticate with BlueSky")
        return posted_urls
    
    # Post new articles
    for article in new_articles:
        if poster.post_article(
            article.council_name, 
            article.title, 
            article.url,
            date=article.date,
            excerpt=article.excerpt
        ):
            posted_urls.add(article.url)
    
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
    posted_urls = post_new_articles(articles, posted_urls, dry_run=args.dry_run)
    
    # Save updated posted list
    if not args.dry_run:
        save_posted_articles(posted_urls)
        print(f"\nSaved {len(posted_urls)} posted URLs")


if __name__ == '__main__':
    main()
