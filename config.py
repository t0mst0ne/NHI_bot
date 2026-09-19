import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# API Keys & Bot Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "").strip()

# Target URL
NHI_BASE_URL = "https://www.nhi.gov.tw"
NHI_LIST_URL = "https://www.nhi.gov.tw/ch/lp-3258-1.html"

# SQLite Database
DB_PATH = BASE_DIR / "nhi_history.db"

# Temp / Download cache folder
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# AI Settings
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Schedule: daily scan time (HH:MM in 24h format, e.g. "09:00")
DAILY_SCAN_TIME = os.getenv("DAILY_SCAN_TIME", "09:00")
