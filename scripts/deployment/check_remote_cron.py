import pty
import os
import sys
import time

# Try to import credentials
try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    print("Error: deploy_secrets.py not found.")
    sys.exit(1)

CMD = "crontab -l"

def check_remote_cron():
    print(f"=== Checking Crontab on {USER}@{HOST} ===")
    
    ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", f"{USER}@{HOST}", CMD]
    
    pid, fd = pty.fork()
    
    if pid == 0:
        # Child process
        os.execvp("ssh", ssh_cmd)
    else:
        # Parent process
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
    check_remote_cron()
