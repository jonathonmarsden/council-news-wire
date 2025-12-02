#!/bin/bash

# Setup script for Ubuntu/Debian VPS (e.g. DigitalOcean)
# Run this as root

set -e

echo "=== Council Bot VPS Setup ==="

# 1. Update System
echo "Updating system packages..."
apt-get update && apt-get upgrade -y

# 2. Install Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
else
    echo "Docker already installed."
fi

# 3. Install Docker Compose (if not part of docker cli)
# Modern docker includes 'docker compose'
echo "Verifying Docker Compose..."
docker compose version || echo "Warning: 'docker compose' not found. You might need to install the plugin."

# 4. Create Project Directory
PROJECT_DIR="/opt/council-news-bot"
echo "Creating project directory at $PROJECT_DIR..."
mkdir -p $PROJECT_DIR
mkdir -p $PROJECT_DIR/data
mkdir -p $PROJECT_DIR/logs

# 5. Permissions
# Assuming we run as root for simplicity on a droplet, but ideally we'd use a user.
# For now, we'll just ensure the directories are writable.
chmod -R 755 $PROJECT_DIR
chmod -R 777 $PROJECT_DIR/data
chmod -R 777 $PROJECT_DIR/logs

echo "=== Setup Complete ==="
echo "Next steps:"
echo "1. Copy your project files to $PROJECT_DIR"
echo "2. Create your .env file in $PROJECT_DIR/.env"
echo "3. Run 'docker compose up -d --build'"
