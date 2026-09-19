import logging
from typing import Dict, Any, List
from google import genai
from google.genai import types
import config

logger = logging.getLogger(__name__)

class NHIAnalyzer:
    def __init__(self):
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.model = config.GEMINI_MODEL

    def analyze(self, announcement: Dict[str, Any], attachment_texts: List[Dict[str, str]]) -> str:
        """
        Use Gemini to produce a thorough, structured Traditional Chinese explanation of the announcement.
        """
        prompt = self._build_prompt(announcement, attachment_texts)
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "你是一位精通台灣全民健康保險法規、藥品特材給付及醫療費用支付標準的資深政策分析專家。"
                        "請以專業、清晰、結構分明的正體中文（繁體中文），為醫事人員、醫療院所管理階層及公眾解析健保署的最新公告與法規。"
                        "必須特別關注公告內容與附件（PDF、Excel表格等）中的具體細節（如藥品成分名、健保代碼、調整後價格、生效日期、給付限制條款）。"
                        "請避免空泛套話，直接切入核心重點。"
                    ),
                    temperature=0.2,
                )
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini API error during analysis: {e}")
            return f"❌ AI 分析失敗：{e}"

    def _build_prompt(self, announcement: Dict[str, Any], attachment_texts: List[Dict[str, str]]) -> str:
        title = announcement.get("title", "")
        doc_no = announcement.get("doc_no", "")
        issue_date = announcement.get("issue_date", "")
        content = announcement.get("content", "")
        category = announcement.get("category", "regulations")
        category_tag = announcement.get("category_tag", "⚖️【法規公告】")

        attachments_section = ""
        if attachment_texts:
            attachments_section = "\n\n【附件內容擷取】\n"
            for idx, att in enumerate(attachment_texts, 1):
                attachments_section += f"\n--- 附件 {idx}：{att.get('name', '檔案')} ({att.get('title', '')}) ---\n"
                attachments_section += att.get("text", "")[:12000] + "\n"

        category_guidance = ""
        if category in ["drug_pbac", "device_pbac"]:
            category_guidance = (
                "【特別分析要求（共擬會審查紀錄）】\n"
                "此為新藥/特材進入健保給付前最關鍵的共擬會審查紀錄：\n"
                "- 請特別整理：本次會議討論通過、暫予保留或不予同意的品項（成分名、商品名、廠牌）。\n"
                "- 臨床適應症、治療線次、核定健保支付價格或藥商建議價。\n"
                "- 健保財務影響預估或附加協議（風險分攤方案）。\n"
            )
        elif category == "drug_supply":
            category_guidance = (
                "【特別分析要求（藥品供應與短缺）】\n"
                "- 請特別整理：短缺藥品品名/成分、短缺原因及預估恢復供貨期程。\n"
                "- 臨床建議替代藥品品項與健保代碼。\n"
                "- 醫療院所與藥局因應調劑注意事項。\n"
            )
        elif category == "medical_news":
            category_guidance = (
                "【特別分析要求（重大醫療政策新聞）】\n"
                "- 請提煉政策核心亮點：挹注金額、受益族群、醫療院所調整幅度。\n"
                "- 轉化為醫事人員與民眾能快速掌握的白話重點。\n"
            )

        prompt = f"""請詳細解析以下衛生福利部中央健康保險署（健保署）最新公布資訊：

【分類標籤】{category_tag}
【資訊標題】{title}
【參考編號/字號】{doc_no}
【日期】{issue_date}

【內文資料】
{content}
{attachments_section}

{category_guidance}

請依照以下結構進行深度解讀（使用清晰的 Markdown 格式與適當 Emoji，專業且精準）：

1. 📌 **【核心摘要】**
   - 本公告/紀錄的核心結論、政策背景與主要意圖（1-2段話）。

2. 🎯 **【關鍵要點與數據】**
   - 具體項目、藥品/特材成分名、健保代碼、點數或價格變更、審查通過條件。

3. 🏥 **【受影響對象與醫療機構】**
   - 哪些層級醫療院所（醫學中心、區域、地區、診所、藥局）或專科醫師受影響？
   - 適用病患族群。

4. 📅 **【時程與生效日期】**
   - 明確標出實施、生效或供貨時程。

5. 📎 **【附件精華解析】**
   - 提煉附件（PDF、Excel、ODS）內部之重要表格與條文對照。

6. 💡 **【臨床與行政實務因應】**
   - 臨床開立、健保申報或藥品採購時的具體行動建議。
"""
        return prompt
