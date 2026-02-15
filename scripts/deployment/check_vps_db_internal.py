
import subprocess
import re

def run_psql_command(query):
    """Run a PSQL command inside the council_db container."""
    cmd = [
        "docker", "exec", "council_db", 
        "psql", "-U", "councilbot", "-d", "council_news", 
        "-c", query
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def check_db():
    print("=== Checking Production DB (Postgres) ===")
    
    # Check counts by state
    print("\n--- Articles by State ---")
    query_states = "SELECT state, COUNT(*) FROM articles GROUP BY state ORDER BY count(*) DESC;"
    print(run_psql_command(query_states))

    # Check unposted by state
    print("\n--- Unposted Articles by State ---")
    query_unposted = "SELECT state, COUNT(*) FROM articles WHERE posted_at IS NULL AND status != 'archived' GROUP BY state ORDER BY count(*) DESC;"
    print(run_psql_command(query_unposted))

    # Check for potential errors/zombies
    print("\n--- Potential Zombies (Last 24h) ---")
    # Note: casting date to ensure correctly handled if possible, otherwise rely on first_seen_at
    query_zombies = "SELECT count(*) FROM articles WHERE first_seen_at > NOW() - INTERVAL '24 hours' AND title IS NULL;"
    print("Null Titles (Last 24h):")
    print(run_psql_command(query_zombies))

if __name__ == "__main__":
    check_db()
