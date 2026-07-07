#!/usr/bin/env python3
"""
Pre-deployment validation script.

Runs all checks that the deployment script will perform, but in a more
detailed Python-based format with clear output.

Usage:
    python3 scripts/deployment/validate.py
"""

import json
import sys
from pathlib import Path
from typing import List, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

STATES = ['nsw', 'vic', 'qld', 'tas', 'sa', 'wa', 'nt', 'act']

class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def check_json_validity() -> Tuple[bool, List[str]]:
    """Validate all JSON configuration files."""
    errors = []
    
    for state in STATES:
        state_dir = PROJECT_ROOT / 'states' / state
        if not state_dir.exists():
            continue
            
        # Check councils.json
        councils_file = state_dir / 'councils.json'
        if councils_file.exists():
            try:
                with open(councils_file) as f:
                    data = json.load(f)
                if 'councils' not in data:
                    errors.append(f"{state}/councils.json missing 'councils' key")
            except json.JSONDecodeError as e:
                errors.append(f"{state}/councils.json: {e}")
        
        # Check config.json
        config_file = state_dir / 'config.json'
        if config_file.exists():
            try:
                with open(config_file) as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                errors.append(f"{state}/config.json: {e}")
    
    return len(errors) == 0, errors

def check_python_imports() -> Tuple[bool, List[str]]:
    """Check that all required Python modules can be imported."""
    errors = []
    required_modules = [
        'requests',
        'bs4',
        'atproto',
        'dateutil',
        'dotenv',
        'curl_cffi',
        'lxml',
    ]
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            errors.append(f"Missing module: {module}")
    
    return len(errors) == 0, errors

def check_core_modules() -> Tuple[bool, List[str]]:
    """Check that core bot modules can be imported."""
    errors = []
    
    try:
        from core.scrapers import CardScraper, RSSScraper, ScraperFactory
        from core.database import Database
        from core.poster import BlueSkyPoster
    except Exception as e:
        errors.append(f"Core module import failed: {e}")
        return False, errors
    
    return True, []

def count_enabled_councils() -> Tuple[int, dict]:
    """Count enabled councils per state."""
    state_counts = {}
    total = 0
    
    for state in STATES:
        councils_file = PROJECT_ROOT / 'states' / state / 'councils.json'
        if councils_file.exists():
            try:
                with open(councils_file) as f:
                    data = json.load(f)
                enabled = sum(1 for c in data.get('councils', []) if c.get('enabled', False))
                state_counts[state.upper()] = enabled
                total += enabled
            except:
                state_counts[state.upper()] = 0
    
    return total, state_counts

def check_env_example() -> Tuple[bool, List[str]]:
    """Ensure .env.example doesn't contain real credentials."""
    errors = []
    env_file = PROJECT_ROOT / '.env.example'
    
    if not env_file.exists():
        errors.append(".env.example not found")
        return False, errors
    
    with open(env_file) as f:
        content = f.read()
    
    # Check for dummy placeholders
    if 'xxxx-xxxx-xxxx-xxxx' not in content:
        errors.append(".env.example may contain real credentials")
    
    # Any real-looking BlueSky app password (xxxx-xxxx-xxxx-xxxx format that
    # isn't the literal placeholder) means real credentials leaked in.
    import re
    for match in re.findall(r'\b[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}\b', content):
        if match != 'xxxx-xxxx-xxxx-xxxx':
            errors.append(f".env.example contains a real-looking app password: {match[:4]}-****")
    
    return len(errors) == 0, errors

def check_git_status() -> Tuple[bool, List[str]]:
    """Check if there are uncommitted changes."""
    import subprocess
    
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return False, ["Not a git repository or git not available"]
        
        changes = result.stdout.strip()
        if changes:
            return False, [f"Uncommitted changes:\n{changes}"]
        
        return True, []
    except Exception as e:
        return False, [f"Git check failed: {e}"]

def check_deploy_secrets() -> Tuple[bool, List[str]]:
    """Check if deployment secrets file exists."""
    secrets_file = PROJECT_ROOT / 'scripts' / 'deployment' / 'deploy_secrets.py'
    
    if not secrets_file.exists():
        return False, ["deploy_secrets.py not found"]
    
    try:
        sys.path.insert(0, str(secrets_file.parent))
        from deploy_secrets import HOST, USER, PASS
        
        if not HOST or not USER or not PASS:
            return False, ["deploy_secrets.py has empty credentials"]
        
        return True, []
    except Exception as e:
        return False, [f"Cannot import deploy_secrets: {e}"]

def run_all_checks():
    """Run all validation checks and display results."""
    print(f"{Colors.BLUE}{'='*60}{Colors.NC}")
    print(f"{Colors.BLUE}  Council News Bot - Pre-Deployment Validation{Colors.NC}")
    print(f"{Colors.BLUE}{'='*60}{Colors.NC}\n")
    
    all_passed = True
    
    # Check 1: JSON Validity
    print(f"{Colors.BLUE}[1/7]{Colors.NC} Validating JSON configuration files...")
    passed, errors = check_json_validity()
    if passed:
        print(f"  {Colors.GREEN}✓{Colors.NC} All JSON files are valid")
    else:
        print(f"  {Colors.RED}✗{Colors.NC} JSON validation errors:")
        for error in errors:
            print(f"    - {error}")
        all_passed = False
    
    # Check 2: Python Dependencies
    print(f"\n{Colors.BLUE}[2/7]{Colors.NC} Checking Python dependencies...")
    passed, errors = check_python_imports()
    if passed:
        print(f"  {Colors.GREEN}✓{Colors.NC} All dependencies installed")
    else:
        print(f"  {Colors.RED}✗{Colors.NC} Missing dependencies:")
        for error in errors:
            print(f"    - {error}")
        print(f"\n  {Colors.YELLOW}Fix:{Colors.NC} pip install -r requirements.txt")
        all_passed = False
    
    # Check 3: Core Modules
    print(f"\n{Colors.BLUE}[3/7]{Colors.NC} Testing core module imports...")
    passed, errors = check_core_modules()
    if passed:
        print(f"  {Colors.GREEN}✓{Colors.NC} Core modules load successfully")
    else:
        print(f"  {Colors.RED}✗{Colors.NC} Module import errors:")
        for error in errors:
            print(f"    - {error}")
        all_passed = False
    
    # Check 4: Enabled Councils
    print(f"\n{Colors.BLUE}[4/7]{Colors.NC} Counting enabled councils...")
    total, state_counts = count_enabled_councils()
    if total > 0:
        print(f"  {Colors.GREEN}✓{Colors.NC} {total} councils enabled across all states")
        for state, count in sorted(state_counts.items()):
            if count > 0:
                print(f"    - {state}: {count}")
    else:
        print(f"  {Colors.RED}✗{Colors.NC} No enabled councils found")
        all_passed = False
    
    # Check 5: .env.example
    print(f"\n{Colors.BLUE}[5/7]{Colors.NC} Checking .env.example is sanitized...")
    passed, errors = check_env_example()
    if passed:
        print(f"  {Colors.GREEN}✓{Colors.NC} .env.example contains only dummy credentials")
    else:
        print(f"  {Colors.RED}✗{Colors.NC} .env.example issues:")
        for error in errors:
            print(f"    - {error}")
        all_passed = False
    
    # Check 6: Git Status
    print(f"\n{Colors.BLUE}[6/7]{Colors.NC} Checking git repository status...")
    passed, errors = check_git_status()
    if passed:
        print(f"  {Colors.GREEN}✓{Colors.NC} Working directory is clean")
    else:
        print(f"  {Colors.YELLOW}⚠{Colors.NC} Git status warnings:")
        for error in errors:
            print(f"    {error}")
        # Don't fail on git warnings
    
    # Check 7: Deploy Secrets
    print(f"\n{Colors.BLUE}[7/7]{Colors.NC} Verifying deployment credentials...")
    passed, errors = check_deploy_secrets()
    if passed:
        print(f"  {Colors.GREEN}✓{Colors.NC} Deployment secrets configured")
    else:
        print(f"  {Colors.YELLOW}⚠{Colors.NC} Deploy secrets warnings:")
        for error in errors:
            print(f"    - {error}")
        print(f"\n  {Colors.YELLOW}Note:{Colors.NC} This is only needed for VPS deployment")
    
    # Summary
    print(f"\n{Colors.BLUE}{'='*60}{Colors.NC}")
    if all_passed:
        print(f"{Colors.GREEN}✓ All critical checks passed!{Colors.NC}")
        print(f"\n{Colors.GREEN}Ready to deploy:{Colors.NC}")
        print(f"  ./scripts/deployment/deploy.sh")
        return 0
    else:
        print(f"{Colors.RED}✗ Some checks failed{Colors.NC}")
        print(f"\nPlease fix the errors above before deploying.")
        return 1

if __name__ == '__main__':
    sys.exit(run_all_checks())
