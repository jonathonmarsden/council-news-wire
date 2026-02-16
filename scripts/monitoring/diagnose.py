#!/usr/bin/env python3
import sys
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import func, select, desc

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from core.database import Database
    from core.models import ScraperStats, Article, CouncilHealth, LogEvent
except ImportError as e:
    print(f"Error importing core modules: {e}")
    sys.exit(1)

def diagnose():
    try:
        db = Database()
        session = db.get_session()
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return

    print("--- Council News Bot Diagnosis ---")
    print(f"Time: {datetime.now()}")

    # Time window: Last 24 hours
    now = datetime.now()
    start_time = now - timedelta(hours=24)
    print(f"Analyzing data since: {start_time}")

    # 1. Total Stats
    try:
        stats_query = select(
            func.count(ScraperStats.id).label("total_runs"),
            func.sum(ScraperStats.articles_found).label("total_found"),
            func.sum(ScraperStats.articles_saved).label("total_saved"),
            func.avg(ScraperStats.duration_ms).label("avg_duration")
        ).where(ScraperStats.run_at >= start_time)
        
        stats_result = session.execute(stats_query).first()
        
        runs = stats_result.total_runs or 0
        found = stats_result.total_found or 0
        saved = stats_result.total_saved or 0 # Note: The original script commented this out, but I'll check it
        avg_dur = f"{(stats_result.avg_duration or 0)/1000:.2f}s"
        
        # 2. Error Counts (status == 'error')
        error_query = select(func.count(ScraperStats.id)).where(
            ScraperStats.run_at >= start_time,
            ScraperStats.status == 'error'
        )
        error_count = session.execute(error_query).scalar() or 0

        success_rate = 100
        if runs > 0:
            success_rate = ((runs - error_count) / runs) * 100

        print(f"\n[Performance]")
        print(f"Total Runs: {runs}")
        print(f"Success Rate: {success_rate:.1f}%")
        print(f"Articles Found: {found}")
        print(f"Articles Saved: {saved}")
        print(f"Avg Duration: {avg_dur}")
        print(f"Errors: {error_count}")
        
    except Exception as e:
        print(f"Error querying stats: {e}")

    # 3. Broken Councils
    try:
        broken_query = select(
            CouncilHealth.council_id,
            CouncilHealth.consecutive_failures,
            CouncilHealth.last_failure_at
        ).where(CouncilHealth.consecutive_failures >= 3)
        
        broken_councils = session.execute(broken_query).all()
        
        print(f"\n[Broken Scrapers] ({len(broken_councils)})")
        if broken_councils:
            for c in broken_councils:
                print(f" - {c.council_id}: {c.consecutive_failures} fails (Last: {c.last_failure_at})")
        else:
            print(" - None")
            
    except Exception as e:
        print(f"Error querying broken councils: {e}")

    # 4. Quiet Councils
    try:
        quiet_query = select(func.count(CouncilHealth.council_id)).where(
            CouncilHealth.consecutive_empty_runs > 10
        )
        quiet_count = session.execute(quiet_query).scalar() or 0
        print(f"\n[Quiet Councils] (>10 empty runs)")
        print(f"Count: {quiet_count}")
        
    except Exception as e:
        print(f"Error querying quiet councils: {e}")

    # 5. Recent Logs (Warnings/Errors)
    try:
        log_query = select(
            LogEvent.severity,
            LogEvent.message,
            LogEvent.created_at,
            LogEvent.source
        ).where(
            LogEvent.created_at >= start_time,
            LogEvent.severity.in_(['warning', 'error'])
        ).order_by(desc(LogEvent.created_at)).limit(10)
        
        logs = session.execute(log_query).all()
        
        print(f"\n[Recent Warnings/Errors] (Last 10)")
        if logs:
            for l in logs:
                print(f" - [{l.created_at}] [{l.severity.upper()}] {l.source}: {l.message}")
        else:
            print(" - None")

    except Exception as e:
        print(f"Error querying logs: {e}")

    session.close()

if __name__ == "__main__":
    diagnose()
