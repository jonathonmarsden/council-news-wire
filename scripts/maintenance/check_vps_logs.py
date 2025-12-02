import pty
import os
import sys
import time

# Try to import credentials from a local ignored file
try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    print("Error: scripts/deploy_secrets.py not found.")
    sys.exit(1)

CMD = "cd /opt/council-news-bot && docker compose logs --tail=50"

def read(fd):
    return os.read(fd, 1024)

def check_logs():
    pid, fd = pty.fork()
    
    if pid == 0:
        # Child process
        # We use ssh directly here
        os.execvp("ssh", ["ssh", f"{USER}@{HOST}", CMD])
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
                        
                    if "continue connecting" in output.lower():
                        time.sleep(0.5)
                        os.write(fd, b"yes\n")
                        
                except OSError:
                    break
        except Exception as e:
            print(f"Error: {e}")
        finally:
            os.close(fd)

if __name__ == "__main__":
    check_logs()
