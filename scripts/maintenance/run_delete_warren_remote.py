
import pty
import os
import sys
import time

# Add current directory to path to allow importing deploy_secrets
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../deployment"))

try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    print("Error: deploy_secrets.py not found.")
    sys.exit(1)

REMOTE_SCRIPT_PATH = "/opt/council-news-bot/scripts/maintenance/delete_warren_posts.py"
LOCAL_SCRIPT_PATH = "scripts/maintenance/delete_warren_posts.py"

def read(fd):
    return os.read(fd, 1024)

def run_command_with_pty(command, password):
    print(f"Running: {command}")
    pid, fd = pty.fork()
    if pid == 0:
        os.execv("/bin/sh", ["/bin/sh", "-c", command])
    else:
        output_buffer = b""
        while True:
            try:
                chunk = read(fd)
                if not chunk:
                    break
                output_buffer += chunk
                sys.stdout.write(chunk.decode(errors='ignore'))
                sys.stdout.flush()
                
                if b"password:" in chunk.lower():
                    time.sleep(0.5)
                    os.write(fd, (password + "\n").encode())
            except OSError:
                break
        return output_buffer

def main():
    # 1. Upload script
    print("Uploading delete script...")
    run_command_with_pty(f"scp {LOCAL_SCRIPT_PATH} {USER}@{HOST}:{REMOTE_SCRIPT_PATH}", PASS)
    
    # 2. Run script
    print("\nRunning delete script on VPS (inside Docker)...")
    
    # Copy to container
    copy_cmd = "docker cp /opt/council-news-bot/scripts/maintenance/delete_warren_posts.py council_news_bot:/app/scripts/maintenance/delete_warren_posts.py"
    run_command_with_pty(f"ssh {USER}@{HOST} '{copy_cmd}'", PASS)
    
    # Execute in container
    exec_cmd = "docker exec council_news_bot python3 scripts/maintenance/delete_warren_posts.py"
    run_command_with_pty(f"ssh {USER}@{HOST} '{exec_cmd}'", PASS)

if __name__ == "__main__":
    main()
