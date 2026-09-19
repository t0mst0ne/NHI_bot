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

# Target URLs for the 5 Major Medical Categories
NHI_BASE_URL = "https://www.nhi.gov.tw"

CATEGORIES = {
    "regulations": {
        "name": "法規公告",
        "tag": "⚖️【法規公告】",
        "url": "https://www.nhi.gov.tw/ch/lp-3258-1.html",
        "description": "新藥收載、支付價格異動、給付規定修訂、特材與支付標準法規"
    },
    "drug_pbac": {
        "name": "藥品共擬會",
        "tag": "💊【藥品共擬會】",
        "url": "https://www.nhi.gov.tw/ch/np-2488-1.html",
        "description": "藥物給付項目及支付標準共同擬訂會議（藥品部分）會議紀錄，新藥納保前哨站"
    },
    "device_pbac": {
        "name": "特材共擬會",
        "tag": "🩺【特材共擬會】",
        "url": "https://www.nhi.gov.tw/ch/np-3330-1.html",
        "description": "特殊材料共同擬訂會議議程與會議紀錄，新型醫材與器械審查"
    },
    "medical_news": {
        "name": "重大醫療新聞",
        "tag": "📰【醫療政策新聞】",
        "url": "https://www.nhi.gov.tw/ch/lp-3255-1.html",
        "description": "健保署官方新聞發布中與醫療、藥品、手術、點數加給相關之重大政策"
    },
    "medical_services": {
        "name": "醫療服務與診療",
        "tag": "🏥【醫療服務與診療】",
        "url": "https://www.nhi.gov.tw/ch/np-3720-1.html",
        "description": "醫療服務共擬會會議紀錄、新增修訂支付標準診療項目"
    },
    "drug_supply": {
        "name": "藥品供應資訊",
        "tag": "📦【藥品供應資訊】",
        "url": "https://www.nhi.gov.tw/ch/np-2511-1.html",
        "description": "短缺藥品供貨計畫、購藥價高於健保價反映窗口與替代藥品"
    }
}

# Default list url for legacy references
NHI_LIST_URL = CATEGORIES["regulations"]["url"]

# Data directory (persisted in git for GitHub Actions state tracking)
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "nhi_history.db"

# Temp / Download cache folder
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# AI Settings
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Schedule: daily scan time (HH:MM in 24h format, e.g. "12:00")
DAILY_SCAN_TIME = os.getenv("DAILY_SCAN_TIME", "12:00")
