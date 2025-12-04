
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

REMOTE_SCRIPT_PATH = "/opt/council-news-bot/scripts/maintenance/daily_health_check.py"
LOCAL_SCRIPT_PATH = "scripts/maintenance/daily_health_check.py"

def read(fd):
    return os.read(fd, 1024)

def run_command_with_pty(command, password):
    # print(f"Running: {command}") 
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
                # sys.stdout.write(chunk.decode(errors='ignore'))
                # sys.stdout.flush()
                
                if b"password:" in chunk.lower():
                    time.sleep(0.5)
                    os.write(fd, (password + "\n").encode())
            except OSError:
                break
        return output_buffer.decode(errors='ignore')

def main():
    # 1. Upload script
    print("Uploading health check script...")
    run_command_with_pty(f"scp {LOCAL_SCRIPT_PATH} {USER}@{HOST}:{REMOTE_SCRIPT_PATH}", PASS)
    
    # 2. Run script
    print("Running health check on VPS...")
    output = run_command_with_pty(f"ssh {USER}@{HOST} 'cd /opt/council-news-bot && python3 scripts/maintenance/daily_health_check.py'", PASS)
    
    # Filter output to remove ssh banner/password prompts
    lines = output.splitlines()
    clean_output = []
    start_capture = False
    for line in lines:
        if "=== Target Council Status" in line:
            start_capture = True
        if start_capture:
            clean_output.append(line)
            
    print("\n".join(clean_output))

    # 3. Get Logs (Tail)
    print("\n=== Recent VPS Logs (Tail 20) ===")
    log_output = run_command_with_pty(f"ssh {USER}@{HOST} 'cd /opt/council-news-bot && docker compose logs --tail=20'", PASS)
    # Simple filter for logs
    log_lines = log_output.splitlines()
    for line in log_lines:
        if "council_news_bot" in line:
            print(line)

if __name__ == "__main__":
    main()
