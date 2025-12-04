import pty
import os
import sys
import time

# Add current directory to path to allow importing deploy_secrets
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../deployment"))

try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    try:
        sys.path.append(os.path.join(os.getcwd(), "deployment"))
        from deploy_secrets import HOST, USER, PASS
    except ImportError:
        print("Error: deploy_secrets.py not found.")
        sys.exit(1)

LOCAL_SCRIPT_PATH = "scripts/maintenance/full_health_check.py"
REMOTE_SCRIPT_PATH = "/opt/council-news-bot/scripts/maintenance/full_health_check.py"

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
                data = read(fd)
                if not data:
                    break
                output_buffer += data
                
                if b"password:" in data.lower():
                    os.write(fd, (password + "\n").encode())
            except OSError:
                break
        
        _, status = os.waitpid(pid, 0)
        return output_buffer.decode()

def main():
    # 1. Upload script
    print("Uploading full health check script...")
    run_command_with_pty(f"scp {LOCAL_SCRIPT_PATH} {USER}@{HOST}:{REMOTE_SCRIPT_PATH}", PASS)
    
    # 2. Run script
    print("Running full health check on VPS...")
    # We need to make sure we run it from the root dir so it can find states/
    output = run_command_with_pty(f"ssh {USER}@{HOST} 'cd /opt/council-news-bot && python3 scripts/maintenance/full_health_check.py'", PASS)
    
    # Filter output
    lines = output.splitlines()
    start_capture = False
    clean_output = []
    
    for line in lines:
        if "Loaded" in line:
            start_capture = True
        if start_capture:
            clean_output.append(line)
            
    print("\n".join(clean_output))

if __name__ == "__main__":
    main()
