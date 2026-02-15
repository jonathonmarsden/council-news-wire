import pty
import os
import sys
import time

try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    print("Error: deploy_secrets.py not found.")
    sys.exit(1)

SQL_QUERY = """
SELECT council_id, left(title, 30), date, first_seen_at 
FROM articles 
WHERE status = 'new' 
LIMIT 20;
"""

REMOTE_CMD = f'docker exec -i council_db psql -U councilbot -d council_news -c "{SQL_QUERY}"'

def inspect_dates():
    print(f"=== Inspecting Dates on {USER}@{HOST} ===")
    
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
                    if not chunk:
                        break
                    decoded = chunk.decode(errors='ignore')
                    output += chunk
                    sys.stdout.write(decoded)
                    sys.stdout.flush()
                    
                    if "password:" in decoded.lower():
                        time.sleep(0.5)
                        os.write(fd, (PASS + "\n").encode())
                        
                except OSError:
                    break
        except Exception as e:
            print(f"Error: {e}")
        finally:
            os.close(fd)

if __name__ == "__main__":
    inspect_dates()
