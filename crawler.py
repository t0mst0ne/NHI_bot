import logging
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

import config

logger = logging.getLogger(__name__)

class NHICrawler:
    def __init__(self):
        self.session = curl_requests.Session(impersonate="chrome124")
        self.firecrawl_app = None
        if config.FIRECRAWL_API_KEY:
            try:
                from firecrawl import FirecrawlApp
                self.firecrawl_app = FirecrawlApp(api_key=config.FIRECRAWL_API_KEY)
                logger.info("Firecrawl client initialized.")
            except Exception as e:
                logger.warning(f"Failed to initialize Firecrawl client: {e}")

    def _fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML using curl_cffi with browser impersonation."""
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": config.NHI_BASE_URL + "/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        try:
            res = self.session.get(url, headers=headers, timeout=20)
            if res.status_code == 200 and "Just a moment..." not in res.text:
                return res.text
            else:
                logger.warning(f"Failed fetching {url}, status: {res.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def get_announcements_list(self) -> List[Dict[str, Any]]:
        """Fetch announcement list from lp-3258-1.html."""
        html = self._fetch_html(config.NHI_LIST_URL)
        if not html and self.firecrawl_app:
            logger.info("curl_cffi failed or blocked; falling back to Firecrawl for list page...")
            try:
                scrape_res = self.firecrawl_app.scrape_url(config.NHI_LIST_URL, params={'formats': ['html']})
                html = scrape_res.get('html', '')
            except Exception as e:
                logger.error(f"Firecrawl scrape failed: {e}")

        if not html:
            logger.error("Could not fetch announcements list.")
            return []

        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            logger.warning("No table found on list page.")
            return []

        announcements = []
        rows = table.find_all("tr")[1:]  # skip header row
        for row in rows:
            tds = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(tds) < 4:
                continue

            a_tag = row.find("a")
            if not a_tag or not a_tag.get("href"):
                continue

            href = a_tag.get("href")
            detail_url = urljoin(config.NHI_BASE_URL, href)

            # Generate unique ID from URL
            # e.g., /ch/cp-20443-d255d-3258-1.html -> cp-20443-d255d-3258-1
            m = re.search(r'(cp-[\w-]+)', href)
            announcement_id = m.group(1) if m else href

            announcements.append({
                "id": announcement_id,
                "title": tds[1] if len(tds) > 1 else a_tag.get_text(strip=True),
                "doc_no": tds[2] if len(tds) > 2 else "",
                "issue_date": tds[3] if len(tds) > 3 else "",
                "publish_date": tds[4] if len(tds) > 4 else "",
                "detail_url": detail_url
            })

        return announcements

    def get_announcement_detail(self, detail_url: str) -> Dict[str, Any]:
        """Fetch announcement detail page and extract text and attachments."""
        html = self._fetch_html(detail_url)
        if not html and self.firecrawl_app:
            logger.info(f"Using Firecrawl for detail page: {detail_url}")
            try:
                scrape_res = self.firecrawl_app.scrape_url(detail_url, params={'formats': ['html']})
                html = scrape_res.get('html', '')
            except Exception as e:
                logger.error(f"Firecrawl detail scrape failed: {e}")

        if not html:
            return {"content": "", "attachments": []}

        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("main") or soup

        # Extract content box
        content_box = main.find(class_="contentbox")
        content_text = content_box.get_text(separator="\n", strip=True) if content_box else main.get_text(separator="\n", strip=True)

        # Extract attachments
        attachments = []
        file_sec = main.find(class_="fileDownload")
        if file_sec:
            for li in file_sec.select("ul > li"):
                name_span = li.find(class_="fileName")
                name = name_span.get_text(strip=True) if name_span else "附件"
                for a_tag in li.find_all("a"):
                    href = a_tag.get("href")
                    if href and "/dl-" in href:
                        file_url = urljoin(config.NHI_BASE_URL, href)
                        title = a_tag.get("title") or a_tag.get_text(strip=True)
                        attachments.append({
                            "name": name,
                            "title": title,
                            "url": file_url
                        })
        else:
            # Fallback for any dl- links in content
            for a_tag in main.find_all("a"):
                href = a_tag.get("href", "")
                if "/dl-" in href:
                    file_url = urljoin(config.NHI_BASE_URL, href)
                    title = a_tag.get("title") or a_tag.get_text(strip=True)
                    attachments.append({
                        "name": title or "附件",
                        "title": title,
                        "url": file_url
                    })

        return {
            "content": content_text,
            "attachments": attachments
        }
