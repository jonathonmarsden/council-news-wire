# CI/CD Operations Guide

## Overview
This repository has automated CI/CD workflows for safe, reliable deployments.

## Workflows

### 1. **Test & Lint** (Automatic)
**Trigger:** Push to `master`, `main`, or `develop`  
**Purpose:** Test code quality before deploy  
**What it does:**
- Runs pytest tests (Python 3.9, 3.10, 3.11)
- Lints code (flake8, black, isort)
- Type checks (mypy)
- Security scan (bandit)

**Location:** `.github/workflows/test.yml`

---

### 2. **Deploy to VPS** (Automatic after tests pass)
**Trigger:** Push to `master` (only if tests pass)  
**Purpose:** Deploy code to production  
**What it does:**
1. Waits for Test & Lint to pass
2. Syncs code to VPS via rsync
3. Rebuilds Docker containers
4. Runs post-deploy health check
5. Sends Discord notification (success or failure)

**Location:** `.github/workflows/deploy.yml`

**Manual deploy:** Go to Actions → "Deploy to VPS" → "Run workflow"

---

### 3. **Rollback** (Manual - Emergency Use)
**Trigger:** Manual only  
**Purpose:** Revert to previous working version  
**What it does:**
1. Reverts to previous commit (or specified commit)
2. Deploys old code to VPS
3. Restarts containers
4. Sends Discord alert

**How to use:**
1. Go to Actions → "Rollback" → "Run workflow"
2. Leave commit field **empty** to rollback to previous commit
3. Or enter specific commit SHA to rollback to that version

**Location:** `.github/workflows/rollback.yml`

---

### 4. **Ops Monitoring** (Scheduled Daily)
**Trigger:** Daily at 21:00 UTC (~8am AEDT)  
**Purpose:** Daily health checks and backups  
**What it does:**
1. Runs daily briefing (scraper stats)
2. Generates health report (broken scrapers)
3. Backs up PostgreSQL database (14-day retention)
4. Sends Discord alerts if any step fails
5. Sends success notification if all pass

**Location:** `.github/workflows/ops_monitoring.yml`

**Manual run:** Go to Actions → "Ops Monitoring" → "Run workflow"

---

## GitHub Secrets Required

Configure these in: **Settings → Secrets and variables → Actions**

| Secret Name | Value | Purpose |
|-------------|-------|---------|
| `VPS_HOST` | `vps.example.com` | Production server IP |
| `VPS_USER` | `root` | SSH user |
| `VPS_SSH_KEY` | (Deploy SSH private key) | Authentication |
| `DISCORD_WEBHOOK_ALERTS` | (Discord webhook URL) | Critical alerts |

---

## Normal Workflow

### Making Changes
```bash
# 1. Edit code locally
vim core/something.py

# 2. Test locally
pytest

# 3. Commit and push
git add .
git commit -m "fix: description"
git push origin master

# 4. That's it! CI/CD handles the rest:
#    - Tests run automatically
#    - If tests pass, deploy runs automatically
#    - You get Discord notifications
```

---

## Emergency Procedures

### Deploy Failed - Need Rollback
1. Go to **Actions → Rollback → Run workflow**
2. Leave commit field empty (rolls back to previous)
3. Click "Run workflow"
4. Check Discord for confirmation

### Daily Monitoring Failed
- Check Discord alert (tells you which step failed)
- Go to Actions → workflow run → see logs
- Common fixes:
  - VPS out of disk: SSH in, clean up logs
  - Database locked: Restart containers
  - Network timeout: Re-run workflow manually

### Tests Failing (Blocking Deploy)
- Fix tests first (can't deploy until green)
- Or bypass with manual deploy:
  - Go to Actions → "Deploy to VPS" → "Run workflow"
  - Manual runs skip test gate (use carefully!)

---

## Monitoring

### Where to Check Status
- **GitHub Actions:** https://github.com/jonathonmarsden/council-news-bot/actions
- **Discord:** #council-news-alerts channel
- **VPS directly:** `ssh root@vps.example.com`

### What Gets Monitored
✅ Code quality (tests, lint, type checks)  
✅ Deploy success/failure  
✅ Post-deploy health  
✅ Daily scraper stats  
✅ Database backups  
✅ Container status  

---

## Best Practices

1. **Always push to master** - Don't SSH and edit files on VPS
2. **Check Actions tab** after push - Confirm green checkmarks
3. **Read Discord alerts** - They tell you what failed
4. **Test locally first** - Saves CI/CD time
5. **Use rollback if needed** - Don't panic-edit on VPS

---

## Troubleshooting

**Q: Deploy stuck/hanging?**  
A: Check Actions logs. Likely rsync or Docker build timeout.

**Q: Rollback not working?**  
A: Check you have at least 2 commits. Can't rollback from first commit.

**Q: No Discord notifications?**  
A: Verify `DISCORD_WEBHOOK_ALERTS` secret is set correctly.

**Q: Want to skip tests for urgent fix?**  
A: Use manual deploy (Actions → Deploy to VPS → Run workflow).

**Q: Database backup failing?**  
A: Check VPS disk space: `ssh root@vps.example.com "df -h"`

---

## Further Reading

- [docs/operations/RUNBOOK.md](../docs/operations/RUNBOOK.md) - Daily operations
- [docs/operations/MONITORING.md](../docs/operations/MONITORING.md) - Monitoring guide
- [docs/operations/TROUBLESHOOTING.md](../docs/operations/TROUBLESHOOTING.md) - Common issues
- [docs/architecture/SYSTEM_DESIGN.md](../docs/architecture/SYSTEM_DESIGN.md) - System overview
