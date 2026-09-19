import io
import os
import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from curl_cffi import requests

logger = logging.getLogger(__name__)

class AttachmentExtractor:
    def __init__(self, download_dir: Path):
        self.download_dir = download_dir
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session(impersonate="chrome124")

    def download_file(self, url: str, filename: Optional[str] = None) -> Optional[Path]:
        """Download a file with browser fingerprint to bypass Cloudflare."""
        try:
            headers = {
                "Referer": "https://www.nhi.gov.tw/",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
            res = self.session.get(url, headers=headers, timeout=30)
            if res.status_code != 200:
                logger.error(f"Failed to download {url}: status {res.status_code}")
                return None

            if not filename:
                # Derive filename from url or header
                parsed = urlparse(url)
                filename = os.path.basename(parsed.path) or "downloaded_file"

            # Clean filename
            filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
            dest_path = self.download_dir / filename
            dest_path.write_bytes(res.content)
            return dest_path
        except Exception as e:
            logger.error(f"Download exception for {url}: {e}")
            return None

    def extract_text(self, file_path: Path, max_chars: int = 15000) -> str:
        """Extract text content from PDF, Excel, Word, ODS, ODT."""
        ext = file_path.suffix.lower()
        try:
            if ext == ".pdf":
                return self._extract_pdf(file_path, max_chars)
            elif ext in [".xlsx", ".xls"]:
                return self._extract_excel(file_path, max_chars)
            elif ext == ".ods":
                return self._extract_ods(file_path, max_chars)
            elif ext == ".docx":
                return self._extract_docx(file_path, max_chars)
            elif ext == ".odt":
                return self._extract_odt(file_path, max_chars)
            else:
                return f"[檔案類型 {ext}，不支援直接文字擷取]"
        except Exception as e:
            logger.warning(f"Error extracting {file_path.name}: {e}")
            return f"[檔案解析失敗: {e}]"

    def _extract_pdf(self, path: Path, max_chars: int) -> str:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        extracted = []
        total_len = 0
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            extracted.append(f"--- 頁碼 {i+1} ---\n{text}")
            total_len += len(text)
            if total_len > max_chars:
                extracted.append("\n[內容已達長度上限截斷...]")
                break
        return "\n".join(extracted)

    def _extract_excel(self, path: Path, max_chars: int) -> str:
        import openpyxl
        wb = openpyxl.load_workbook(str(path), data_only=True)
        sheets_text = []
        total_len = 0
        for name in wb.sheetnames[:5]:  # limit to first 5 sheets
            ws = wb[name]
            sheet_rows = []
            sheet_rows.append(f"=== 工作表: {name} ===")
            for row in ws.iter_rows(values_only=True):
                # Filter empty rows
                vals = [str(v).strip() for v in row if v is not None and str(v).strip() != ""]
                if vals:
                    line = " | ".join(vals)
                    sheet_rows.append(line)
                    total_len += len(line)
                if total_len > max_chars:
                    sheet_rows.append("[內容過長已截斷...]")
                    break
            sheets_text.append("\n".join(sheet_rows))
            if total_len > max_chars:
                break
        return "\n\n".join(sheets_text)

    def _extract_ods(self, path: Path, max_chars: int) -> str:
        from odf import opendocument, table, text
        doc = opendocument.load(str(path))
        tables = doc.getElementsByType(table.Table)
        sheets_text = []
        total_len = 0
        for t in tables[:5]:
            t_name = t.getAttribute("name") or "Sheet"
            sheet_rows = [f"=== ODS 工作表: {t_name} ==="]
            rows = t.getElementsByType(table.TableRow)
            for r in rows:
                cells = r.getElementsByType(table.TableCell)
                row_vals = []
                for c in cells:
                    # extract text from paragraphs in cell
                    ps = c.getElementsByType(text.P)
                    cell_text = "".join([elem.data for p in ps for elem in p.childNodes if hasattr(elem, 'data')]).strip()
                    if cell_text:
                        row_vals.append(cell_text)
                if row_vals:
                    line = " | ".join(row_vals)
                    sheet_rows.append(line)
                    total_len += len(line)
                if total_len > max_chars:
                    sheet_rows.append("[ODS 內容過長已截斷...]")
                    break
            sheets_text.append("\n".join(sheet_rows))
            if total_len > max_chars:
                break
        return "\n\n".join(sheets_text)

    def _extract_docx(self, path: Path, max_chars: int) -> str:
        import docx
        doc = docx.Document(str(path))
        lines = []
        total_len = 0
        for p in doc.paragraphs:
            txt = p.text.strip()
            if txt:
                lines.append(txt)
                total_len += len(txt)
            if total_len > max_chars:
                lines.append("[內容過長已截斷...]")
                break
        return "\n".join(lines)

    def _extract_odt(self, path: Path, max_chars: int) -> str:
        from odf import opendocument, text
        doc = opendocument.load(str(path))
        paragraphs = doc.getElementsByType(text.P)
        lines = []
        total_len = 0
        for p in paragraphs:
            txt = "".join([elem.data for elem in p.childNodes if hasattr(elem, 'data')]).strip()
            if txt:
                lines.append(txt)
                total_len += len(txt)
            if total_len > max_chars:
                lines.append("[內容過長已截斷...]")
                break
        return "\n".join(lines)
