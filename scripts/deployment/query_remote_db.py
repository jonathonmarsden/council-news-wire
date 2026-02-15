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

# SQL query to run inside the container
SQL_QUERY = """
SELECT 'TOTAL_NEW_ITEMS: ' || count(*) FROM articles WHERE status = 'new';
SELECT '----------------------------------------' as separator;
SELECT council_id, left(title, 40) as title_short, state, to_char(first_seen_at, 'YYYY-MM-DD HH24:MI') as seen 
FROM articles 
WHERE status = 'new' 
ORDER BY first_seen_at DESC 
LIMIT 20;
"""

# Docker exec command to run psql
# We need to be careful with quoting. 
# The outer SSH command takes one string.
# The inner docker command runs psql.
REMOTE_CMD = f'docker exec -i council_db psql -U councilbot -d council_news -c "{SQL_QUERY}"'

def query_remote_db():
    print(f"=== Querying Remote DB on {USER}@{HOST} ===")
    
    ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", f"{USER}@{HOST}", REMOTE_CMD]
    
    pid, fd = pty.fork()
    
    if pid == 0:
        # Child process
        os.execvp("ssh", ssh_cmd)
    else:
        # Parent process
        try:
            output_buffer = ""
            while True:
                try:
                    chunk = os.read(fd, 1024)
                    if not chunk:
                        break
                    decoded_chunk = chunk.decode(errors='ignore')
                    output_buffer += decoded_chunk
                    sys.stdout.write(decoded_chunk)
                    sys.stdout.flush()
                    
                    if "password:" in decoded_chunk.lower():
                        time.sleep(0.5)
                        os.write(fd, (PASS + "\n").encode())
                        
                except OSError:
                    break
        except Exception as e:
            print(f"Error: {e}")
        finally:
            os.close(fd)

if __name__ == "__main__":
    query_remote_db()
