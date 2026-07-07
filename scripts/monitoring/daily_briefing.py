#!/usr/bin/env python3
"""
Daily Briefing Script

Generates a 24-hour summary of bot activity and posts it to Discord.
Should be run via cron once per day (e.g., at 9:00 AM).
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select, desc

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.database import Database
from core.models import ScraperStats, Article, CouncilHealth, LogEvent
from discord_logger import DISCORD_WEBHOOK_LOGS, send_discord_embed

# Config
WEBHOOK_URL = DISCORD_WEBHOOK_LOGS

def generate_briefing():
    db = Database()
    session = db.get_session()
    
    # Time window: Last 24 hours. DB timestamps are UTC (server_default
    # func.now() in Postgres); datetime.now() here was container-local Sydney
    # time, silently shrinking "Last 24 Hours" to ~13-14h of data.
    now = datetime.utcnow()
    start_time = now - timedelta(hours=24)
    
    # 1. Total Stats
    stats_query = select(
        func.count(ScraperStats.id).label("total_runs"),
        func.sum(ScraperStats.articles_found).label("total_found"),
        func.sum(ScraperStats.articles_saved).label("total_saved"),
        func.avg(ScraperStats.duration_ms).label("avg_duration")
    ).where(ScraperStats.run_at >= start_time)
    
    stats_result = session.execute(stats_query).first()
    
    # 2. Error Counts (status == 'error')
    error_query = select(func.count(ScraperStats.id)).where(
        ScraperStats.run_at >= start_time,
        ScraperStats.status == 'error'
    )
    error_count = session.execute(error_query).scalar() or 0

    # 2b. Posts by Council
    post_query = select(
        Article.council_id,
        func.count(Article.id).label("posted")
    ).where(Article.posted_at >= start_time)\
     .group_by(Article.council_id)\
     .order_by(desc("posted"))\
     .limit(5)

    top_posted = session.execute(post_query).all()

    # 2c. Warning/Error Events
    event_counts = session.execute(
        select(LogEvent.severity, func.count(LogEvent.id))
        .where(LogEvent.created_at >= start_time)
        .group_by(LogEvent.severity)
    ).all()

    event_map = {row[0]: row[1] for row in event_counts}
    warnings_count = event_map.get("warning", 0)
    errors_count = event_map.get("error", 0)
    
    # 3. Top Councils by Articles Found
    top_councils_query = select(
        ScraperStats.council_id,
        func.sum(ScraperStats.articles_found).label("found")
    ).where(ScraperStats.run_at >= start_time)\
     .group_by(ScraperStats.council_id)\
     .order_by(desc("found"))\
     .limit(5)
     
    top_councils = session.execute(top_councils_query).all()
    
    # 4. Broken Councils (Consecutive Failures > 3)
    broken_query = select(
        CouncilHealth.council_id,
        CouncilHealth.consecutive_failures,
        CouncilHealth.last_failure_at
    ).where(CouncilHealth.consecutive_failures >= 3)
    
    broken_councils = session.execute(broken_query).all()
    
    # 5. Quiet Councils (High Empty Runs)
    quiet_query = select(func.count(CouncilHealth.council_id)).where(
        CouncilHealth.consecutive_empty_runs > 10
    )
    quiet_count = session.execute(quiet_query).scalar() or 0

    # --- Build Report ---
    
    runs = stats_result.total_runs or 0
    found = stats_result.total_found or 0
    # saved = stats_result.total_saved or 0
    avg_dur = f"{(stats_result.avg_duration or 0)/1000:.2f}s"
    
    success_rate = 100
    if runs > 0:
        success_rate = ((runs - error_count) / runs) * 100
        
    color = 3066993 # Green
    if success_rate < 95: color = 15105570 # Orange
    if success_rate < 80: color = 15158332 # Red

    description = (
        f"**Period**: Last 24 Hours\n"
        f"**Success Rate**: {success_rate:.1f}%\n"
        f"**Total Scraper Runs**: {runs}\n"
        f"**Articles Scanned**: {found}\n"
        f"**Avg Scraper Duration**: {avg_dur}\n"
        f"**Warnings / Errors**: {warnings_count} / {errors_count}\n"
    )
    
    fields = []
    
    # Field: Top Activity
    if top_councils:
        top_text = "\n".join([f"• {c.council_id}: {c.found}" for c in top_councils])
        fields.append({
            "name": "📈 Most Active Councils",
            "value": top_text,
            "inline": False
        })

    if top_posted:
        posted_text = "\n".join([f"• {c.council_id}: {c.posted}" for c in top_posted])
        fields.append({
            "name": "📰 Most Posts Published",
            "value": posted_text,
            "inline": False
        })
        
    # Field: Health Issues
    if broken_councils:
        broken_text = "\n".join([f"• {c.council_id} ({c.consecutive_failures} fails)" for c in broken_councils[:10]])
        if len(broken_councils) > 10:
            broken_text += f"\n...and {len(broken_councils)-10} more."
            
        fields.append({
            "name": f"❌ Broken Scrapers ({len(broken_councils)})",
            "value": broken_text,
            "inline": False
        })
        
    if quiet_count > 0:
        fields.append({
             "name": "⚠️ Quiet Councils",
             "value": f"{quiet_count} councils have returned 0 results for >10 runs.",
             "inline": False
        })

    embed = {
        "title": "🌅 Daily Morning Briefing",
        "description": description,
        "color": color,
        "fields": fields,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    send_discord_embed(WEBHOOK_URL, embed, username="Roundup Supervisor")
    session.close()

if __name__ == "__main__":
    generate_briefing()
