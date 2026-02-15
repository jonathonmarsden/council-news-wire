# Council News Bot - Monitoring & Alerting Guide

**Last Updated**: 15 February 2026  
**Purpose**: Health monitoring, alerting setup, metrics collection  
**Audience**: Ops, DevOps, on-call engineers  

---

## Overview

Bot monitoring uses three layers:
1. **Discord Alerts** — Real-time notifications (failures, summaries)
2. **Health Checks** — Automated periodic verification
3. **Database Metrics** — Article counts, scrape success rates

---

## Discord Alerts

### Alert Channels

- **#council-news-alerts** — Bot notifications (failures, summaries)
- **#council-news-feed** — Posted articles in real-time
- **#council-news-errors** — Detailed error logs (optional)

### Alert Types

#### 🔴 Critical: Scraper Failure (3+ consecutive runs)

**Trigger**: Council returns 0 articles for 3+ runs in a row

**Message**:
```
⚠️ SILENT FAILURE: Joondalup (WA)  
Scraper returned 0 articles for 3 consecutive runs.  
Check selectors or WAF blocking.  
URL: https://www.joondalup.wa.gov.au/news/
```

**Action Required**: 
1. Check council website manually
2. Update CSS selectors in `states/wa/councils.json`
3. Test with `python main.py --state wa --council joondalup --dry-run`
4. Deploy fix

#### 🟡 Warning: Proxy Authentication (407)

**Trigger**: Proxy returns 407 Proxy Authentication Required

**Message**:
```
⚠️ PROXY ERROR: Western Australia  
Tunnel connection failed: 407 Proxy Authentication Required  
Action: Verify "REDACTED-rotate" credentials and IP whitelist
```

**Action Required**:
1. Validate proxy credentials: `curl -x http://REDACTED-rotate:... https://httpbin.org/ip`
2. Check Webshare account status
3. Update `.env` if credentials changed
4. Restart bot: `docker compose restart bot`

#### 🟢 Information: Daily Summary

**Trigger**: Posted after evening scrape

**Message**:
```
📊 Daily Summary: Western Australia (WA)
├─ Councils: 97/97 active
├─ Articles: 342 found, 18 new
├─ Posts: 15 successful
├─ Runtime: 8m 42s
└─ Status: ✅ Healthy
```

**Means**: Bot is working normally

#### 🟠 Error: BlueSky Rate Limited (429)

**Trigger**: Posted 20+ articles in 1 hour

**Message**:
```
⚠️ RATE LIMITED: BlueSky API  
Posted 18/20 articles, then got HTTP 429.  
Backoff: 15 minutes before retrying.
```

**Action**:
- Reduce `--max-per-council` or `--limit` in cron
- Or space out posting with longer delays

---

## Automated Health Checks

### Daily Health Check

**Runs**: 08:00 UTC (after morning scrapes complete)

**Command**:
```bash
python scripts/monitoring/health_check.py --state all
```

**Output**: `reports/health_check_$(date).json`

**Metrics Checked**:
- ✅ DB connectivity
- ✅ Proxy health (test request)
- ✅ BlueSky auth (test login)
- ✅ Articles per state (24-hour count)
- ✅ Scraper success rate (last 7 days)
- ⚠️  Councils with 3+ failures
- ⚠️  Proxy rotation working

**Example Output**:
```json
{
  "timestamp": "2026-02-15T08:15:30Z",
  "database": {"status": "ok", "articles_count": 125432},
  "proxy": {"status": "ok", "response_time_ms": 450},
  "bluesky": {"status": "ok", "authenticated": true},
  "states": {
    "vic": {
      "articles_24h": 342,
      "success_rate": 0.95,
      "failed_councils": []
    }
  },
  "warnings": []
}
```

### Weekly Audit

**Runs**: Monday 09:00 UTC

**Command**:
```bash
python scripts/deployment/check_twice_daily_schedule.py
```

**Checks**:
- ✅ Cron jobs scheduled correctly
- ✅ All states have morning + evening runs
- ✅ Staggering prevents overload
- ✅ Time windows correctly configured

---

## Metrics & Dashboards

### Key Metrics to Monitor

#### Success Rate
```
Success % = (Councils with articles / Total councils) * 100
```
- **Healthy**: >85%
- **Warning**: 70-85%
- **Critical**: <70%

#### Article Throughput
```
Articles/day = Total articles found per state per day
```
- **Expected**: 300-500 per state daily (varies)
- **Warning**: Drop >50% from baseline is suspicious

#### Scrape Latency
```
P95 latency = Time to scrape 95% of councils
```
- **Target**: <10 minutes per state
- **Warning**: >15 minutes (proxy slow, WAF blocking)
- **Critical**: >25 minutes (timeout, no articles)

#### Proxy Response Time
```
Proxy latency = Time to proxy.httpbin.org/ip
```
- **Healthy**: <500ms
- **Warning**: 500-1000ms
- **Critical**: >1000ms or timeouts

### Querying Metrics from Database

```bash
# Articles found in last 24 hours
sqlite3 /opt/council-news-bot/bot.db \
  "SELECT COUNT(*) FROM articles WHERE date > datetime('now', '-1 day');"

# Success rate (councils with articles in last week)
sqlite3 /opt/council-news-bot/bot.db \
  "SELECT 
    COUNT(DISTINCT council_id) as total_councils,
    COUNT(DISTINCT CASE WHEN date > datetime('now', '-7 days') THEN council_id END) as success_councils
   FROM articles;"

# Scrape performance
sqlite3 /opt/council-news-bot/bot.db \
  "SELECT 
    council_id,
    COUNT(*) as run_count,
    CAST(AVG(duration_ms) AS INT) as avg_duration_ms,
    COUNT(CASE WHEN status='error' THEN 1 END) as error_count
   FROM scraper_runs
   WHERE timestamp > datetime('now', '-7 days')
   GROUP BY council_id
   ORDER BY error_count DESC;"
```

---

## Alerting Rules

### Create Custom Alerts

#### Email on Critical Error

```bash
# Add to crontab
0 */4 * * * root /opt/council-news-bot/scripts/monitoring/check_critical_errors.sh
```

**Script** (`scripts/monitoring/check_critical_errors.sh`):
```bash
#!/bin/bash
ERRORS=$(docker logs council_news_bot --since 4h | grep -c "Error\|407\|429")
if [ $ERRORS -gt 10 ]; then
    echo "High error rate ($ERRORS) detected" | \
    mail -s "🔴 Council Bot Alert" ops@example.com
fi
```

#### Slack Integration

```bash
# Send to Slack instead of Discord
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"🔴 Bot Error: Proxy timeout"}' \
  $SLACK_WEBHOOK_URL
```

---

## On-Call Checklist

### Every 4 Hours

- [ ] View Discord #council-news-alerts for new alerts
- [ ] If alert exists, check RUNBOOK.md [Troubleshooting](#troubleshooting-section) 
- [ ] Monitor average latency: should stay <10s per council

### Daily (Start of Shift)

- [ ] View health check from 08:00 UTC
- [ ] Check if any states fell below 80% success rate
- [ ] Review scraper logs: `docker logs council_news_bot --since 24h | grep -i error | wc -l`

### Weekly (Monday)

- [ ] Run: `python scripts/deployment/check_twice_daily_schedule.py`
- [ ] Check cron jobs: `crontab -l | grep council-news-bot`
- [ ] Review failed councils list from health check
- [ ] Update selectors for any with 0-article runs

### Quarterly

- [ ] Review proxy usage/cost with Webshare account
- [ ] Audit article validation rules (garbage content detection)
- [ ] Update RUNBOOK.md with new learnings

---

## Performance Benchmarks

### Healthy Run

**State**: Victoria (140 councils)  
**Duration**: 12-15 minutes  
**Articles Found**: 250-400  
**Success Rate**: 92%  
**Proxy**: <500ms avg per request

### Degraded Run

**State**: Victoria  
**Duration**: 20-25 minutes  
**Articles Found**: 150-250  
**Success Rate**: 70-80%  
**Proxy**: 800-1200ms avg per request  
**Likely Cause**: WAF/proxy slow, some councils timing out

### Critical Status

**State**: Victoria  
**Duration**: >30 minutes or timeout  
**Articles Found**: <50  
**Success Rate**: <60%  
**Proxy**: >1500ms or failing  
**Action**: Check proxy, manually re-scrape state

---

## Monitoring External Dependencies

### Webshare Proxy Health

**Check every 6 hours**:
```bash
# Test rotation (should return different IPs)
IP1=$(curl -s -x http://REDACTED-rotate:REDACTED@proxy.example.com:80 https://httpbin.org/ip | jq -r .origin)
sleep 2
IP2=$(curl -s -x http://REDACTED-rotate:REDACTED@proxy.example.com:80 https://httpbin.org/ip | jq -r .origin)

if [ "$IP1" = "$IP2" ]; then
    echo "⚠️  WARNING: Proxy not rotating (same IP: $IP1)"
else
    echo "✅ Proxy rotating: $IP1 → $IP2"
fi
```

### BlueSky Service Status

**Check daily**:
```bash
# Simple connectivity check
curl -s https://bsky.social/xrpc/com.atproto.server.getSession \
  -H "Authorization: Bearer $(python -c 'from core.poster import BlueSkyPoster; p = BlueSkyPoster(...); print(p.session_token)')" \
  | jq .did
```

### Australian Council Websites

**Monitor**: Watch for major redesigns
- Most use Joomla, Drupal, or WordPress (changes rare)
- WAF blocks (Cloudflare, Akamai) increase after DDoS events
- RSS feeds more stable than HTML scraping

---

## Logs & Debugging

### Docker Logs

```bash
# Last 100 lines
docker logs council_news_bot --tail=100

# Since 1 hour ago
docker logs council_news_bot --since=1h

# Follow in real-time
docker logs -f council_news_bot

# Specific error type
docker logs council_news_bot | grep -i "proxy\|407\|timeout"
```

### Database Logs

```bash
# Recent errors from DB
sqlite3 /opt/council-news-bot/bot.db \
  "SELECT timestamp, council_id, status, error_msg FROM scraper_runs 
   WHERE status='error' 
   ORDER BY timestamp DESC LIMIT 20;"
```

### Enable Debug Logging

```bash
# Edit docker-compose.yml, set LOG_LEVEL=DEBUG
# Or pass at runtime:
docker compose exec -T bot python main.py --state vic --dry-run
# (will print verbose debug output)
```

---

**Last Updated**: 15 February 2026  
**Version**: 1.0  
**Review Cycle**: Quarterly
