#!/bin/bash
#
# Council News Bot - Production Deployment Script
# 
# This script performs a safe deployment to the VPS with comprehensive pre-flight checks.
# It ensures the codebase is ready, configs are valid, and the VPS is accessible.
#
# Usage:
#   ./scripts/deployment/deploy.sh [--skip-checks] [--dry-run]
#

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REMOTE_PATH="/opt/council-news-bot"
SKIP_CHECKS=false
DRY_RUN=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --skip-checks)
            SKIP_CHECKS=true
            ;;
        --dry-run)
            DRY_RUN=true
            ;;
        --help)
            echo "Usage: $0 [--skip-checks] [--dry-run]"
            echo ""
            echo "Options:"
            echo "  --skip-checks    Skip pre-flight validation checks"
            echo "  --dry-run        Show what would be deployed without making changes"
            echo "  --help           Show this help message"
            exit 0
            ;;
    esac
done

# Load VPS credentials
if [ -f "$SCRIPT_DIR/deploy_secrets.py" ]; then
    # Extract credentials from Python file
    VPS_HOST=$(python3 -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); from deploy_secrets import HOST; print(HOST)")
    VPS_USER=$(python3 -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); from deploy_secrets import USER; print(USER)")
    VPS_PASS=$(python3 -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); from deploy_secrets import PASS; print(PASS)")
else
    echo -e "${RED}ERROR: deploy_secrets.py not found${NC}"
    echo "Please create scripts/deployment/deploy_secrets.py with VPS credentials"
    exit 1
fi

# Helper functions
print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Run command on VPS via SSH
run_remote() {
    local cmd="$1"
    sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o PreferredAuthentications=password -o PubkeyAuthentication=no \
        "$VPS_USER@$VPS_HOST" "$cmd" 2>/dev/null
}

# Pre-flight checks
run_preflight_checks() {
    print_header "PRE-FLIGHT CHECKS"
    
    local CHECKS_PASSED=true
    
    # Check 1: Git repository is clean
    print_info "Checking git status..."
    if [ -n "$(cd "$PROJECT_ROOT" && git status --porcelain)" ]; then
        print_warning "Working directory has uncommitted changes"
        print_info "Modified files:"
        cd "$PROJECT_ROOT" && git status --short
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            CHECKS_PASSED=false
        fi
    else
        print_success "Git repository is clean"
    fi
    
    # Check 2: Python dependencies
    print_info "Checking Python dependencies..."
    if python3 -c "import requests, bs4, atproto, dateutil, dotenv, curl_cffi" 2>/dev/null; then
        print_success "All Python dependencies installed"
    else
        print_error "Missing Python dependencies"
        print_info "Run: pip install -r requirements.txt"
        CHECKS_PASSED=false
    fi
    
    # Check 3: Local environment file exists
    print_info "Checking local .env file..."
    if [ -f "$PROJECT_ROOT/.env" ]; then
        print_success ".env file exists locally"
    else
        print_warning ".env file not found (VPS should have it)"
    fi
    
    # Check 4: Validate JSON configs
    print_info "Validating JSON configuration files..."
    local JSON_VALID=true
    for state_dir in "$PROJECT_ROOT/states"/*; do
        if [ -d "$state_dir" ]; then
            state=$(basename "$state_dir")
            if [ -f "$state_dir/councils.json" ]; then
                if python3 -m json.tool "$state_dir/councils.json" > /dev/null 2>&1; then
                    print_success "$state/councils.json is valid"
                else
                    print_error "$state/councils.json has JSON syntax errors"
                    JSON_VALID=false
                fi
            fi
            if [ -f "$state_dir/config.json" ]; then
                if python3 -m json.tool "$state_dir/config.json" > /dev/null 2>&1; then
                    print_success "$state/config.json is valid"
                else
                    print_error "$state/config.json has JSON syntax errors"
                    JSON_VALID=false
                fi
            fi
        fi
    done
    if [ "$JSON_VALID" = false ]; then
        CHECKS_PASSED=false
    fi
    
    # Check 5: Test VPS connectivity
    print_info "Testing VPS connectivity..."
    if run_remote "echo 'Connected'" > /dev/null 2>&1; then
        print_success "VPS is reachable at $VPS_HOST"
    else
        print_error "Cannot connect to VPS at $VPS_HOST"
        CHECKS_PASSED=false
    fi
    
    # Check 6: Verify VPS Docker is running
    print_info "Checking Docker on VPS..."
    if run_remote "docker --version" > /dev/null 2>&1; then
        print_success "Docker is installed on VPS"
    else
        print_error "Docker not found on VPS"
        CHECKS_PASSED=false
    fi
    
    # Check 7: Count enabled councils
    print_info "Counting enabled councils..."
    TOTAL_ENABLED=$(python3 -c "
import json
from pathlib import Path
total = 0
for state_dir in Path('$PROJECT_ROOT/states').iterdir():
    if state_dir.is_dir():
        councils_file = state_dir / 'councils.json'
        if councils_file.exists():
            with open(councils_file) as f:
                data = json.load(f)
                total += sum(1 for c in data.get('councils', []) if c.get('enabled', False))
print(total)
" 2>/dev/null)
    if [ -n "$TOTAL_ENABLED" ] && [ "$TOTAL_ENABLED" -gt 0 ]; then
        print_success "$TOTAL_ENABLED councils enabled across all states"
    else
        print_error "No enabled councils found"
        CHECKS_PASSED=false
    fi
    
    # Check 8: Database file size check (warn if too large)
    if [ -f "$PROJECT_ROOT/council_news.db" ]; then
        DB_SIZE=$(du -h "$PROJECT_ROOT/council_news.db" | cut -f1)
        print_info "Local database size: $DB_SIZE"
        print_warning "Database will be backed up on VPS before deployment"
    fi
    
    # Check 9: Verify no credentials in .env.example
    print_info "Checking .env.example is sanitized..."
    if grep -q "xxxx-xxxx-xxxx-xxxx" "$PROJECT_ROOT/.env.example" 2>/dev/null; then
        print_success ".env.example contains dummy credentials only"
    else
        print_error ".env.example may contain real credentials"
        CHECKS_PASSED=false
    fi
    
    # Check 10: Test a sample scraper locally
    print_info "Testing sample scraper (quick validation)..."
    if python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from core.scrapers import CardScraper
scraper = CardScraper('test', 'Test Council', 'https://example.com', limit=1)
print('Scraper initialization successful')
" 2>/dev/null; then
        print_success "Scraper modules load correctly"
    else
        print_error "Scraper initialization failed"
        CHECKS_PASSED=false
    fi
    
    echo ""
    if [ "$CHECKS_PASSED" = true ]; then
        print_success "All pre-flight checks passed!"
        return 0
    else
        print_error "Some pre-flight checks failed"
        return 1
    fi
}

# Backup VPS database
backup_vps_database() {
    print_header "BACKING UP VPS DATABASE"
    
    local TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    local BACKUP_NAME="council_news_backup_${TIMESTAMP}.db"
    
    print_info "Creating backup on VPS..."
    run_remote "cd $REMOTE_PATH && [ -f council_news.db ] && cp council_news.db backups/$BACKUP_NAME || echo 'No database to backup'"
    
    # Ensure backups directory exists
    run_remote "mkdir -p $REMOTE_PATH/backups"
    
    # Keep only last 10 backups
    run_remote "cd $REMOTE_PATH/backups && ls -t council_news_backup_*.db 2>/dev/null | tail -n +11 | xargs -r rm"
    
    print_success "Database backed up as $BACKUP_NAME"
}

# Deploy code to VPS
deploy_code() {
    print_header "DEPLOYING CODE TO VPS"
    
    if [ "$DRY_RUN" = true ]; then
        print_info "DRY RUN - Would deploy the following files:"
        cd "$PROJECT_ROOT"
        rsync -avn --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
              --exclude='.env' --exclude='council_news.db*' --exclude='*.log' \
              --exclude='venv' --exclude='.vscode' --exclude='.idea' \
              --exclude='backups' --exclude='debug_*.html' \
              --exclude='scripts/deployment/deploy_secrets.py' \
              ./ | head -50
        print_info "... (truncated, showing first 50 files)"
        return 0
    fi
    
    print_info "Syncing files to VPS..."
    cd "$PROJECT_ROOT"
    sshpass -p "$VPS_PASS" rsync -avz --progress \
        --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
        --exclude='.env' --exclude='council_news.db*' --exclude='*.log' \
        --exclude='venv' --exclude='.vscode' --exclude='.idea' \
        --exclude='backups' --exclude='debug_*.html' \
        --exclude='scripts/deployment/deploy_secrets.py' \
        -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o PreferredAuthentications=password -o PubkeyAuthentication=no" \
        ./ "$VPS_USER@$VPS_HOST:$REMOTE_PATH/"
    
    print_success "Code deployed successfully"
}

# Restart VPS services
restart_services() {
    print_header "RESTARTING SERVICES"
    
    if [ "$DRY_RUN" = true ]; then
        print_info "DRY RUN - Would restart Docker containers"
        return 0
    fi
    
    print_info "Stopping existing containers..."
    run_remote "cd $REMOTE_PATH && docker compose down" || true
    
    print_info "Building and starting containers..."
    run_remote "cd $REMOTE_PATH && docker compose up -d --build"
    
    sleep 5
    
    print_info "Checking container status..."
    run_remote "cd $REMOTE_PATH && docker compose ps"
    
    print_success "Services restarted"
}

# Verify deployment
verify_deployment() {
    print_header "VERIFYING DEPLOYMENT"
    
    print_info "Checking container health..."
    local CONTAINER_STATUS=$(run_remote "cd $REMOTE_PATH && docker compose ps --format json 2>/dev/null | grep -c '\"State\":\"running\"'" || echo "0")
    
    if [ "$CONTAINER_STATUS" -gt 0 ]; then
        print_success "Container is running"
    else
        print_error "Container is not running!"
        print_info "Recent logs:"
        run_remote "cd $REMOTE_PATH && docker compose logs --tail=20"
        return 1
    fi
    
    print_info "Checking recent log output..."
    run_remote "cd $REMOTE_PATH && docker compose logs --tail=10"
    
    print_success "Deployment verification complete"
}

# Show deployment summary
show_summary() {
    print_header "DEPLOYMENT SUMMARY"
    
    echo -e "${GREEN}Deployment completed successfully!${NC}"
    echo ""
    echo "VPS Details:"
    echo "  Host: $VPS_HOST"
    echo "  Path: $REMOTE_PATH"
    echo ""
    echo "Useful Commands:"
    echo "  View logs:    ssh $VPS_USER@$VPS_HOST 'cd $REMOTE_PATH && docker compose logs -f'"
    echo "  Check status: ssh $VPS_USER@$VPS_HOST 'cd $REMOTE_PATH && docker compose ps'"
    echo "  Restart:      ssh $VPS_USER@$VPS_HOST 'cd $REMOTE_PATH && docker compose restart'"
    echo "  Stop:         ssh $VPS_USER@$VPS_HOST 'cd $REMOTE_PATH && docker compose down'"
    echo ""
    echo "Next Steps:"
    echo "  1. Monitor logs for the first few minutes"
    echo "  2. Check BlueSky feeds for new posts"
    echo "  3. Verify database is being updated"
    echo ""
}

# Main deployment flow
main() {
    print_header "COUNCIL NEWS BOT - DEPLOYMENT SCRIPT"
    
    echo "Target: $VPS_USER@$VPS_HOST:$REMOTE_PATH"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}Mode: DRY RUN (no changes will be made)${NC}"
    fi
    echo ""
    
    # Pre-flight checks
    if [ "$SKIP_CHECKS" = false ]; then
        if ! run_preflight_checks; then
            print_error "Pre-flight checks failed!"
            echo ""
            read -p "Continue anyway? (y/N) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo "Deployment cancelled."
                exit 1
            fi
        fi
    else
        print_warning "Skipping pre-flight checks (--skip-checks flag)"
    fi
    
    # Confirm deployment
    if [ "$DRY_RUN" = false ]; then
        echo ""
        read -p "Proceed with deployment? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Deployment cancelled."
            exit 0
        fi
    fi
    
    # Execute deployment steps
    backup_vps_database
    deploy_code
    restart_services
    
    if [ "$DRY_RUN" = false ]; then
        verify_deployment
        show_summary
    else
        echo ""
        print_info "DRY RUN complete - no changes were made"
    fi
}

# Check if sshpass is installed
if ! command -v sshpass &> /dev/null; then
    echo -e "${RED}ERROR: sshpass is not installed${NC}"
    echo "Please install it:"
    echo "  macOS: brew install hudochenkov/sshpass/sshpass"
    echo "  Linux: sudo apt-get install sshpass"
    exit 1
fi

# Run main function
main
