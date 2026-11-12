import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from storage import Storage, TAIPEI


class DailyMarkdownTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db_path = Path(self.directory.name) / "history.db"
        self.storage = Storage(self.db_path)
        self.daily_dir = self.db_path.parent / "daily"

    def save(self, item_id, day="2026-11-12", summary="**重點**\n\n完整 AI 摘要"):
        with patch("storage.datetime") as clock:
            clock.now.return_value = datetime.fromisoformat(f"{day}T12:00:00+08:00")
            clock.fromisoformat.side_effect = datetime.fromisoformat
            self.storage.mark_processed(
                item_id, "測試公告", "健保字第123號", "115-11-11", "115-11-12",
                "https://www.nhi.gov.tw/ch/example.html", summary, "drug_pbac"
            )
            clock.now.assert_called_once_with(TAIPEI)

    def test_same_day_combines_announcements_and_preserves_summary(self):
        self.save("first")
        self.save("second")
        content = (self.daily_dir / "2026-11-12.md").read_text(encoding="utf-8")
        for expected in (
            "共 2 則公告", "藥品共擬會", "健保字第123號", "115-11-11",
            "115-11-12", "https://www.nhi.gov.tw/ch/example.html",
            "**重點**\n\n完整 AI 摘要", "`first`", "`second`", "+08:00",
        ):
            self.assertIn(expected, content)
        self.assertEqual(len(list(self.daily_dir.glob("*.md"))), 1)
        self.assertFalse((self.db_path.parent / "processed.json").exists())
        self.assertTrue(self.storage.is_processed("first"))

    def test_separate_dates_and_force_update_without_duplicates(self):
        self.save("first")
        self.save("second", "2026-11-13")
        self.save("first", "2026-11-14", "更新後的摘要")
        self.assertEqual(
            {path.name for path in self.daily_dir.glob("*.md")},
            {"2026-11-12.md", "2026-11-13.md"},
        )
        content = (self.daily_dir / "2026-11-12.md").read_text(encoding="utf-8")
        self.assertEqual(content.count("公告 ID：`first`"), 1)
        self.assertIn("更新後的摘要", content)
        self.assertNotIn("完整 AI 摘要", content)
        self.assertEqual(self.storage.count(), 2)

    def test_startup_backfills_all_legacy_records_and_converts_timezone(self):
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.executemany(
                "INSERT INTO announcements (id, title, url, created_at) VALUES (?, ?, ?, ?)",
                [(f"legacy-{i}", "舊公告", "https://example.com", "2026-09-19T21:35:04")
                 for i in range(1001)]
                + [("utc", "UTC 公告", "https://example.com", "2026-11-12T17:00:00+00:00")],
            )
        Storage(self.db_path)
        legacy = (self.daily_dir / "2026-09-19.md").read_text(encoding="utf-8")
        self.assertEqual(legacy.count("公告 ID："), 1001)
        self.assertIn("尚無 AI 摘要", legacy)
        self.assertIn("`utc`", (self.daily_dir / "2026-11-13.md").read_text(encoding="utf-8"))

    def test_no_announcements_creates_no_daily_file(self):
        self.assertEqual(list(self.daily_dir.glob("*.md")), [])

    def test_seed_record_explains_missing_historical_summary(self):
        self.save("seed", summary="[Baseline seed record]")
        content = (self.daily_dir / "2026-11-12.md").read_text(encoding="utf-8")
        self.assertIn("初始化歷史紀錄，未保存 AI 摘要", content)
        self.assertNotIn("[Baseline seed record]", content)

    def test_export_failure_is_reported_and_recovered_on_restart(self):
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.save("recoverable")
        self.assertTrue(self.storage.is_processed("recoverable"))
        Storage(self.db_path)
        output = self.daily_dir / "2026-11-12.md"
        self.assertIn("`recoverable`", output.read_text(encoding="utf-8"))
        modified = output.stat().st_mtime_ns
        Storage(self.db_path)
        self.assertEqual(output.stat().st_mtime_ns, modified)


if __name__ == "__main__":
    unittest.main()
