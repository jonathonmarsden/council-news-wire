#!/usr/bin/env python3
"""
Update Remote Crontab
---------------------
Uses credentials from scripts/deployment/deploy_secrets.py to 
apply the crontab_setup.txt found on the remote server.
"""

import sys
import os
import subprocess

# Add deployment dir to path to import secrets
current_dir = os.path.dirname(os.path.abspath(__file__))
deployment_dir = os.path.join(current_dir, '../deployment')
sys.path.append(deployment_dir)

try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    print("Error: Could not import deploy_secrets.")
    sys.exit(1)

def run_ssh_command(command):
    """Run a command via sshpass"""
    full_cmd = [
        "sshpass", "-p", PASS,
        "ssh", "-o", "StrictHostKeyChecking=no",
        f"{USER}@{HOST}",
        command
    ]
    return subprocess.run(full_cmd, capture_output=True, text=True)

def main():
    print(f"Connecting to {USER}@{HOST}...")
    
    # Check if the setup file exists
    remote_file = "/opt/council-news-bot/crontab_setup.txt"
    check_cmd = f"test -f {remote_file} && echo 'exists'"
    res = run_ssh_command(check_cmd)
    
    if "exists" not in res.stdout:
        print(f"Error: {remote_file} not found on server. Did you deploy?")
        sys.exit(1)
        
    # Apply crontab
    print("Applying crontab...")
    apply_cmd = f"crontab {remote_file}"
    res = run_ssh_command(apply_cmd)
    
    if res.returncode != 0:
        print(f"Failed to apply crontab: {res.stderr}")
        sys.exit(1)
        
    print("✅ Crontab updated successfully.")
    
    # Verify
    print("\n--- Current Remote Crontab ---")
    verify_res = run_ssh_command("crontab -l")
    print(verify_res.stdout)

if __name__ == "__main__":
    main()
