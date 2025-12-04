import pty
import os
import sys
import time

# Add project root to path to allow importing deploy_secrets
# Current file is in scripts/maintenance/
# We need to go up 2 levels to get to project root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

try:
    from scripts.deployment.deploy_secrets import HOST, USER, PASS
except ImportError:
    print("Error: Could not import deploy_secrets. Make sure scripts/deployment/deploy_secrets.py exists.")
    sys.exit(1)

def read(fd):
    return os.read(fd, 1024)

def run_command(cmd_list):
    print(f"\n=== Running: {' '.join(cmd_list)} ===")
    pid, fd = pty.fork()
    
    if pid == 0:
        # Child process
        os.execvp(cmd_list[0], cmd_list)
    else:
        # Parent process
        try:
            while True:
                try:
                    output = read(fd).decode(errors='ignore')
                    if not output:
                        break
                    sys.stdout.write(output)
                    sys.stdout.flush()
                    
                    if "password:" in output.lower():
                        time.sleep(0.5)
                        os.write(fd, (PASS + "\n").encode())
                        
                except OSError:
                    break
        except Exception as e:
            print(f"Error: {e}")
        finally:
            os.close(fd)
            os.waitpid(pid, 0)

def main():
    # 1. SCP the file
    scp_cmd = [
        "scp",
        "-o", "PreferredAuthentications=password",
        "-o", "PubkeyAuthentication=no",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "scripts/maintenance/fix_cairns_urls.py",
        f"{USER}@{HOST}:/opt/council-news-bot/scripts/maintenance/"
    ]
    run_command(scp_cmd)
    
    # 2. SSH to run it
    ssh_cmd = [
        "ssh",
        "-o", "PreferredAuthentications=password",
        "-o", "PubkeyAuthentication=no",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        f"{USER}@{HOST}",
        "cd /opt/council-news-bot && python3 scripts/maintenance/fix_cairns_urls.py"
    ]
    run_command(ssh_cmd)

if __name__ == "__main__":
    main()
