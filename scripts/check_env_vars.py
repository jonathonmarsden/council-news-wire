
import os
from dotenv import load_dotenv

load_dotenv()

STATES = ['VIC', 'NSW', 'QLD', 'WA', 'SA', 'TAS', 'NT', 'ACT']

def check_env():
    print("Checking environment variables for BlueSky credentials...")
    for state in STATES:
        handle_var = f"BLUESKY_HANDLE_{state}"
        pass_var = f"BLUESKY_PASSWORD_{state}"
        
        handle = os.environ.get(handle_var)
        password = os.environ.get(pass_var)
        
        status = "✅ OK" if (handle and password) else "❌ MISSING"
        print(f"{state}: {status} (Handle var: {handle_var})")

if __name__ == "__main__":
    check_env()
