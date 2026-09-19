import os
import time
import logging
from pathlib import Path
from typing import List, Optional, Dict
import requests
import config

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}"

    def _format_to_html(self, text: str) -> str:
        """Convert standard markdown from Gemini into safe Telegram HTML."""
        import html
        import re

        # First escape HTML special characters
        # But we want to preserve markdown formatting tokens before converting
        # 1. Protect code blocks ```...```
        code_blocks = []
        def save_code_block(m):
            code_blocks.append(html.escape(m.group(1)))
            return f"__CODE_BLOCK_{len(code_blocks)-1}__"
        text = re.sub(r'```(?:[\w]*\n)?(.*?)```', save_code_block, text, flags=re.DOTALL)

        # 2. Protect inline code `...`
        inline_codes = []
        def save_inline_code(m):
            inline_codes.append(html.escape(m.group(1)))
            return f"__INLINE_CODE_{len(inline_codes)-1}__"
        text = re.sub(r'`([^`]+)`', save_inline_code, text)

        # 3. Escape general HTML
        text = html.escape(text)

        # 4. Convert markdown links [text](url)
        text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', text)

        # 5. Convert headers (### or ## or #)
        text = re.sub(r'^(?:#{1,4})\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)

        # 6. Convert bold **text**
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

        # 7. Convert italic *text*
        text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)

        # 8. Restore code blocks
        for i, code in enumerate(code_blocks):
            text = text.replace(f"__CODE_BLOCK_{i}__", f"<pre>{code}</pre>")

        # 9. Restore inline code
        for i, icode in enumerate(inline_codes):
            text = text.replace(f"__INLINE_CODE_{i}__", f"<code>{icode}</code>")

        return text

    def send_message(self, text: str, parse_mode: Optional[str] = "HTML") -> bool:
        """Send a single text message with HTML parsing and plain-text fallback."""
        url = f"{self.api_base}/sendMessage"
        
        formatted_text = self._format_to_html(text) if parse_mode == "HTML" else text
        payload = {
            "chat_id": self.chat_id,
            "text": formatted_text,
            "disable_web_page_preview": False
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200:
                return True
            else:
                logger.warning(f"Telegram {parse_mode} failed ({res.text}), falling back to plain text...")
                payload["text"] = text  # fallback to raw text without HTML tags
                payload.pop("parse_mode", None)
                res2 = requests.post(url, json=payload, timeout=15)
                return res2.status_code == 200
        except Exception as e:
            logger.error(f"Telegram request failed: {e}")
            return False

    def send_document(self, file_path: Path, caption: str = "") -> bool:
        """Send an attachment file to Telegram."""
        url = f"{self.api_base}/sendDocument"
        try:
            with open(file_path, "rb") as f:
                data = {"chat_id": self.chat_id}
                if caption:
                    data["caption"] = caption[:1024]
                files = {"document": (file_path.name, f)}
                res = requests.post(url, data=data, files=files, timeout=60)
                return res.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send document {file_path}: {e}")
            return False

    def notify_announcement(
        self,
        announcement: Dict,
        ai_summary: str,
        downloaded_files: Optional[List[Path]] = None
    ) -> bool:
        """Send full announcement briefing, splitting into chunks if > 4000 chars."""
        title = announcement.get("title", "")
        doc_no = announcement.get("doc_no", "無")
        issue_date = announcement.get("issue_date", "")
        url = announcement.get("detail_url", "")

        category_tag = announcement.get("category_tag", "⚖️【法規公告】")

        header = (
            f"📢 *【健保署情報推播】* {category_tag}\n\n"
            f"📌 *主旨*：{title}\n"
            f"📄 *編號/字號*：`{doc_no}`\n"
            f"📅 *發布日期*：{issue_date}\n"
            f"🔗 *官方連結*：[點擊前往健保署頁面]({url})\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        full_content = header + ai_summary

        # Split message if exceeds Telegram's 4000 character limit
        chunks = self._chunk_message(full_content, max_len=3900)
        success = True

        for i, chunk in enumerate(chunks):
            part_suffix = f"\n\n<i>(第 {i+1}/{len(chunks)} 頁)</i>" if len(chunks) > 1 else ""
            ok = self.send_message(chunk + part_suffix, parse_mode="HTML")
            if not ok:
                success = False
            time.sleep(1)  # small delay to prevent rate limiting

        # Send attachments if available
        if downloaded_files:
            for file_path in downloaded_files:
                if file_path and file_path.exists():
                    logger.info(f"Sending attachment: {file_path.name}")
                    self.send_document(file_path, caption=f"📎 附件：{file_path.name}")
                    time.sleep(1)

        return success

    def _chunk_message(self, text: str, max_len: int = 3900) -> List[str]:
        """Split text cleanly on paragraph breaks."""
        if len(text) <= max_len:
            return [text]

        chunks = []
        paragraphs = text.split("\n\n")
        current_chunk = ""

        for p in paragraphs:
            if len(current_chunk) + len(p) + 2 <= max_len:
                current_chunk += ("\n\n" + p if current_chunk else p)
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                # If a single paragraph is longer than max_len
                if len(p) > max_len:
                    lines = p.split("\n")
                    sub_chunk = ""
                    for line in lines:
                        if len(sub_chunk) + len(line) + 1 <= max_len:
                            sub_chunk += ("\n" + line if sub_chunk else line)
                        else:
                            if sub_chunk:
                                chunks.append(sub_chunk)
                            sub_chunk = line
                    if sub_chunk:
                        current_chunk = sub_chunk
                else:
                    current_chunk = p

        if current_chunk:
            chunks.append(current_chunk)

        return chunks
