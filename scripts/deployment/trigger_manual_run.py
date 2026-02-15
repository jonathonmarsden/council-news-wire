import pty
import os
import sys
import time

try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    print("Error: deploy_secrets.py not found.")
    sys.exit(1)

CMD = "cd /opt/council-news-bot && docker compose run --rm bot python3 main.py --state wa"

def trigger_run():
    print(f"=== Triggering Manual Run (WA) on {USER}@{HOST} ===")
    print(f"Command: {CMD}")
    
    ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", f"{USER}@{HOST}", CMD]
    
    pid, fd = pty.fork()
    
    if pid == 0:
        os.execvp("ssh", ssh_cmd)
    else:
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
            print(f"Error: {e}")
        finally:
            os.close(fd)

if __name__ == "__main__":
    trigger_run()
