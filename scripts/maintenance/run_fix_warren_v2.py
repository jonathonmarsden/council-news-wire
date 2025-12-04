import pty
import os
import sys
import time

# Add current directory to path to allow importing deploy_secrets
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../deployment"))

try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    # Fallback if not found in relative path
    try:
        sys.path.append(os.path.join(os.getcwd(), "deployment"))
        from deploy_secrets import HOST, USER, PASS
    except ImportError:
        print("Error: deploy_secrets.py not found.")
        sys.exit(1)

LOCAL_SCRIPT = "scripts/maintenance/fix_warren_db.py"
REMOTE_SCRIPT = "/opt/council-news-bot/scripts/maintenance/fix_warren_db.py"

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
                # print(data.decode(), end='') # Debug output
                
                if b"password:" in data.lower():
                    os.write(fd, (password + "\n").encode())
            except OSError:
                break
        
        _, status = os.waitpid(pid, 0)
        return output_buffer.decode()

def main():
    print("Uploading fix script...")
    scp_cmd = f"scp {LOCAL_SCRIPT} {USER}@{HOST}:{REMOTE_SCRIPT}"
    run_command_with_pty(scp_cmd, PASS)
    
    print("Running fix script on VPS...")
    ssh_cmd = f"ssh {USER}@{HOST} 'python3 {REMOTE_SCRIPT}'"
    output = run_command_with_pty(ssh_cmd, PASS)
    print(output)

if __name__ == "__main__":
    main()
