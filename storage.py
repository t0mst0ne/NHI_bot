import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
from zoneinfo import ZoneInfo
from config import CATEGORIES, DB_PATH

TAIPEI = ZoneInfo("Asia/Taipei")

class Storage:
    def __init__(self, db_path=DB_PATH):
        self.db_path = str(db_path)
        self.init_db()
        self.export_daily_markdown()

    @contextmanager
    def _get_connection(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
                yield conn

    def init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS announcements (
                    id TEXT PRIMARY KEY,
                    category TEXT DEFAULT 'regulations',
                    title TEXT NOT NULL,
                    doc_no TEXT,
                    issue_date TEXT,
                    publish_date TEXT,
                    url TEXT NOT NULL,
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Check if category column exists in case of existing table
            cursor.execute("PRAGMA table_info(announcements)")
            columns = [col[1] for col in cursor.fetchall()]
            if "category" not in columns:
                cursor.execute("ALTER TABLE announcements ADD COLUMN category TEXT DEFAULT 'regulations'")
            conn.commit()

    def is_processed(self, announcement_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM announcements WHERE id = ?", (announcement_id,))
            return cursor.fetchone() is not None

    def export_daily_markdown(self):
        """Export all history by its first processed date in Taiwan time."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            records = conn.execute(
                "SELECT * FROM announcements ORDER BY created_at, id"
            ).fetchall()

        by_date = {}
        for record in records:
            processed_at = datetime.fromisoformat(record["created_at"])
            # Legacy timestamps were recorded as naive local Taiwan time.
            if processed_at.tzinfo is None:
                processed_at = processed_at.replace(tzinfo=TAIPEI)
            day = processed_at.astimezone(TAIPEI).date().isoformat()
            by_date.setdefault(day, []).append(record)

        daily_dir = Path(self.db_path).parent / "daily"
        daily_dir.mkdir(parents=True, exist_ok=True)
        for day, items in sorted(by_date.items()):
            lines = [
                f"# 健保署公告每日紀錄：{day}",
                "",
                "依首次處理日期（台灣時間）彙整。",
                "",
                f"共 {len(items)} 則公告。",
                "",
            ]
            for item in items:
                category = item["category"] or "regulations"
                category_name = CATEGORIES.get(category, {}).get("name", category)
                title = " ".join(item["title"].splitlines())
                summary = (item["summary"] or "尚無 AI 摘要。").strip()
                if summary == "[Baseline seed record]":
                    summary = "此為初始化歷史紀錄，未保存 AI 摘要。"
                lines.extend([
                    f"## {title}",
                    "",
                    f"- 分類：{category_name}",
                    f"- 公告 ID：`{item['id']}`",
                    f"- 發文字號：{item['doc_no'] or '未提供'}",
                    f"- 發文日期：{item['issue_date'] or '未提供'}",
                    f"- 公告日期：{item['publish_date'] or '未提供'}",
                    f"- 原始連結：<{item['url']}>",
                    f"- 首次處理時間：{item['created_at']}",
                    "",
                    "### AI 摘要",
                    "",
                    summary,
                    "",
                    "---",
                    "",
                ])
            output = daily_dir / f"{day}.md"
            content = "\n".join(lines)
            if not output.exists() or output.read_text(encoding="utf-8") != content:
                temporary = output.with_suffix(".md.tmp")
                temporary.write_text(content, encoding="utf-8")
                temporary.replace(output)

    def mark_processed(
        self,
        announcement_id: str,
        title: str,
        doc_no: str,
        issue_date: str,
        publish_date: str,
        url: str,
        summary: str = "",
        category: str = "regulations"
    ):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO announcements (
                    id, category, title, doc_no, issue_date, publish_date, url, summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    category = excluded.category,
                    title = excluded.title,
                    doc_no = excluded.doc_no,
                    issue_date = excluded.issue_date,
                    publish_date = excluded.publish_date,
                    url = excluded.url,
                    summary = excluded.summary
            """, (
                announcement_id,
                category,
                title,
                doc_no,
                issue_date,
                publish_date,
                url,
                summary,
                datetime.now(TAIPEI).isoformat()
            ))
            conn.commit()
        self.export_daily_markdown()

    def get_recent(self, limit: int = 5, category: Optional[str] = None) -> List[Dict]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if category:
                cursor.execute(
                    "SELECT * FROM announcements WHERE category = ? ORDER BY created_at DESC LIMIT ?",
                    (category, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM announcements ORDER BY created_at DESC LIMIT ?", (limit,)
                )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def count(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM announcements")
            return cursor.fetchone()[0]

    def count_by_category(self) -> Dict[str, int]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT category, COUNT(*) FROM announcements GROUP BY category")
            return {row[0] or "regulations": row[1] for row in cursor.fetchall()}
