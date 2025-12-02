import os
from pathlib import Path
from dotenv import load_dotenv

# Determine the project root directory
# This assumes core/config.py is located at <project_root>/core/config.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(PROJECT_ROOT / ".env")

# Database Configuration
DB_PATH = Path(os.getenv("DB_PATH", PROJECT_ROOT / "bot.db"))

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = PROJECT_ROOT / "logs"

# Scraper Configuration
USER_AGENT = os.getenv("USER_AGENT", "CouncilNewsBot/1.0")

# State Configuration Paths
STATES_DIR = PROJECT_ROOT / "states"
CONFIG_PATHS = {
    "vic": STATES_DIR / "vic" / "councils.json",
    "nsw": STATES_DIR / "nsw" / "councils.json",
    "qld": STATES_DIR / "qld" / "councils.json",
    "tas": STATES_DIR / "tas" / "councils.json",
    "wa": STATES_DIR / "wa" / "councils.json",
    "sa": STATES_DIR / "sa" / "councils.json",
    "nt": STATES_DIR / "nt" / "councils.json",
}

def get_db_path() -> Path:
    """Return the absolute path to the database."""
    return DB_PATH

def get_project_root() -> Path:
    """Return the absolute path to the project root."""
    return PROJECT_ROOT
