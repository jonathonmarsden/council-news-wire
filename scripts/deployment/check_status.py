import pty
import os
import sys
import time

# Add current directory to path to allow importing deploy_secrets
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Try to import credentials from a local ignored file
try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    print("Error: deploy_secrets.py not found.")
    sys.exit(1)

def read(fd):
    return os.read(fd, 1024)

def check_status():
    # Command to run via SSH - fetch last 1000 lines which should cover the recent deployment run
    ssh_cmd = f"ssh {USER}@{HOST} 'cd /opt/council-news-bot && docker compose logs --tail=2000'"
    
    print(f"=== Fetching logs from {USER}@{HOST} ===")
    
    pid, fd = pty.fork()
    
    if pid == 0:
        # Child process
        os.execv('/usr/bin/ssh', ['ssh', f'{USER}@{HOST}', 'cd /opt/council-news-bot && docker compose logs --tail=2000'])
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
            print(e)
            
if __name__ == "__main__":
    check_status()
