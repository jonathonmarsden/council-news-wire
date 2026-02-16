# Discord Webhook Setup - Final Step

## Status: 95% Complete ✅

**What's Done:**
- ✅ Database tables created (`log_events`, `run_summaries`)
- ✅ All logging code deployed and tested
- ✅ Cron schedule updated with hourly briefing
- ✅ System collecting telemetry in database
- ✅ Hourly and daily summary scripts ready

**What's Needed:** Replace placeholder Discord webhook URLs

---

## Quick Setup (2 minutes)

### Step 1: Get Your Discord Webhook URLs

**Option A - Find Existing Webhooks:**
If you already created webhooks, they're in your Discord server:
1. Go to Discord Server Settings → Integrations → Webhooks
2. Copy the webhook URLs for your logs and alerts channels

**Option B - Create New Webhooks:**
1. Right-click your Discord logs channel → Edit Channel
2. Integrations → Webhooks → New Webhook
3. Name: "Council Bot Logs" → Copy Webhook URL
4. Repeat for alerts channel: "Council Bot Alerts"

### Step 2: Update VPS Configuration

SSH to VPS and edit the .env file:
```bash
ssh root@vps.example.com
nano /opt/council-news-bot/.env
```

Find these lines at the bottom:
```
DISCORD_WEBHOOK_LOGS=https://discord.com/api/webhooks/REPLACE_WITH_LOGS_WEBHOOK
DISCORD_WEBHOOK_ALERTS=https://discord.com/api/webhooks/REPLACE_WITH_ALERTS_WEBHOOK
```

Replace with your actual webhook URLs, then save (Ctrl+O, Enter, Ctrl+X).

### Step 3: Restart and Test

```bash
cd /opt/council-news-bot

# Restart to pick up new environment variables
docker compose restart bot

# Test hourly briefing (should post to Discord logs channel)
docker compose run --rm bot python3 scripts/monitoring/hourly_briefing.py

# Check it worked
echo "✅ If you see an embed in Discord logs channel, setup is complete!"
```

---

## What Gets Posted to Discord

### Hourly Briefing (every hour at :00)
- Last hour activity summary
- Number of posts published
- Top 5 councils by activity
- State breakdown
- Warning/error counts

### Daily Briefing (21:00 UTC / 8am AEDT)
- 24-hour health report
- Total posts across all states
- Silent failures detected
- Database status

### Critical Alerts (as they occur)
- Scraper failures (3+ consecutive)
- Database connection issues
- System errors

---

## Verification Commands

```bash
# Check logs are being collected
ssh root@vps.example.com "cd /opt/council-news-bot && docker compose exec -T db psql -U councilbot council_news -c 'SELECT COUNT(*) FROM log_events; SELECT COUNT(*) FROM run_summaries;'"

# View recent cron logs
ssh root@vps.example.com "tail -50 /var/log/council_bot_cron.log"

# Check next hourly briefing time
ssh root@vps.example.com "crontab -l | grep hourly_briefing"
```

---

## Current Configuration

**VPS:** vps.example.com  
**Project:** /opt/council-news-bot  
**Cron:** Active with twice-daily scraping + hourly summaries  
**Database:** PostgreSQL with logging tables  
**Status:** Operational (Discord posting pending webhook URLs)

---

*Last Updated: 2026-02-16*
