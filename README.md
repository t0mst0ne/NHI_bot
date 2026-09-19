# 健保署法規公告 AI 自動監測與 Telegram 推播機器人 (NHI Bot)

本專案是一個專為台灣衛生福利部中央健康保險署（健保署）**法規公告**（[https://www.nhi.gov.tw/ch/lp-3258-1.html](https://www.nhi.gov.tw/ch/lp-3258-1.html)）設計的自動監控與 AI 深度解讀推播系統。

系統每日定時掃描最新公告與法規修訂，自動下載並萃取附件文件（**PDF、Excel/ODS 表格、Word/ODT 條文**），透過 **Google Gemini** 進行專業醫療法規與藥品特材給付分析，並將結構化解讀報告與原始附件檔案自動發送至指定的 **Telegram Bot**。

---

## 🌟 核心功能特色

1. **混合爬蟲雙引擎（支援 Firecrawl 與 curl_cffi）**：
   - **Firecrawl 支援**：若在 `.env` 設定 `FIRECRAWL_API_KEY`，系統優先使用 Firecrawl 進行高效能雲端爬取與內容轉換。
   - **curl_cffi 瀏覽器指紋引擎**：無須額外 API 費用，模擬 Chrome 真實 TLS (JA3/JA4) 指紋，自動通過健保署網站的 Cloudflare 驗證機制。
2. **全格式附件下載與內文解析**：
   - **PDF**：使用 `pypdf` 自動萃取表格與文字。
   - **試算表 (Excel `.xlsx` / 開放文件 `.ods`)**：使用 `openpyxl` 與 `odfpy` 解析藥品代碼、核定價格、調整幅度。
   - **文件 (Word `.docx` / 開放文件 `.odt`)**：使用 `python-docx` 與 `odfpy` 解析條文修正對照表。
   - **智慧去重**：若同份公文同時提供 PDF 與 ODS/ODT，自動優先處理 PDF，避免重複冗餘下載。
3. **Google Gemini 深度法規解讀**：
   - 核心摘要與政策目的。
   - 藥品/特材給付重點（成分名、代碼、新收載/價格調幅、限制線次）。
   - 醫療院所與受影響對象（申報規則、支付點數）。
   - 生效與實施時程（精確標記追溯日期）。
   - 附件精華與實務因應建議。
4. **Telegram 推播與雙向互動**：
   - **超長訊息自動分頁**：智能處理 Telegram 4096 字元限制，並自動轉換 Markdown 為 Telegram 專用 HTML。
   - **附件自動夾帶發送**：直接在 Telegram 接收原始 PDF/Excel，方便在手機或平板直接閱讀。
   - **互動指令支援**：
     - `/scan` 或 `/check`：手動立即觸發掃描最新法規公告。
     - `/latest`：檢視最近處理過的健保公告清單。
     - `/status`：查看機器人運行狀態、資料庫統計與爬蟲模式。
     - `/help`：顯示功能指令選單。
5. **SQLite 歷史紀錄防重複機制**：
   - 內建 `nhi_history.db`，已推播過的公告不會重複發送。

---

## 📁 系統架構

```
NHI_bot/
├── .env                  # 環境變數與金鑰配置
├── config.py             # 配置管理
├── storage.py            # SQLite 資料庫操作模組
├── crawler.py            # 健保署法規公告爬蟲 (Firecrawl / curl_cffi)
├── extractor.py          # 附件下載與文件文字萃取 (PDF, ODS, Excel, Word)
├── analyzer.py           # Google Gemini AI 專業分析模組
├── notifier.py           # Telegram 訊息分頁推播與文件傳送
├── bot.py                # Telegram 互動指令監聽器
├── scanner.py            # 掃描、分析、推播核心流程排程
├── main.py               # 程式進入點 (支援單次掃描、排程與互動 Bot)
├── requirements.txt      # Python 套件清單
└── README.md             # 本說明文件
```

---

## 🚀 快速開始

### 1. 環境需求
- Python 3.10+ (已在 Python 3.14 測試通過)
- macOS / Linux / Windows

### 2. 安裝虛擬環境與套件

```bash
# 建立虛擬環境
python3 -m venv .venv
source .venv/bin/activate

# 安裝依賴
pip install -r requirements.txt
```

### 3. 設定環境變數 (`.env`)

專案目錄下的 `.env` 檔案格式如下：

```ini
GEMINI_API_KEY=your_gemini_api_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here

# 選填：若要使用 Firecrawl 爬取，請填入 API 金鑰；未填則自動使用本地 curl_cffi
FIRECRAWL_API_KEY=

# 選填：每日自動掃描時間 (24小時制，預設 09:00)
DAILY_SCAN_TIME=09:00

# 選填：Gemini 模型 (預設 gemini-2.5-flash)
GEMINI_MODEL=gemini-2.5-flash
```

---

## 🏃 執行方式

### 模式 A：常駐執行（每日定時自動掃描 + Telegram 互動指令）
最推薦的日常運行模式，會在後台按 `DAILY_SCAN_TIME` 每日掃描，同時隨時響應 Telegram 聊天視窗中的 `/scan` 等指令：

```bash
.venv/bin/python main.py
```

### 模式 B：單次立即掃描（適合 crontab 或手動執行）
掃描官網，推播新公告後立即結束程式：

```bash
.venv/bin/python main.py --scan-once
```

若想要強制重新掃描並推播已記錄過的公告（例如測試推播效果）：
```bash
.venv/bin/python main.py --scan-once --force
```

---

## ⏰ 設定系統排程 (Crontab 或 Launchd)

若偏好使用作業系統的原生 crontab 每日執行：

```bash
crontab -e
```
加入以下設定（例如每日早上 9:00 執行）：
```cron
0 9 * * * cd /Users/tomstone/GITHUB/NHI_bot && /Users/tomstone/GITHUB/NHI_bot/.venv/bin/python main.py --scan-once >> /Users/tomstone/GITHUB/NHI_bot/cron.log 2>&1
```

---

## 💬 Telegram 指令操作

在 Telegram 中向你的 Bot 發送：
- `/scan`：立即連線健保署網站檢查是否有最新公文，並即時分析推播。
- `/latest`：顯示目前已收錄的最新 3 篇公告。
- `/status`：查看系統運行數據、模型版本與爬蟲引擎狀態。
- `/help`：查看指令清單。
