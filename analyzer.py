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

        attachments_section = ""
        if attachment_texts:
            attachments_section = "\n\n【附件內容擷取】\n"
            for idx, att in enumerate(attachment_texts, 1):
                attachments_section += f"\n--- 附件 {idx}：{att.get('name', '檔案')} ({att.get('title', '')}) ---\n"
                attachments_section += att.get("text", "")[:10000] + "\n"

        prompt = f"""請詳細解析以下衛生福利部中央健康保險署（健保署）最新公告：

【公告標題】{title}
【發文字號】{doc_no}
【發布日期】{issue_date}

【公告內文】
{content}
{attachments_section}

請依照以下格式進行專業詳細解讀（使用清晰的 Markdown 格式與適當 Emoji）：

1. 📌 **【核心摘要】**
   - 本公告的主要目的、政策背景及核心結論（簡明扼要，1-2段話）。

2. 🎯 **【法規與給付重點】**
   - 若為藥品或特材：請列出具體成分名／品名、健保代碼、支付價格（新收載或價格調幅）、初核說明、給付規定修訂重點（如適用癌別、治療線次、限制條件）。
   - 若為支付標準或計畫：列出新增/修正點數、申報代碼、品質保證或獎勵保留款重點。

3. 🏥 **【受影響對象與適用機構】**
   - 哪些醫療院所（醫學中心、區域醫院、地區醫院、基層診所、藥局）或特定科別醫師會受到影響？
   - 哪些病患族群直接受惠或適用？

4. 📅 **【生效與實施時程】**
   - 明確指出生效日期（注意是否追溯生效或特定季別實施）。

5. 📎 **【附件精華解析】**
   - 綜合附件（PDF、Excel、ODS）內部的關鍵表格數據或條文對照重點整理。

6. 💡 **【實務因應與注意事項】**
   - 醫療機構、醫事行政人員申報時需注意的事項或審查要點。
"""
        return prompt
