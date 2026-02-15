#!/bin/bash
# Install the monitoring cron job on the VPS

CRON_SRC="scripts/deployment/quiet_check.cron"
CRON_DEST="/etc/cron.d/council_quiet_check"

if [ -f "$CRON_SRC" ]; then
    echo "Installing cron job to $CRON_DEST..."
    cp "$CRON_SRC" "$CRON_DEST"
    chmod 644 "$CRON_DEST"
    chown root:root "$CRON_DEST"
    echo "Cron job installed."
else
    echo "Error: Cron source file not found at $CRON_SRC"
    exit 1
fi
