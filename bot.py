import time
import logging
import threading
from typing import Optional
import requests

import config
from storage import Storage
from scanner import NHIScanner
from notifier import TelegramNotifier

logger = logging.getLogger(__name__)

class TelegramInteractiveBot:
    def __init__(self):
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = str(config.TELEGRAM_CHAT_ID)
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}"
        self.storage = Storage()
        self.scanner = NHIScanner()
        self.notifier = TelegramNotifier()
        self.running = False
        self.offset = 0

    def _send_reply(self, chat_id: str, text: str, parse_mode: str = "HTML"):
        url = f"{self.api_base}/sendMessage"
        formatted = self.notifier._format_to_html(text) if parse_mode == "HTML" else text
        payload = {"chat_id": chat_id, "text": formatted, "parse_mode": parse_mode}
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.status_code != 200:
                payload["text"] = text
                payload.pop("parse_mode", None)
                requests.post(url, json=payload, timeout=15)
        except Exception as e:
            logger.error(f"Error sending reply: {e}")

    def handle_command(self, chat_id: str, text: str):
        cmd = text.strip().split()[0].lower() if text else ""
        # Support commands with @botname e.g. /scan@mybot
        cmd = cmd.split("@")[0]

        if cmd in ["/start", "/help"]:
            msg = (
                "👋 <b>歡迎使用健保署法規公告 AI 追蹤機器人！</b>\n\n"
                "本機器人每日自動掃描衛福部健保署最新法規公告，並使用 Google Gemini 深度解析內文與附件（PDF/Excel/ODS/Word）。\n\n"
                "📌 <b>可用指令：</b>\n"
                "• <code>/scan</code> 或 <code>/check</code>：立即掃描健保署官網是否有最新公告\n"
                "• <code>/latest</code>：查看近期已分析的健保公告\n"
                "• <code>/status</code>：查看機器人運行狀態與資料庫統計\n"
                "• <code>/help</code>：顯示本說明選單\n"
            )
            self._send_reply(chat_id, msg)

        elif cmd in ["/scan", "/check"]:
            self._send_reply(chat_id, "🔍 <b>已啟動即時掃描...</b>\n正在檢查健保署法規公告頁面，請稍候。")
            def _async_scan():
                try:
                    stats = self.scanner.run_scan()
                    summary_msg = (
                        f"✅ <b>掃描完成！</b>\n"
                        f"• 掃描總數：{stats['scanned']} 篇\n"
                        f"• 新增並推播：{stats['processed']} 篇\n"
                        f"• 已略過舊檔：{stats['skipped']} 篇\n"
                        f"• 錯誤筆數：{stats['errors']} 篇"
                    )
                    self._send_reply(chat_id, summary_msg)
                except Exception as e:
                    self._send_reply(chat_id, f"❌ 掃描過程發生錯誤：{e}")
            threading.Thread(target=_async_scan, daemon=True).start()

        elif cmd == "/latest":
            recents = self.storage.get_recent(limit=3)
            if not recents:
                self._send_reply(chat_id, "目前資料庫尚無已處理的公告紀錄。可輸入 <code>/scan</code> 立即開始抓取。")
                return

            msg = "📋 <b>近期處理的健保署公告：</b>\n\n"
            for idx, item in enumerate(recents, 1):
                msg += f"<b>{idx}. {item['title']}</b>\n"
                msg += f"📅 發布日期：{item.get('issue_date', '無')}\n"
                msg += f"📄 字號：<code>{item.get('doc_no', '無')}</code>\n"
                msg += f"🔗 <a href=\"{item['url']}\">官方公告連結</a>\n\n"
            self._send_reply(chat_id, msg)

        elif cmd == "/status":
            count = self.storage.count()
            crawler_mode = "Firecrawl (API)" if config.FIRECRAWL_API_KEY else "curl_cffi (Browser Impersonation)"
            status_msg = (
                "🤖 <b>健保署 AI 機器人狀態報告</b>\n\n"
                f"• <b>AI 模型</b>：<code>{config.GEMINI_MODEL}</code>\n"
                f"• <b>爬蟲引擎</b>：<code>{crawler_mode}</code>\n"
                f"• <b>已追蹤公告數</b>：<code>{count}</code> 篇\n"
                f"• <b>每日排程時間</b>：<code>{config.DAILY_SCAN_TIME}</code>\n"
                f"• <b>目標網址</b>：<a href=\"{config.NHI_LIST_URL}\">健保署法規公告 (3258)</a>"
            )
            self._send_reply(chat_id, status_msg)

    def start_polling(self):
        """Long-polling loop for incoming user commands."""
        self.running = True
        logger.info("Telegram interactive polling started.")
        while self.running:
            try:
                url = f"{self.api_base}/getUpdates"
                params = {"offset": self.offset, "timeout": 20}
                res = requests.get(url, params=params, timeout=30)
                if res.status_code == 200:
                    data = res.json()
                    for update in data.get("result", []):
                        self.offset = update["update_id"] + 1
                        message = update.get("message")
                        if not message:
                            continue
                        sender_chat_id = str(message.get("chat", {}).get("id"))
                        # Optionally authorize sender (if TELEGRAM_CHAT_ID is set, check or allow)
                        text = message.get("text", "")
                        if text and text.startswith("/"):
                            logger.info(f"Received command: '{text}' from chat {sender_chat_id}")
                            self.handle_command(sender_chat_id, text)
                time.sleep(1)
            except Exception as e:
                logger.error(f"Polling loop exception: {e}")
                time.sleep(5)
