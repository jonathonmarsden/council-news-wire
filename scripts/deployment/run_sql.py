import pty
import os
import sys
import time
import argparse

try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    print("Error: deploy_secrets.py not found.")
    sys.exit(1)

def run_sql(sql_query):
    # Escape double quotes for shell safety if needed, though simple strings are okay
    # We wrap the query in double quotes for the bash command
    escaped_query = sql_query.replace('"', '\\"')
    remote_cmd = f'docker exec -i council_db psql -U councilbot -d council_news -c "{escaped_query}"'
    
    print(f"=== Running SQL on {USER}@{HOST} ===")
    print(f"Query: {sql_query}")
    
    ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", f"{USER}@{HOST}", remote_cmd]
    
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
    if len(sys.argv) < 2:
        print("Usage: python3 run_sql.py <query>")
        sys.exit(1)
    
    run_sql(sys.argv[1])
