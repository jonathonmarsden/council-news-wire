"""
Article processing and posting pipeline for Council News Bot.

Handles content quality filtering, staleness checks, database persistence,
and BlueSky posting.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from dateutil import parser as date_parser

from core.database import Database
from core.exceptions import TransientPostError
from core.poster import BlueSkyPoster
from core.validator import is_valid_article
from core.scrapers.base import NewsArticle

MAX_ARTICLE_AGE_DAYS = 7

# Optional Discord logging
try:
    from discord_logger import current_run
    DISCORD_LOGGING = True
except ImportError:
    DISCORD_LOGGING = False


def process_articles(
    articles: List[NewsArticle],
    db: Database,
    state_code: str,
    force_fresh: bool = False,
) -> List[Dict]:
    """
    Filter, validate, and persist scraped articles.

    Steps:
    1. Reject garbage/non-news content via is_valid_article()
    2. Separate fresh articles (within MAX_ARTICLE_AGE_DAYS) from archived ones
    3. Bulk-upsert both groups to the database
    4. Return the current unposted queue for this state

    Args:
        articles: Raw scraped articles from scrape_councils()
        db: Database instance
        state_code: Two-letter state code (e.g. 'VIC')
        force_fresh: If True, bypass the staleness check

    Returns:
        List of unposted article dicts from the database
    """
    now = datetime.now()
    cutoff_date = now - timedelta(days=MAX_ARTICLE_AGE_DAYS)
    fresh_articles = []
    archived_articles = []

    valid_articles = [a for a in articles if is_valid_article(a)]
    rejected_count = len(articles) - len(valid_articles)
    if rejected_count > 0:
        print(f"  Rejected {rejected_count} articles as invalid garbage content.")

    for article in valid_articles:
        is_fresh = False
        if force_fresh:
            is_fresh = True
        elif article.date:
            check_date = article.date
            check_cutoff = cutoff_date
            if check_date.tzinfo is not None and check_date.tzinfo.utcoffset(check_date) is not None:
                check_cutoff = datetime.now(check_date.tzinfo) - timedelta(days=MAX_ARTICLE_AGE_DAYS)
            is_fresh = check_date >= check_cutoff

        if is_fresh:
            fresh_articles.append(article)
        else:
            archived_articles.append(article)

    fresh_data = [a.to_dict() for a in fresh_articles]
    new_fresh_count = db.add_articles_bulk(fresh_data, state_code, status='new')

    archived_data = [a.to_dict() for a in archived_articles]
    new_archived_count = db.add_articles_bulk(archived_data, state_code, status='archived')

    total_found = len(articles)
    total_new_db = new_fresh_count + new_archived_count
    duplicates = total_found - total_new_db

    print(f"Processing Summary: Found {total_found} total")
    print(f"  - {new_fresh_count} new fresh articles (queued)")
    print(f"  - {new_archived_count} new archived articles (too old)")
    print(f"  - {duplicates} duplicates (already known)")

    return db.get_unposted_articles(state_code)


def post_articles(
    articles: List[Dict],
    poster: BlueSkyPoster,
    db: Database,
    council_lookup: Dict[str, Dict],
    hashtags: List[str],
    council_hashtag_map: Dict[str, str],
    limit: int = 0,
    dry_run: bool = False,
    max_per_council: int = 5,
) -> None:
    """
    Post a list of articles to BlueSky.

    Applies per-council rate limiting (max_per_council), validates each article
    before posting, and marks permanently-rejected articles to prevent retry loops.

    Args:
        articles: Unposted article dicts from the database
        poster: Authenticated BlueSkyPoster instance
        db: Database instance
        council_lookup: Dict mapping council_id -> council config
        hashtags: Base state hashtags to include on every post
        council_hashtag_map: Dict mapping council_id -> canonical council hashtag
        limit: Total post cap for this run (0 = unlimited)
        dry_run: If True, print what would be posted without posting
        max_per_council: Maximum posts per council per run
    """
    if not articles:
        print("No articles to post")
        return

    print(f"Found {len(articles)} unposted articles")

    if limit > 0:
        articles = articles[:limit]
        print(f"Limiting to {limit} posts total")

    if dry_run:
        print("\nDry run - would post:")
        council_counts: Dict[str, int] = {}
        for article in articles:
            c_id = article['council_id']
            if council_counts.get(c_id, 0) >= max_per_council:
                continue
            council_counts[c_id] = council_counts.get(c_id, 0) + 1
            council_name = council_lookup.get(c_id, {}).get('name', c_id)
            print(f"  📰 {council_name}: {article['title']}")
        return

    if not poster.authenticate():
        print("Failed to authenticate with BlueSky")
        return

    posted_count = 0
    council_counts: Dict[str, int] = {}

    for article in articles:
        c_id = article['council_id']
        if council_counts.get(c_id, 0) >= max_per_council:
            print(f"  ⚠️ Skipping {article['title'][:30]}... (Max {max_per_council} posts reached for {c_id})")
            continue

        article_date = None
        if article.get('date'):
            d = article['date']
            if isinstance(d, datetime):
                article_date = d
            else:
                try:
                    article_date = date_parser.parse(str(d))
                except (ValueError, TypeError) as e:
                    print(f"Warning: Failed to parse date '{d}': {e}")

        if not is_valid_article(article):
            print(f"⚠️ Skipping invalid article (metadata/garbage): {article.get('title', 'Unknown')}")
            db.mark_as_rejected(article['url'], "REJECTED_VALIDATION")
            continue

        council_config = council_lookup.get(c_id, {})
        council_name = council_config.get('name', c_id)
        council_tag = council_hashtag_map.get(c_id)

        excerpt = article['excerpt']
        if council_config.get('skip_excerpt'):
            excerpt = None

        tags_for_post = list(hashtags) if hashtags else []
        if council_tag and council_tag not in tags_for_post:
            tags_for_post.append(council_tag)

        # Atomic claim so a concurrent posting process can't send the same
        # article; confirmed by mark_as_posted, rolled back by release_claim.
        if not db.claim_article(article['url']):
            print(f"  ⚠️ Skipping {article['title'][:30]}... (claimed by another process)")
            continue

        try:
            post_uri = poster.post_article(
                council_name,
                article['title'],
                article['url'],
                date=article_date,
                excerpt=excerpt,
                hashtags=tags_for_post,
                council_hashtag=council_tag,
            )
        except TransientPostError as e:
            dead_lettered = db.release_claim(article['url'])
            if dead_lettered:
                print(f"❌ Dead-lettered after {db.MAX_POST_ATTEMPTS} attempts: {article['title'][:50]}")
            print(f"⚠️ Transient posting failure ({e}); stopping this batch — articles stay queued.")
            break

        if post_uri:
            db.mark_as_posted(article['url'], poster.handle)
            posted_count += 1
            council_counts[c_id] = council_counts.get(c_id, 0) + 1
            print(f"✅ Posted: {article['title'][:50]}...")

            if DISCORD_LOGGING:
                try:
                    current_run.log_posted(1)
                except (AttributeError, KeyError, TypeError) as log_err:
                    print(f"Warning: Failed to log run post stats: {log_err}")

            if posted_count < len(articles):
                time.sleep(2)
        else:
            print(f"⚠️ Rejected: {article['title'][:30]}... (permanently skipping)")
            db.mark_as_rejected(article['url'], "REJECTED_POSTER_VALIDATION")

    print(f"\n✅ Posted {posted_count} articles")
