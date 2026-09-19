import logging
import re
import hashlib
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
        """Fetch HTML using curl_cffi with browser impersonation, with Firecrawl fallback."""
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
                logger.warning(f"curl_cffi fetch returned status {res.status_code} for {url}")
        except Exception as e:
            logger.warning(f"curl_cffi error for {url}: {e}")

        # Fallback to Firecrawl if available
        if self.firecrawl_app:
            logger.info(f"Falling back to Firecrawl for {url}...")
            try:
                scrape_res = self.firecrawl_app.scrape_url(url, params={'formats': ['html']})
                return scrape_res.get('html', '')
            except Exception as e:
                logger.error(f"Firecrawl scrape failed: {e}")

        return None

    # ==========================================
    # 1. 法規公告 (Regulations)
    # ==========================================
    def get_regulatory_announcements(self) -> List[Dict[str, Any]]:
        """Fetch official regulatory announcements from lp-3258-1.html."""
        url = config.CATEGORIES["regulations"]["url"]
        html = self._fetch_html(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        items = []
        for row in table.find_all("tr")[1:]:
            tds = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(tds) < 4:
                continue

            a_tag = row.find("a")
            if not a_tag or not a_tag.get("href"):
                continue

            href = a_tag.get("href")
            detail_url = urljoin(config.NHI_BASE_URL, href)
            m = re.search(r'(cp-[\w-]+)', href)
            item_id = m.group(1) if m else href

            items.append({
                "id": item_id,
                "category": "regulations",
                "category_tag": config.CATEGORIES["regulations"]["tag"],
                "category_name": config.CATEGORIES["regulations"]["name"],
                "title": tds[1] if len(tds) > 1 else a_tag.get_text(strip=True),
                "doc_no": tds[2] if len(tds) > 2 else "",
                "issue_date": tds[3] if len(tds) > 3 else "",
                "publish_date": tds[4] if len(tds) > 4 else "",
                "detail_url": detail_url
            })
        return items

    # ==========================================
    # 2A. 藥品共擬會會議紀錄 (Drug PBAC)
    # ==========================================
    def get_drug_pbac_meetings(self) -> List[Dict[str, Any]]:
        """Fetch drug PBAC joint meeting records."""
        root_url = config.CATEGORIES["drug_pbac"]["url"]
        html = self._fetch_html(root_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("main") or soup
        year_a = next((a for a in main.find_all("a") if "年" in a.get_text() and ("lp-" in a.get("href", "") or "np-" in a.get("href", ""))), None)
        if not year_a:
            return []

        year_url = urljoin(config.NHI_BASE_URL, year_a.get("href"))
        html_year = self._fetch_html(year_url)
        if not html_year:
            return []

        soup_year = BeautifulSoup(html_year, "html.parser")
        items = []
        for a in soup_year.find("main").find_all("a"):
            h = a.get("href", "")
            t = a.get_text(strip=True)
            if "會議紀錄" in t and "cp-" in h:
                detail_url = urljoin(config.NHI_BASE_URL, h)
                m = re.search(r'(cp-[\w-]+)', h)
                item_id = m.group(1) if m else h

                # Extract date from title or string if available
                date_match = re.search(r'\((\d{3}\.\d{2}\.\d{2})新增\)', t)
                issue_date = date_match.group(1) if date_match else ""

                items.append({
                    "id": f"drug_pbac_{item_id}",
                    "category": "drug_pbac",
                    "category_tag": config.CATEGORIES["drug_pbac"]["tag"],
                    "category_name": config.CATEGORIES["drug_pbac"]["name"],
                    "title": t,
                    "doc_no": "藥品共擬會審查紀錄",
                    "issue_date": issue_date,
                    "publish_date": issue_date,
                    "detail_url": detail_url
                })
        return items

    # ==========================================
    # 2B. 特材共擬會會議紀錄 (Device PBAC)
    # ==========================================
    def get_device_pbac_meetings(self) -> List[Dict[str, Any]]:
        """Fetch medical device PBAC joint meeting records."""
        root_url = config.CATEGORIES["device_pbac"]["url"]
        html = self._fetch_html(root_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("main") or soup
        year_a = next((a for a in main.find_all("a") if "年" in a.get_text() and ("lp-" in a.get("href", "") or "np-" in a.get("href", ""))), None)
        if not year_a:
            return []

        year_url = urljoin(config.NHI_BASE_URL, year_a.get("href"))
        html_year = self._fetch_html(year_url)
        if not html_year:
            return []

        soup_year = BeautifulSoup(html_year, "html.parser")
        items = []
        for a in soup_year.find("main").find_all("a"):
            h = a.get("href", "")
            if "dl-" in h and a.parent:
                parent_text = a.parent.get_text(strip=True)
                if "會議紀錄" in parent_text:
                    clean_title = parent_text.replace("PDF", "").replace("會議實錄錄音檔", "").strip()
                    file_url = urljoin(year_url, h)
                    item_id = hashlib.md5(f"device_pbac_{clean_title}_{h}".encode()).hexdigest()[:16]

                    date_match = re.search(r'\((\d{3}\.\d{2}\.\d{2})新增\)', clean_title)
                    issue_date = date_match.group(1) if date_match else ""

                    items.append({
                        "id": f"device_pbac_{item_id}",
                        "category": "device_pbac",
                        "category_tag": config.CATEGORIES["device_pbac"]["tag"],
                        "category_name": config.CATEGORIES["device_pbac"]["name"],
                        "title": clean_title,
                        "doc_no": "特材共擬會審查紀錄",
                        "issue_date": issue_date,
                        "publish_date": issue_date,
                        "detail_url": year_url,
                        "direct_file": {
                            "name": clean_title,
                            "title": f"{clean_title}.pdf",
                            "url": file_url
                        }
                    })
        return list(reversed(items))

    # ==========================================
    # 3. 重大醫療新聞 (Medical News)
    # ==========================================
    def get_medical_news(self) -> List[Dict[str, Any]]:
        """Fetch medical policy news from lp-3255-1.html with keyword filtering."""
        url = config.CATEGORIES["medical_news"]["url"]
        html = self._fetch_html(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        items = []
        med_keywords = [
            "藥", "給付", "健保", "支付", "手術", "護理", "癌症", "罕病",
            "診所", "醫院", "試辦", "急重症", "醫療", "檢測", "疫苗", "調升",
            "挹注", "重症", "門診", "住院", "透析", "達文西", "復健", "兒童"
        ]

        for li in soup.select(".list ul li"):
            a_tag = li.find("a")
            if not a_tag or not a_tag.get("href"):
                continue

            title_el = a_tag.find(class_="title") or a_tag
            raw_title = title_el.get_text(strip=True)
            # Filter only medical-related news
            if not any(kw in raw_title for kw in med_keywords):
                continue

            time_el = a_tag.find("time")
            issue_date = time_el.get_text(strip=True) if time_el else ""

            href = a_tag.get("href")
            detail_url = urljoin(config.NHI_BASE_URL, href)
            m = re.search(r'(cp-[\w-]+)', href)
            item_id = m.group(1) if m else href

            items.append({
                "id": f"news_{item_id}",
                "category": "medical_news",
                "category_tag": config.CATEGORIES["medical_news"]["tag"],
                "category_name": config.CATEGORIES["medical_news"]["name"],
                "title": raw_title,
                "doc_no": "健保署新聞發布",
                "issue_date": issue_date,
                "publish_date": issue_date,
                "detail_url": detail_url
            })
        return items

    # ==========================================
    # 4. 醫療服務與診療項目 (Medical Services)
    # ==========================================
    def get_medical_services(self) -> List[Dict[str, Any]]:
        """Fetch medical services joint meeting and fee schedule revisions."""
        root_url = config.CATEGORIES["medical_services"]["url"]
        html = self._fetch_html(root_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("main") or soup
        year_a = next((a for a in main.find_all("a") if "年" in a.get_text() and ("lp-" in a.get("href", "") or "np-" in a.get("href", ""))), None)
        if not year_a:
            return []

        year_url = urljoin(config.NHI_BASE_URL, year_a.get("href"))
        html_year = self._fetch_html(year_url)
        if not html_year:
            return []

        soup_year = BeautifulSoup(html_year, "html.parser")
        items = []
        for a in soup_year.find("main").find_all("a"):
            h = a.get("href", "")
            t = a.get_text(strip=True)
            if ("會議紀錄" in t or "實錄" in t) and ("cp-" in h or "dl-" in h):
                detail_url = urljoin(config.NHI_BASE_URL, h)
                item_id = hashlib.md5(f"service_pbac_{t}_{h}".encode()).hexdigest()[:16]
                items.append({
                    "id": f"service_pbac_{item_id}",
                    "category": "medical_services",
                    "category_tag": config.CATEGORIES["medical_services"]["tag"],
                    "category_name": config.CATEGORIES["medical_services"]["name"],
                    "title": t,
                    "doc_no": "醫療服務共擬會會議",
                    "issue_date": "115年度",
                    "publish_date": "115年度",
                    "detail_url": detail_url
                })
        return items

    # ==========================================
    # 5. 藥品供應與短缺資訊 (Drug Supply)
    # ==========================================
    def get_drug_supply_updates(self) -> List[Dict[str, Any]]:
        """Fetch drug shortage and supply contingency files from np-2511-1.html."""
        url = config.CATEGORIES["drug_supply"]["url"]
        html = self._fetch_html(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        file_sec = soup.find(class_="fileDownload")
        if not file_sec:
            return []

        items = []
        for li in file_sec.select("ul > li"):
            name_span = li.find(class_="fileName")
            name = name_span.get_text(strip=True) if name_span else ""
            if not name:
                continue

            # Pick primary attachment (PDF or Excel)
            for a in li.find_all("a"):
                h = a.get("href", "")
                if "dl-" in h and (h.endswith(".pdf") or h.endswith(".xlsx") or h.endswith(".xls")):
                    file_url = urljoin(config.NHI_BASE_URL, h)
                    item_id = hashlib.md5(f"supply_{name}_{h}".encode()).hexdigest()[:16]

                    date_match = re.search(r'\((\d{2,3}[\.\/]\d{1,2}[\.\/]\d{1,2})更新\)', name)
                    issue_date = date_match.group(1) if date_match else ""

                    items.append({
                        "id": f"drug_supply_{item_id}",
                        "category": "drug_supply",
                        "category_tag": config.CATEGORIES["drug_supply"]["tag"],
                        "category_name": config.CATEGORIES["drug_supply"]["name"],
                        "title": f"藥品供應資訊更新：{name}",
                        "doc_no": "健保藥品短缺與供應資訊",
                        "issue_date": issue_date,
                        "publish_date": issue_date,
                        "detail_url": url,
                        "direct_file": {
                            "name": name,
                            "title": a.get("title") or f"{name}.pdf",
                            "url": file_url
                        }
                    })
                    break
        return items

    # ==========================================
    # Master Aggregator: All 5 Medical Categories
    # ==========================================
    def get_all_medical_announcements(self) -> List[Dict[str, Any]]:
        """Aggregate announcements across all 5 major medical categories."""
        all_items = []
        try:
            logger.info("Fetching Category 1: 法規公告 (Regulations)...")
            all_items.extend(self.get_regulatory_announcements())
        except Exception as e:
            logger.error(f"Error fetching regulations: {e}")

        try:
            logger.info("Fetching Category 2: 藥品共擬會 (Drug PBAC)...")
            all_items.extend(self.get_drug_pbac_meetings())
        except Exception as e:
            logger.error(f"Error fetching drug PBAC: {e}")

        try:
            logger.info("Fetching Category 2: 特材共擬會 (Device PBAC)...")
            all_items.extend(self.get_device_pbac_meetings())
        except Exception as e:
            logger.error(f"Error fetching device PBAC: {e}")

        try:
            logger.info("Fetching Category 3: 重大醫療新聞 (Medical News)...")
            all_items.extend(self.get_medical_news())
        except Exception as e:
            logger.error(f"Error fetching medical news: {e}")

        try:
            logger.info("Fetching Category 4: 醫療服務與診療 (Medical Services)...")
            all_items.extend(self.get_medical_services())
        except Exception as e:
            logger.error(f"Error fetching medical services: {e}")

        try:
            logger.info("Fetching Category 5: 藥品供應與短缺資訊 (Drug Supply)...")
            all_items.extend(self.get_drug_supply_updates())
        except Exception as e:
            logger.error(f"Error fetching drug supply updates: {e}")

        logger.info(f"Total medical items aggregated: {len(all_items)}")
        return all_items

    # Backwards compatibility alias
    def get_announcements_list(self) -> List[Dict[str, Any]]:
        return self.get_all_medical_announcements()

    def get_announcement_detail(self, detail_url: str) -> Dict[str, Any]:
        """Fetch announcement detail page and extract text and attachments."""
        # If detail_url is a direct binary file (.pdf, .xlsx), return directly
        if detail_url.lower().endswith((".pdf", ".xlsx", ".xls", ".ods", ".odt", ".docx")):
            return {"content": "直接檔案下載連結", "attachments": []}

        html = self._fetch_html(detail_url)
        if not html:
            return {"content": "", "attachments": []}

        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("main") or soup

        # Extract content box
        content_box = main.find(class_="contentbox") or main.find(class_="cp") or main.find(class_="inner")
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
