import pty
import os
import sys
import time
import subprocess

try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    print("Error: deploy_secrets.py not found.")
    sys.exit(1)

LOCAL_SCRIPT = "scripts/deployment/debug_db_remote_script.py"
REMOTE_PATH = "/opt/council-news-bot/data/debug_script.py"

def run_debug():
    print(f"=== Uploading and Running Debug Script on {USER}@{HOST} ===")
    
    # 1. Upload
    print("Uploading...")
    with open(LOCAL_SCRIPT, 'rb') as f:
        content = f.read()

    # We use a trick: echo 'content' | ssh ... cat > target
    # But content might have quotes.
    # Better: use scp.
    scp_cmd = ["scp", "-o", "StrictHostKeyChecking=no", LOCAL_SCRIPT, f"{USER}@{HOST}:{REMOTE_PATH}"]
    
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp("scp", scp_cmd)
    else:
        _handle_password(fd)
        os.waitpid(pid, 0)
    
    # 2. Run
    print("\nRunning in container...")
    run_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", f"{USER}@{HOST}", f"cd /opt/council-news-bot && docker compose run --rm bot python3 data/debug_script.py"]
    
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp("ssh", run_cmd)
    else:
        _handle_password(fd)
        os.waitpid(pid, 0)

def _handle_password(fd):
    try:
        while True:
            try:
                output = os.read(fd, 1024).decode(errors='ignore')
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
        pass

if __name__ == "__main__":
    run_debug()
