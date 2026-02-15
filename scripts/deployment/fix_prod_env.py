import pty
import os
import sys
import time

# Try to import credentials from a local ignored file
try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    print("Error: deploy_secrets.py not found.")
    sys.exit(1)

CMD = "sed -i 's/^# DATABASE_URL/DATABASE_URL/' /opt/council-news-bot/.env && cd /opt/council-news-bot && docker compose up -d --force-recreate"

def run_remote_command():
    print(f"=== Fixing Environment on {USER}@{HOST} ===")
    
    # Construct the SSH command
    # -t forces pseudo-tty allocation which requires password prompt handling behavior we want
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

def read(fd):
    return os.read(fd, 1024)

if __name__ == "__main__":
    run_remote_command()
