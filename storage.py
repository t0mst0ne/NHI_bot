import sqlite3
from datetime import datetime
from typing import List, Optional, Dict
from config import DB_PATH

class Storage:
    def __init__(self, db_path=DB_PATH):
        self.db_path = str(db_path)
        self.init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS announcements (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    doc_no TEXT,
                    issue_date TEXT,
                    publish_date TEXT,
                    url TEXT NOT NULL,
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def is_processed(self, announcement_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM announcements WHERE id = ?", (announcement_id,))
            return cursor.fetchone() is not None

    def _sync_to_json(self):
        try:
            import json
            from pathlib import Path
            json_file = Path(self.db_path).parent / "processed.json"
            all_records = self.get_recent(limit=500)
            # Save lightweight index
            data = {
                r["id"]: {
                    "title": r["title"],
                    "doc_no": r["doc_no"],
                    "issue_date": r["issue_date"],
                    "publish_date": r["publish_date"],
                    "url": r["url"],
                    "created_at": r["created_at"]
                }
                for r in all_records
            }
            json_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            pass

    def mark_processed(
        self,
        announcement_id: str,
        title: str,
        doc_no: str,
        issue_date: str,
        publish_date: str,
        url: str,
        summary: str = ""
    ):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO announcements (
                    id, title, doc_no, issue_date, publish_date, url, summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                announcement_id,
                title,
                doc_no,
                issue_date,
                publish_date,
                url,
                summary,
                datetime.now().isoformat()
            ))
            conn.commit()
        self._sync_to_json()

    def get_recent(self, limit: int = 5) -> List[Dict]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
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
