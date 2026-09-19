import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from storage import Storage
from crawler import NHICrawler
from extractor import AttachmentExtractor
from analyzer import NHIAnalyzer
from notifier import TelegramNotifier
import config

logger = logging.getLogger(__name__)

class NHIScanner:
    def __init__(self):
        self.storage = Storage()
        self.crawler = NHICrawler()
        self.extractor = AttachmentExtractor(config.DOWNLOAD_DIR)
        self.analyzer = NHIAnalyzer()
        self.notifier = TelegramNotifier()

    def _dedupe_attachments(self, attachments: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Deduplicate attachments that offer both PDF and ODS/ODT for the same document."""
        by_name = {}
        for att in attachments:
            name = att.get("name", "附件")
            by_name.setdefault(name, []).append(att)

        chosen = []
        for name, items in by_name.items():
            # If multiple versions exist (e.g. PDF and ODS/ODT), prefer PDF
            pdf_item = next((item for item in items if item["url"].lower().endswith(".pdf")), None)
            if pdf_item:
                chosen.append(pdf_item)
            else:
                chosen.extend(items)
        return chosen

    def run_scan(self, max_items: Optional[int] = None, force_reprocess: bool = False) -> Dict[str, Any]:
        """
        Scan NHI announcements list, process any new items, and send Telegram alerts.
        """
        logger.info("Starting NHI announcements scan...")
        announcements = self.crawler.get_announcements_list()
        if not announcements:
            logger.warning("No announcements retrieved.")
            return {"scanned": 0, "processed": 0, "errors": 0}

        if max_items:
            announcements = announcements[:max_items]

        stats = {"scanned": len(announcements), "processed": 0, "errors": 0, "skipped": 0}

        # Process from oldest to newest so notifications arrive in chronological order
        for item in reversed(announcements):
            item_id = item["id"]
            if not force_reprocess and self.storage.is_processed(item_id):
                stats["skipped"] += 1
                continue

            logger.info(f"Processing announcement [{item_id}]: {item['title'][:40]}...")
            try:
                # 1. Fetch detail content and attachments list
                detail = self.crawler.get_announcement_detail(item["detail_url"])
                item["content"] = detail.get("content", "")
                raw_attachments = detail.get("attachments", [])

                # 2. Download and extract text from attachments
                deduped_attachments = self._dedupe_attachments(raw_attachments)
                downloaded_paths = []
                extracted_attachment_texts = []

                for att in deduped_attachments:
                    url = att["url"]
                    title = att.get("title", "")
                    name = att.get("name", "附件")
                    logger.info(f"Downloading attachment: {title} ({url})")
                    fpath = self.extractor.download_file(url, filename=title)
                    if fpath:
                        downloaded_paths.append(fpath)
                        text_sample = self.extractor.extract_text(fpath)
                        extracted_attachment_texts.append({
                            "name": name,
                            "title": title,
                            "text": text_sample
                        })

                # 3. Analyze with Gemini
                logger.info(f"Analyzing with Gemini ({config.GEMINI_MODEL})...")
                ai_summary = self.analyzer.analyze(item, extracted_attachment_texts)

                # 4. Notify via Telegram
                logger.info("Sending Telegram notification...")
                self.notifier.notify_announcement(
                    announcement=item,
                    ai_summary=ai_summary,
                    downloaded_files=downloaded_paths
                )

                # 5. Mark as processed in database
                self.storage.mark_processed(
                    announcement_id=item_id,
                    title=item["title"],
                    doc_no=item.get("doc_no", ""),
                    issue_date=item.get("issue_date", ""),
                    publish_date=item.get("publish_date", ""),
                    url=item["detail_url"],
                    summary=ai_summary
                )

                stats["processed"] += 1
                logger.info(f"Successfully processed and notified [{item_id}].")

            except Exception as e:
                logger.error(f"Error processing [{item_id}]: {e}", exc_info=True)
                stats["errors"] += 1

        logger.info(f"Scan complete: {stats}")
        return stats
