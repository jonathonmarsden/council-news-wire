import pty
import os
import sys

# Add current directory to path to allow importing deploy_secrets
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
    print(f"Running: {command}")
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
        return output_buffer.decode()

def main():
    # Grep for glamorgan in the docker logs
    cmd = f"ssh {USER}@{HOST} 'docker logs council_news_bot 2>&1 | grep -i \"glamorgan\" | tail -n 20'"
    output = run_command_with_pty(cmd, PASS)
    print(output)

if __name__ == "__main__":
    main()
