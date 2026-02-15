import pty
import os
import sys
import time

try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    print("Error: deploy_secrets.py not found.")
    sys.exit(1)

SQL_QUERY = "UPDATE articles SET posted_at = NULL WHERE status = 'new' AND posted_at IS NOT NULL;"
REMOTE_CMD = f'docker exec -i council_db psql -U councilbot -d council_news -c "{SQL_QUERY}"'

def reset_queue():
    print(f"=== Resetting Queue on {USER}@{HOST} ===")
    ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", f"{USER}@{HOST}", REMOTE_CMD]
    
    pid, fd = pty.fork()
    
    if pid == 0:
        os.execvp("ssh", ssh_cmd)
    else:
        try:
            output = b""
            while True:
                try:
                    chunk = os.read(fd, 1024)
                    if not chunk: break
                    sys.stdout.write(chunk.decode(errors='ignore'))
                    sys.stdout.flush()
                    if b"password:" in chunk.lower():
                        time.sleep(0.5)
                        os.write(fd, (PASS + "\n").encode())
                except OSError: break
        except Exception: pass
        finally: os.close(fd)

if __name__ == "__main__":
    reset_queue()
