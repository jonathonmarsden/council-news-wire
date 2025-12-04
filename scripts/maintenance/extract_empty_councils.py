import json
import os
import re
import glob
import sys
import pty

# Add deployment dir to path for secrets
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../deployment"))
try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    try:
        sys.path.append(os.path.join(os.getcwd(), "deployment"))
        from deploy_secrets import HOST, USER, PASS
    except ImportError:
        print("Error: deploy_secrets.py not found.")
        sys.exit(1)

def read(fd):
    return os.read(fd, 1024)

def run_command_with_pty(command, password):
    pid, fd = pty.fork()
    if pid == 0:
        os.execv("/bin/sh", ["/bin/sh", "-c", command])
    else:
        output_buffer = b""
        while True:
            try:
                data = read(fd)
                if not data:
                    break
                output_buffer += data
                if b"password:" in data.lower():
                    os.write(fd, (password + "\n").encode())
            except OSError:
                break
        
        _, status = os.waitpid(pid, 0)
        return output_buffer.decode(errors='ignore')

def load_council_map():
    name_to_id = {}
    id_to_config = {}
    state_files = glob.glob("states/*/councils.json")
    for fpath in state_files:
        state = os.path.basename(os.path.dirname(fpath))
        try:
            with open(fpath, 'r') as f:
                data = json.load(f)
                for c in data.get('councils', []):
                    if c.get('enabled', True):
                        c['state'] = state
                        name_to_id[c['name']] = c['id']
                        id_to_config[c['id']] = c
        except Exception as e:
            print(f"Error loading {fpath}: {e}")
    return name_to_id, id_to_config

def get_remote_logs():
    print("Fetching logs from VPS...")
    cmd = f"ssh {USER}@{HOST} 'docker logs council_news_bot --tail 20000'"
    return run_command_with_pty(cmd, PASS)

def parse_logs(log_content, name_to_id):
    scraper_health = {}
    found_pattern = re.compile(r"\s+(.+?): Found (\d+) articles")
    
    lines = log_content.splitlines()
    for line in lines:
        m_found = found_pattern.search(line)
        if m_found:
            name = m_found.group(1).strip()
            count = int(m_found.group(2))
            cid = name_to_id.get(name)
            if cid:
                status = 'ok' if count > 0 else 'empty'
                scraper_health[cid] = {'status': status, 'count': count}
    return scraper_health

def main():
    name_to_id, id_to_config = load_council_map()
    logs = get_remote_logs()
    scraper_health = parse_logs(logs, name_to_id)
    
    empty_councils = []
    for cid, config in id_to_config.items():
        health = scraper_health.get(cid)
        if health and health['status'] == 'empty':
            empty_councils.append(cid)
            
    print(f"Found {len(empty_councils)} empty councils.")
    
    with open("empty_councils.json", "w") as f:
        json.dump(empty_councils, f, indent=2)
    print("Saved to empty_councils.json")

if __name__ == "__main__":
    main()
