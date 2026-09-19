# 健保署全方位醫療情報 AI 自動監測與 Telegram 推播機器人 (NHI Bot)

本專案是一個專為台灣衛生福利部中央健康保險署（健保署）設計的全方位醫療情報自動監控與 AI 深度解讀推播系統。

系統每日定時掃描**健保署 5 大醫療核心板塊**，自動下載並萃取附件文件（**PDF、Excel/ODS 表格、Word/ODT 條文**），透過 **Google Gemini** 進行專業醫療法規、藥品特材審查與政策分析，並將結構化解讀報告與原始附件檔案自動發送至指定的 **Telegram Bot**。

---

## 📊 監控之 5 大醫療核心領域

| 板塊分類 | 標籤 | 監控來源 | 重點內容 |
| :--- | :--- | :--- | :--- |
| **1. 正式法規命令** | `⚖️【法規公告】` | [法規公告 (lp-3258-1)](https://www.nhi.gov.tw/ch/lp-3258-1.html) | 新藥收載、藥價調整、給付條文修正、特材收載、支付標準修訂 |
| **2. 新藥/特材審查前哨** | `💊【藥品共擬會】`<br>`🩺【特材共擬會】` | [藥品共擬會 (np-2488-1)](https://www.nhi.gov.tw/ch/np-2488-1.html)<br>[特材共擬會 (np-3330-1)](https://www.nhi.gov.tw/ch/np-3330-1.html) | 新藥與新型醫材進入健保前最關鍵的共同擬訂會議審查紀錄，**提前 1~2 個月掌握即將納保藥物與價格** |
| **3. 重大醫療政策新聞** | `📰【醫療政策新聞】` | [新聞發布 (lp-3255-1)](https://www.nhi.gov.tw/ch/lp-3255-1.html) | 健保署官方新聞，自動篩選醫療、藥品、手術加給、癌症/罕病擴增給付白話政策快訊 |
| **4. 醫療服務與診療** | `🏥【醫療服務與診療】` | [醫療服務共擬會 (np-3720-1)](https://www.nhi.gov.tw/ch/np-3720-1.html)<br>[支付標準項目 (lp-3719-1)](https://www.nhi.gov.tw/ch/lp-3719-1.html) | 診療項目代碼修訂、點數調整、醫院試辦計畫與品質保證方案 |
| **5. 藥品供應與短缺** | `📦【藥品供應資訊】` | [藥品供應資訊 (np-2511-1)](https://www.nhi.gov.tw/ch/np-2511-1.html) | 臨床短缺藥品庫存及供貨計畫表、特約機構反映購藥價窗口與替代藥品清單 |

---

## 🌟 核心功能特色

1. **5 大醫療板塊全覆蓋**：從最前線的共擬會審查、最新政策發布，到正式法規公告與短缺藥品供應，全面一手掌握。
2. **混合爬蟲雙引擎（支援 Firecrawl 與 curl_cffi）**：
   - **Firecrawl 支援**：若在 `.env` 設定 `FIRECRAWL_API_KEY`，系統優先使用 Firecrawl 進行高效能雲端爬取與內容轉換。
   - **curl_cffi 瀏覽器指紋引擎**：無須額外 API 費用，模擬 Chrome 真實 TLS (JA3/JA4) 指紋，自動通過健保署網站的 Cloudflare 驗證機制。
3. **全格式附件下載與內文解析**：
   - **PDF**：使用 `pypdf` 自動萃取表格與文字。
   - **試算表 (Excel `.xlsx` / 開放文件 `.ods`)**：使用 `openpyxl` 與 `odfpy` 解析藥品代碼、核定價格、調整幅度。
   - **文件 (Word `.docx` / 開放文件 `.odt`)**：使用 `python-docx` 與 `odfpy` 解析條文修正對照表。
   - **智慧去重**：若同份公文同時提供 PDF 與 ODS/ODT，自動優先處理 PDF，避免重複冗餘下載。
4. **Google Gemini 深度醫療解讀**：
   - 針對 5 大不同領域動態套用專屬分析提示詞（共擬會強調審查決議與療效比較；法規公告強調代碼價格與給付限制；短缺藥品強調替代方案）。
5. **Telegram 推播與雙向互動**：
   - **分類標籤鮮明**：每則推播均標註清晰 Emoji 分類標籤（如 `💊【藥品共擬會】`）。
   - **超長訊息自動分頁**：智能處理 Telegram 4096 字元限制，並自動轉換 Markdown 為 Telegram 專用 HTML。
   - **附件自動夾帶發送**：直接在 Telegram 接收原始 PDF/Excel，方便在手機或平板直接閱讀。
   - **互動指令支援**：
     - `/scan` 或 `/check`：手動立即觸發掃描 5 大板塊。
     - `/latest`：檢視最近處理過的健保公告清單。
     - `/categories`：檢視 5 大分類詳細說明與官網專區網址。
     - `/status`：查看機器人運行狀態、資料庫統計（含各分類細部數量）與爬蟲模式。
     - `/help`：顯示功能指令選單。
6. **SQLite 與 JSON 雙軌歷史紀錄**：
   - 內建 `data/nhi_history.db` 與 `data/processed.json`，已推播過的情報不會重複發送，並能在 GitHub Actions 中自動保存。

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

## 🤖 GitHub Actions 自動化每日掃描 (推薦)

專案已內建 [`.github/workflows/daily_scan.yml`](file:///.github/workflows/daily_scan.yml)，每天**台灣時間中午 12:00 (UTC 04:00)** 會自動在雲端執行掃描、比較與 Telegram 推播，無需自己架設伺服器！

### 設定步驟：

1. 前往 GitHub 倉庫：`https://github.com/t0mst0ne/NHI_bot`
2. 點選 **Settings** -> **Secrets and variables** -> **Actions**。
3. 點選 **New repository secret**，新增以下 Secrets：
   - `GEMINI_API_KEY`：您的 Google Gemini API Key
   - `TELEGRAM_BOT_TOKEN`：您的 Telegram Bot Token
   - `TELEGRAM_CHAT_ID`：接收推播的 Telegram Chat ID
   - `FIRECRAWL_API_KEY`：（選填）Firecrawl API Key
4. 前往 **Actions** 頁籤，點選 **Daily NHI Scan & Telegram Alert**，點擊 **Run workflow** 即可隨時手動測試雲端執行！
5. **狀態自動同步**：當發現新公告並推播後，GitHub Action 會自動將更新後的 `data/` 歷史紀錄 commit 回倉庫，確保後續不會重複推播。

---

## 💬 Telegram 指令操作

在 Telegram 中向你的 Bot 發送：
- `/scan`：立即連線健保署網站檢查是否有最新公文，並即時分析推播。
- `/latest`：顯示目前已收錄的最新 3 篇公告。
- `/status`：查看系統運行數據、模型版本與爬蟲引擎狀態。
- `/help`：查看指令清單。
