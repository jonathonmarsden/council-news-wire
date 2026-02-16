#!/usr/bin/env python3
"""
Hourly Briefing Script

Generates a 60-minute summary of bot activity and posts it to Discord.
Designed to run via cron every hour.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import func, select, desc, or_

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.database import Database
from core.models import Article, ScraperStats, CouncilHealth, LogEvent
from discord_logger import DISCORD_WEBHOOK_LOGS, send_discord_embed

WEBHOOK_URL = DISCORD_WEBHOOK_LOGS


def generate_hourly_briefing():
    db = Database()
    session = db.get_session()

    now = datetime.utcnow()
    start_time = now - timedelta(hours=1)

    # Posts in the last hour
    total_posts = session.execute(
        select(func.count(Article.id)).where(Article.posted_at >= start_time)
    ).scalar() or 0

    top_councils = session.execute(
        select(Article.council_id, func.count(Article.id).label("count"))
        .where(Article.posted_at >= start_time)
        .group_by(Article.council_id)
        .order_by(desc("count"))
        .limit(5)
    ).all()

    state_posts = session.execute(
        select(Article.state, func.count(Article.id).label("count"))
        .where(Article.posted_at >= start_time)
        .group_by(Article.state)
        .order_by(desc("count"))
    ).all()

    # Scraper runs in the last hour
    run_stats = session.execute(
        select(
            func.count(ScraperStats.id).label("runs"),
            func.avg(ScraperStats.duration_ms).label("avg_duration")
        ).where(ScraperStats.run_at >= start_time)
    ).first()

    error_runs = session.execute(
        select(func.count(ScraperStats.id))
        .where(ScraperStats.run_at >= start_time, ScraperStats.status == "error")
    ).scalar() or 0

    runs = run_stats.runs or 0
    avg_duration_ms = run_stats.avg_duration or 0
    avg_duration = f"{avg_duration_ms / 1000:.2f}s"

    # Structured warnings/errors in the last hour
    event_counts = session.execute(
        select(LogEvent.severity, func.count(LogEvent.id))
        .where(LogEvent.created_at >= start_time)
        .group_by(LogEvent.severity)
    ).all()

    event_map = {row[0]: row[1] for row in event_counts}
    warnings_count = event_map.get("warning", 0)
    errors_count = event_map.get("error", 0)

    # Health issues (persistent failures or empty runs)
    health_issues = session.execute(
        select(
            CouncilHealth.council_id,
            CouncilHealth.consecutive_failures,
            CouncilHealth.consecutive_empty_runs,
        ).where(
            or_(
                CouncilHealth.consecutive_failures >= 3,
                CouncilHealth.consecutive_empty_runs >= 3,
            )
        )
        .order_by(desc(CouncilHealth.consecutive_failures))
        .limit(10)
    ).all()

    session.close()

    success_rate = 100.0
    if runs > 0:
        success_rate = ((runs - error_runs) / runs) * 100

    color = 3066993
    if warnings_count > 0:
        color = 15105570
    if errors_count > 0:
        color = 15158332

    description = (
        f"**Period**: Last 60 minutes\n"
        f"**Posts Published**: {total_posts}\n"
        f"**Scraper Runs**: {runs}\n"
        f"**Success Rate**: {success_rate:.1f}%\n"
        f"**Avg Scraper Duration**: {avg_duration}\n"
        f"**Warnings / Errors**: {warnings_count} / {errors_count}"
    )

    fields = []

    if state_posts:
        state_text = "\n".join([f"• {row.state.upper()}: {row.count}" for row in state_posts])
        fields.append({
            "name": "🗺️ Posts by State",
            "value": state_text,
            "inline": False,
        })

    if top_councils:
        top_text = "\n".join([f"• {row.council_id}: {row.count}" for row in top_councils])
        fields.append({
            "name": "🏛️ Top Councils (Posts)",
            "value": top_text,
            "inline": False,
        })

    if health_issues:
        issue_lines = []
        for row in health_issues:
            fail = row.consecutive_failures
            empty = row.consecutive_empty_runs
            issue_lines.append(f"• {row.council_id}: {fail} fails, {empty} empty")
        fields.append({
            "name": "⚠️ Persistent Issues",
            "value": "\n".join(issue_lines),
            "inline": False,
        })

    embed = {
        "title": "🧾 Hourly Activity Summary",
        "description": description,
        "color": color,
        "fields": fields,
        "timestamp": datetime.utcnow().isoformat(),
    }

    send_discord_embed(WEBHOOK_URL, embed, username="Roundup Supervisor")


if __name__ == "__main__":
    generate_hourly_briefing()
