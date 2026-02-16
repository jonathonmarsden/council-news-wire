# Deployment Guide

This document outlines the deployment process for the Council News Bot to the DigitalOcean VPS.

## 🚀 Deployment Strategy: GitHub Actions (Primary)

Production deploys are **CI/CD-driven**. The GitHub Actions pipeline is the primary path to production.

**Why**:
1. **Auditable**: Deploys are tied to a commit SHA.
2. **Reproducible**: CI runs the same checks every time.
3. **Safer**: Avoids shipping uncommitted local state.

This ensures that:
1.  **Secrets Management**: Your local `.env` and `deploy_secrets.py` (which are git-ignored) remain secure and are transferred directly.
2.  **State Consistency**: The code running is exactly what you have locally.
3.  **Speed**: No need to manage git credentials or merge conflicts on the server.

## 📋 Prerequisites

To deploy, you need:
1.  **Access to the VPS**: The IP is `vps.example.com`.
2.  **`deploy_secrets.py`**: A file in `scripts/deployment/` containing the VPS credentials.
    ```python
    # scripts/deployment/deploy_secrets.py
    HOST = "vps.example.com"
    USER = "root"
    PASS = "your_vps_password"  
    ```
    *Note: If you have SSH Key access configured in `~/.ssh/config`, you can skip the password file and use the shell script directly.*

## 🛠 How to Deploy

### Option 1: GitHub Actions (Primary)

1. Push to `master`.
2. Ensure **Test & Lint** passes.
3. The **Deploy to VPS** workflow runs automatically.

To trigger manually:
- GitHub → Actions → **Deploy to VPS** → Run workflow.

### Option 2: Emergency Local Deploy (Break Glass)

Only use this if GitHub Actions is unavailable. It requires explicit flags.

```bash
python3 scripts/deployment/deploy_with_password.py --force-local
```

### Option 3: Manual Shell Script (SSH Keys required)

If you have SSH keys set up for `root@vps.example.com`:
1.  Run the shell script directly:
    ```bash
    ./scripts/deployment/deploy_to_vps.sh --force-local
    ```

## � Monitoring

### DigitalOcean Metrics Agent
The VPS has the DigitalOcean Monitoring Agent (`do-agent`) installed and running. This sends system-level metrics back to the DigitalOcean Cloud Console.

**To view metrics:**
1.  Log in to [cloud.digitalocean.com](https://cloud.digitalocean.com).
2.  Navigate to **Droplets**.
3.  Select the **council-news-bot** droplet.
4.  Click on the **Graphs** tab.

**Key Metrics to Watch:**
*   **CPU Usage:** Should typically stay below 80%. Spikes during scheduled scrapes (twice daily) are normal.
*   **Memory Usage:** We have a strict 1GB limit on the Docker container, but the host has 4GB. Watch for lines flatlining at 100% which indicates swapping.
*   **Disk Usage:** Ensure `/` doesn't fill up (logs/database backups).

### Service Status
You can check the agent status on the server:
```bash
systemctl status do-agent
```

## �🔍 Verifying the Deployment

After deployment, verify the bot is running:

1.  **View Logs via Script**:
    ```bash
    # (If implemented)
    python3 scripts/deployment/deploy_with_password.py --logs
    ```
2.  **View Logs Manually**:
    ```bash
    ssh root@vps.example.com 'cd /opt/council-news-bot && docker compose logs -f --tail=50'
    ```
    *   (Or use `sshpass` if needed, see current session history for examples).

## 🆘 Troubleshooting

**"Permission denied" / "Authentication failed":**
*   Check that `scripts/deployment/deploy_secrets.py` exists and has the correct password.
*   Ensure `sshpass` is not conflicting if you are running it manually.

**"rsync error":**
*   Ensure the VPS is reachable (`ping vps.example.com`).
*   Check if disk space is full on the VPS (`df -h` via ssh).

**Bot not posting:**
*   Check `docker compose logs` for errors.
*   Ensure `.env` file was transferred correctly (it is included in the rsync include list).
