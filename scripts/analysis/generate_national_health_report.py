import json
import csv
import sys
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent.parent

def parse_date(date_str):
    try:
        # Format: 2025-12-04 01:32:16
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None

def analyze_health():
    # 1. Load Remote Stats
    db_stats = {} # council_id -> {count, last_seen, state}
    filename = 'remote_db_stats_v2.csv'
    if not Path(filename).exists():
        filename = 'remote_db_stats.csv'
        
    with open(filename, 'r') as f:
        reader = csv.reader(f, delimiter='|')
        for row in reader:
            if len(row) < 4: continue
            cid = row[0]
            try:
                count = int(row[1])
                last_seen = parse_date(row[2])
                state = row[3]
                db_stats[cid] = {
                    'count': count,
                    'last_seen': last_seen,
                    'is_recent': False
                }
            except ValueError:
                continue

    # Define "Recent" as within the last 30 days
    # Current simulation date is 2026-01-21
    CURRENT_DATE = datetime(2026, 1, 21)
    dataset_cutoff = CURRENT_DATE - timedelta(days=45) 

    # 2. Iterate Configs
    root_dir = Path("states")
    states = sorted([d.name for d in root_dir.iterdir() if d.is_dir() and not d.name.startswith('_')])
    
    report_data = {
        'states': {},
        'global': {
            'total_councils': 0,
            'enabled_count': 0,
            'disabled_count': 0,
            'healthy_count': 0,
            'stale_count': 0,
            'broken_count': 0, # Enabled but 0 articles
            'zombie_count': 0, # Enabled but not seen recently
        }
    }

    print(f"Generating National Health Report (Ref Date: {CURRENT_DATE.date()})")
    print(f"Stale Cutoff: {dataset_cutoff.date()}\n")

    for state in states:
        config_path = root_dir / state / "councils.json"
        if not config_path.exists(): continue
        
        with open(config_path, 'r') as f:
            councils = json.load(f).get('councils', [])
            
        state_metrics = {
            'total': len(councils),
            'enabled': 0,
            'disabled': 0,
            'healthy': 0,
            'stale': 0, # Has articles, but old
            'broken': 0, # 0 articles ever
            'details': []
        }
        
        for c in councils:
            cid = c['id']
            is_enabled = c.get('enabled', True)
            stats = db_stats.get(cid)
            
            status = "UNKNOWN"
            note = ""
            
            if not is_enabled:
                state_metrics['disabled'] += 1
                status = "DISABLED"
                note = c.get('disabled_reason', 'No reason')
            else:
                state_metrics['enabled'] += 1
                if not stats:
                    state_metrics['broken'] += 1
                    status = "BROKEN_NO_DATA"
                    note = "Enabled but never scraped"
                else:
                    last_seen = stats['last_seen']
                    count = stats['count']
                    
                    if count == 0:
                        state_metrics['broken'] += 1
                        status = "BROKEN_ZERO_COUNT"
                    elif last_seen and last_seen < dataset_cutoff:
                        state_metrics['stale'] += 1
                        status = "STALE"
                        days_ago = (CURRENT_DATE - last_seen).days
                        note = f"Last seen {days_ago} days ago"
                    else:
                        state_metrics['healthy'] += 1
                        status = "HEALTHY"
                        if last_seen:
                             days_ago = (CURRENT_DATE - last_seen).days
                             note = f"Last seen {days_ago} days ago"

            state_metrics['details'].append({
                'id': cid,
                'status': status,
                'note': note,
                'last_seen': str(stats['last_seen']) if stats else 'Never'
            })

            # Add to global
            if status == "HEALTHY": report_data['global']['healthy_count'] += 1
            if status == "STALE": report_data['global']['stale_count'] += 1
            if "BROKEN" in status: report_data['global']['broken_count'] += 1
            
        
        report_data['states'][state] = state_metrics
        report_data['global']['total_councils'] += state_metrics['total']
        report_data['global']['enabled_count'] += state_metrics['enabled']
        report_data['global']['disabled_count'] += state_metrics['disabled']

        # Print State Summary
        s = state_metrics
        print(f"=== {state.upper()} ===")
        print(f"  Coverage: {s['total']} Councils")
        print(f"  Health:   {s['healthy']} Healthy | {s['stale']} Stale | {s['broken']} Broken | {s['disabled']} Disabled")
        rate = (s['healthy'] / s['enabled'] * 100) if s['enabled'] > 0 else 0
        print(f"  Success Rate (of enabled): {rate:.1f}%")
        
        if s['broken'] > 0:
            print(f"  ⚠️  {s['broken']} BROKEN (Enabled but 0 yield):")
            broken_list = [d['id'] for d in s['details'] if 'BROKEN' in d['status']]
            # Print chunks of 5
            for i in range(0, len(broken_list), 5):
                print(f"      {', '.join(broken_list[i:i+5])}")
                
        if s['stale'] > 0:
             print(f"  ⚠️  {s['stale']} STALE (Has data, but nothing recent):")
             stale_list = [f"{d['id']} ({d['note']})" for d in s['details'] if d['status'] == 'STALE']
             # Print first 5
             for item in stale_list[:5]:
                 print(f"      {item}")
             if len(stale_list) > 5: print(f"      ... and {len(stale_list)-5} more")

        print("")

    g = report_data['global']
    print("=== NATIONAL SUMMARY ===")
    print(f"Total Councils: {g['total_councils']}")
    print(f"Enabled: {g['enabled_count']}")
    print(f"Disabled: {g['disabled_count']}")
    print(f"Healthy: {g['healthy_count']}")
    print(f"Issues: {g['stale_count'] + g['broken_count']} (Stale: {g['stale_count']}, Broken: {g['broken_count']})")
    
    overall_health = g['healthy_count'] / g['total_councils'] * 100
    print(f"Overall Network Health: {overall_health:.1f}%")

    # Generate Markdown Report
    report_path = PROJECT_ROOT / "docs" / f"HEALTH_REPORT_{CURRENT_DATE.strftime('%Y_%m_%d')}.md"
    backlog_path = PROJECT_ROOT / "docs" / "BROKEN_COUNCILS_BACKLOG.md"
    
    with open(report_path, 'w') as f:
        f.write(f"# National Health Report ({CURRENT_DATE.date()})\n\n")
        f.write(f"**Overall Health**: {overall_health:.1f}%\n")
        f.write(f"**Healthy**: {g['healthy_count']} | **Issues**: {g['stale_count'] + g['broken_count']}\n\n")
        
        f.write("## State Summary\n\n")
        f.write("| State | Total | Healthy | Broken (0 Yield) | Stale (>45 days) | Disabled |\n")
        f.write("|---|---|---|---|---|---|\n")
        for state, s in report_data['states'].items():
            f.write(f"| {state.upper()} | {s['total']} | {s['healthy']} | {s['broken']} | {s['stale']} | {s['disabled']} |\n")
    
    print(f"\nReport written to {report_path}")

    with open(backlog_path, 'w') as f:
        f.write("# Broken & Stale Councils Backlog\n\n")
        f.write("List of councils requiring attention. Generated automatically.\n\n")
        
        for state, s in report_data['states'].items():
            issues = [d for d in s['details'] if d['status'] in ['BROKEN_NO_DATA', 'BROKEN_ZERO_COUNT', 'STALE']]
            if not issues: continue
            
            f.write(f"## {state.upper()} ({len(issues)})\n")
            for i in issues:
                icon = "💀" if "BROKEN" in i['status'] else "🕰️"
                f.write(f"- {icon} **{i['id']}**: {i['status']} ({i.get('note', '')})\n")
            f.write("\n")
            
    print(f"Backlog written to {backlog_path}")

if __name__ == "__main__":
    analyze_health()
