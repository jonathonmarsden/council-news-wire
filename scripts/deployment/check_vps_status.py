import pty
import os
import sys
import time

try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    print("Error: deploy_secrets.py not found.")
    sys.exit(1)

CMD = f"ssh {USER}@{HOST} 'cd /opt/council-news-bot && docker compose ps && echo \"--- JSON SCRAPER ACTIVITY ---\" && docker compose logs --tail=2000 | grep \"JsonScraper\" | tail -n 20 && echo \"--- POTENTIAL ZOMBIES (0 Items) ---\" && docker compose logs --tail=2000 | grep \"Scraped 0 items\" | tail -n 20 && echo \"--- RECENT LOGS ---\" && docker compose logs --tail=50'"

def check_status():
    pid, fd = pty.fork()
    
    if pid == 0:
        # Child: Run SSH command
        os.execvp("ssh", ["ssh", f"{USER}@{HOST}", CMD.split("'")[1]])
    else:
        # Parent: Monitor and provide password
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

if __name__ == "__main__":
    check_status()
