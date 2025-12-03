
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

REMOTE_SCRIPT_PATH = "/opt/council-news-bot/scripts/maintenance/check_warren_db.py"
LOCAL_SCRIPT_PATH = "scripts/maintenance/check_warren_db.py"

def read(fd):
    return os.read(fd, 1024)

def run_remote_check():
    # 1. SCP the script
    print(f"Uploading {LOCAL_SCRIPT_PATH} to {HOST}...")
    scp_cmd = f"scp {LOCAL_SCRIPT_PATH} {USER}@{HOST}:{REMOTE_SCRIPT_PATH}"
    os.system(f"sshpass -p '{PASS}' {scp_cmd}") # Try sshpass if available, otherwise fallback to pty method for scp is hard.
    
    # Actually, let's use the pty method for everything since we know it works
    pass

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
    # We'll use the existing deploy_with_password.py logic but simplified or just use scp directly with pty
    
    # Create remote directory if needed (it should exist)
    
    # Upload
    print("Uploading check script...")
    run_command_with_pty(f"scp {LOCAL_SCRIPT_PATH} {USER}@{HOST}:{REMOTE_SCRIPT_PATH}", PASS)
    
    # 2. Run script
    print("\nRunning check script on VPS...")
    run_command_with_pty(f"ssh {USER}@{HOST} 'cd /opt/council-news-bot && python3 scripts/maintenance/check_warren_db.py'", PASS)

if __name__ == "__main__":
    main()
