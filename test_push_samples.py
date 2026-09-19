import logging
import time
from pathlib import Path
import config
from crawler import NHICrawler
from extractor import AttachmentExtractor
from analyzer import NHIAnalyzer
from notifier import TelegramNotifier
from storage import Storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_push")

def run_test_push():
    crawler = NHICrawler()
    extractor = AttachmentExtractor(config.DOWNLOAD_DIR)
    analyzer = NHIAnalyzer()
    notifier = TelegramNotifier()
    storage = Storage()

    all_items = crawler.get_all_medical_announcements()

    # Pick the best representative latest item for each category
    selected_items = []
    
    # 1. Regulations (法規公告) - pick the Tevimbra or dialysis
    reg_item = next((x for x in all_items if x["category"] == "regulations" and "cp-20426" in x["id"]), None)
    if not reg_item:
        reg_item = next((x for x in all_items if x["category"] == "regulations"), None)
    if reg_item:
        selected_items.append(reg_item)

    # 2. Drug PBAC (藥品共擬會第83次會議紀錄)
    drug_pbac_item = next((x for x in all_items if x["category"] == "drug_pbac"), None)
    if drug_pbac_item:
        selected_items.append(drug_pbac_item)

    # 3. Device PBAC (特材共擬會第83次會議紀錄)
    device_pbac_item = next((x for x in all_items if x["category"] == "device_pbac"), None)
    if device_pbac_item:
        selected_items.append(device_pbac_item)

    # 4. Medical News (重大醫療新聞 - 精進藥品給付)
    news_item = next((x for x in all_items if x["category"] == "medical_news" and "cp-20393" in x["id"]), None)
    if not news_item:
        news_item = next((x for x in all_items if x["category"] == "medical_news"), None)
    if news_item:
        selected_items.append(news_item)

    # 5. Medical Services (醫療服務共擬會)
    services_item = next((x for x in all_items if x["category"] == "medical_services"), None)
    if services_item:
        selected_items.append(services_item)

    # 6. Drug Supply (短缺藥品庫存及供貨計畫)
    supply_item = next((x for x in all_items if x["category"] == "drug_supply" and "短缺藥品" in x["title"]), None)
    if not supply_item:
        supply_item = next((x for x in all_items if x["category"] == "drug_supply"), None)
    if supply_item:
        selected_items.append(supply_item)

    logger.info(f"Starting test push for {len(selected_items)} selected medical categories...")

    for idx, item in enumerate(selected_items, 1):
        tag = item.get("category_tag", "")
        title = item.get("title", "")
        item_id = item.get("id", "")
        logger.info(f"\n==========================================")
        logger.info(f"[{idx}/{len(selected_items)}] Processing {tag}: {title[:40]}...")
        logger.info(f"URL: {item.get('detail_url')}")

        try:
            # 1. Fetch details
            detail = crawler.get_announcement_detail(item["detail_url"])
            item["content"] = detail.get("content", "")
            raw_attachments = detail.get("attachments", [])

            if item.get("direct_file"):
                raw_attachments.append(item["direct_file"])

            # 2. Process attachments
            # Prefer PDF / Excel, max 2 attachments per test to be considerate with bandwidth
            downloaded_paths = []
            extracted_attachment_texts = []

            for att in raw_attachments[:2]:
                url = att["url"]
                att_title = att.get("title", "")
                name = att.get("name", "附件")
                logger.info(f"  -> Downloading attachment: {att_title} ({url})")
                fpath = extractor.download_file(url, filename=att_title)
                if fpath:
                    downloaded_paths.append(fpath)
                    text_sample = extractor.extract_text(fpath)
                    extracted_attachment_texts.append({
                        "name": name,
                        "title": att_title,
                        "text": text_sample
                    })

            # 3. Analyze with Gemini
            logger.info(f"  -> Analyzing with Gemini ({config.GEMINI_MODEL})...")
            ai_summary = analyzer.analyze(item, extracted_attachment_texts)

            # 4. Notify via Telegram
            logger.info(f"  -> Sending Telegram message & documents...")
            notifier.notify_announcement(
                announcement=item,
                ai_summary=ai_summary,
                downloaded_files=downloaded_paths
            )

            logger.info(f"  -> Successfully pushed {tag} to Telegram!")

            # Small pause between categories
            time.sleep(3)

        except Exception as e:
            logger.error(f"Error pushing item {item_id}: {e}", exc_info=True)

    logger.info("\nAll categories test push complete!")

if __name__ == "__main__":
    run_test_push()
