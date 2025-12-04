import pty
import os
import sys
import time

# Add current directory to path to allow importing deploy_secrets
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    print("Error: deploy_secrets.py not found.")
    sys.exit(1)

def read(fd):
    return os.read(fd, 1024)

def check_logs():
    # Command to run
    cmd = ["ssh", "-o", "PreferredAuthentications=password", "-o", "PubkeyAuthentication=no", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", f"{USER}@{HOST}", "cd /opt/council-news-bot && docker compose logs -f --tail=50"]
    
    print(f"Connecting to {USER}@{HOST} to check logs...")
    
    pid, fd = pty.fork()
    
    if pid == 0:
        # Child process
        os.execvp(cmd[0], cmd)
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

if __name__ == "__main__":
    check_logs()
