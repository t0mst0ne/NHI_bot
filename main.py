import argparse
import logging
import sys
import time
import threading
import schedule

import config
from scanner import NHIScanner
from bot import TelegramInteractiveBot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.BASE_DIR / "bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("main")

def run_scheduler():
    """Background thread to run daily scan at configured time."""
    scanner = NHIScanner()
    logger.info(f"Daily scheduler configured to run everyday at {config.DAILY_SCAN_TIME}.")
    schedule.every().day.at(config.DAILY_SCAN_TIME).do(scanner.run_scan)

    while True:
        schedule.run_pending()
        time.sleep(30)

def main():
    parser = argparse.ArgumentParser(description="NHI Announcements Telegram AI Bot")
    parser.add_argument(
        "--scan-once",
        action="store_true",
        help="Run an immediate scan, push any new announcements to Telegram, and exit."
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run only the Telegram interactive command listener without scheduler."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocessing of announcements even if already in database."
    )
    args = parser.parse_args()

    # Verify credentials
    if not config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is missing in .env!")
        sys.exit(1)
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing in .env!")
        sys.exit(1)

    if args.scan_once:
        logger.info("Executing one-shot scan...")
        scanner = NHIScanner()
        stats = scanner.run_scan(force_reprocess=args.force)
        logger.info(f"Scan finished. Result: {stats}")
        return

    # Start daily scheduler in a background daemon thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    # Start Telegram interactive bot
    bot = TelegramInteractiveBot()
    logger.info("Starting Telegram Bot listener... (Press Ctrl+C to stop)")
    try:
        bot.start_polling()
    except KeyboardInterrupt:
        logger.info("Stopping bot on user interrupt...")
        bot.running = False

if __name__ == "__main__":
    main()
