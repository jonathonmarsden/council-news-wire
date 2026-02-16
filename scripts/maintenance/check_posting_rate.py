#!/usr/bin/env python3
"""
Check Posting Rate Metrics
--------------------------
Calculate actual posting rates for the last 7 days and identify current backlog.
Used to tune rate limiting settings.

Usage:
    python3 scripts/maintenance/check_posting_rate.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from core.database import get_session, Article
from sqlalchemy import func

def main():
    session = get_session()
    
    # Last 7 days posting rate
    seven_days_ago = datetime.now() - timedelta(days=7)
    week_count = session.query(func.count(Article.id)).filter(
        Article.posted == True,
        Article.posted_at >= seven_days_ago
    ).scalar()
    
    # Last 24 hours
    day_ago = datetime.now() - timedelta(days=1)
    day_count = session.query(func.count(Article.id)).filter(
        Article.posted == True,
        Article.posted_at >= day_ago
    ).scalar()
    
    # Current backlog
    backlog = session.query(func.count(Article.id)).filter(
        Article.posted == False,
        Article.is_valid == True
    ).scalar()
    
    print('=' * 60)
    print('POSTING METRICS REPORT')
    print('=' * 60)
    print()
    print('OVERALL SYSTEM:')
    print(f'  Last 24 hours:  {day_count:4d} posts  ({day_count/24:5.1f} per hour)')
    print(f'  Last 7 days:    {week_count:4d} posts  ({week_count/7:5.1f} per day, {week_count/(7*24):5.1f} per hour)')
    print(f'  Current backlog: {backlog:4d} articles')
    print()
    
    # Calculate theoretical capacity
    # 8 states × 24 posts/hour = 192 posts/hour max
    # Current limit: 2 posts per 10-min run = 12 posts/hour per state = 96 posts/hour system
    current_utilization = (week_count / (7 * 24)) / 96 * 100 if week_count > 0 else 0
    
    print('CAPACITY ANALYSIS:')
    print(f'  Current limit:       2 posts per run (12/hr per state, 96/hr system)')
    print(f'  BlueSky API limit:   24 posts/hour per state (192/hr system)')
    print(f'  Current utilization: {current_utilization:.1f}% of configured capacity')
    print()
    
    print('BY STATE (Last 7 Days):')
    print('-' * 60)
    
    states = ['NSW', 'VIC', 'QLD', 'SA', 'WA', 'TAS', 'NT', 'ACT']
    state_data = []
    
    for state in states:
        count = session.query(func.count(Article.id)).filter(
            Article.posted == True,
            Article.posted_at >= seven_days_ago,
            Article.state == state
        ).scalar()
        
        state_backlog = session.query(func.count(Article.id)).filter(
            Article.posted == False,
            Article.is_valid == True,
            Article.state == state
        ).scalar()
        
        state_data.append({
            'state': state,
            'count': count,
            'backlog': state_backlog
        })
        
        posts_per_day = count / 7
        posts_per_hour = count / (7 * 24)
        utilization = (posts_per_hour / 12) * 100 if posts_per_hour > 0 else 0
        
        print(f'{state:>4}: {count:4d} posts ({posts_per_day:5.1f}/day, {posts_per_hour:4.1f}/hr) '
              f'| Backlog: {state_backlog:4d} | Util: {utilization:5.1f}%')
    
    session.close()
    
    print()
    print('=' * 60)
    print('RECOMMENDATION:')
    print('=' * 60)
    
    avg_hourly = week_count / (7 * 24)
    
    if current_utilization < 30:
        print('✅ Very low utilization. Can safely increase --limit to 4 (24/hr).')
        print('   This would increase system capacity from 96/hr to 192/hr.')
    elif current_utilization < 60:
        print('✅ Low utilization. Can increase --limit to 3 (18/hr per state).')
        print('   This would increase system capacity from 96/hr to 144/hr.')
    elif current_utilization < 80:
        print('⚠️  Moderate utilization. Can cautiously increase --limit to 3.')
        print('   Monitor for 24h after change to ensure no 429 errors.')
    else:
        print('🚨 High utilization. Current settings are near optimal.')
        print('   Do NOT increase limit without adding more BlueSky accounts.')
    
    print()
    print(f'Current avg rate: {avg_hourly:.1f} posts/hour')
    print(f'If changed to --limit 3: Est ~{avg_hourly * 1.5:.0f} posts/hour')
    print(f'If changed to --limit 4: Est ~{avg_hourly * 2:.0f} posts/hour')
    print()

if __name__ == '__main__':
    main()
