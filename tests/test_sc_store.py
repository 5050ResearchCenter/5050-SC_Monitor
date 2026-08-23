import json
import sqlite3
import tempfile
from pathlib import Path
import unittest
from contextlib import closing

from sc_store import SCStore


class SCStoreTests(unittest.TestCase):
    def test_records_submission_fields_and_persists_user_totals(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "sc.sqlite3"
            store = SCStore(database_path)

            first = store.record_sc(
                user_uid=42,
                nickname="投稿人",
                content="BV1NoNN6MEse",
                amount=30,
                sent_at=100,
                bv="BV1NoNN6MEse",
            )
            second = store.record_sc(
                user_uid=42,
                nickname="投稿人新昵称",
                content="第二次投稿",
                amount=20,
                sent_at=101,
                bv=None,
            )

            self.assertEqual(first.stats.count, 1)
            self.assertEqual(first.stats.total_amount, 30)
            self.assertEqual(second.stats.count, 2)
            self.assertEqual(second.stats.total_amount, 50)
            self.assertEqual(SCStore(database_path).get_user_stats(42), second.stats)

            with closing(sqlite3.connect(database_path)) as connection:
                row = connection.execute(
                    "SELECT nickname, content, amount FROM super_chats WHERE id = ?",
                    (first.id,),
                ).fetchone()
            self.assertEqual(row, ("投稿人", "BV1NoNN6MEse", 30.0))

    def test_video_metadata_and_blacklist_result_are_stored(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "sc.sqlite3"
            store = SCStore(database_path)
            stored = store.record_sc(
                user_uid=42,
                nickname="投稿人",
                content="BV1NoNN6MEse",
                amount=30,
                sent_at=100,
                bv="BV1NoNN6MEse",
            )

            store.update_video_metadata(
                stored.id,
                title="荒野大啾比",
                tags=("菲比啾比", "鸣潮"),
                blacklisted=True,
                blacklist_matches=("啾比", "鸣潮"),
            )

            with closing(sqlite3.connect(database_path)) as connection:
                row = connection.execute(
                    """
                    SELECT video_title, video_tags, blacklisted, blacklist_matches
                    FROM super_chats WHERE id = ?
                    """,
                    (stored.id,),
                ).fetchone()
            self.assertEqual(row[0], "荒野大啾比")
            self.assertEqual(json.loads(row[1]), ["菲比啾比", "鸣潮"])
            self.assertEqual(row[2], 1)
            self.assertEqual(json.loads(row[3]), ["啾比", "鸣潮"])

    def test_legacy_debug_rows_can_be_reassigned_to_a_stable_uid(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SCStore(Path(directory) / "sc.sqlite3")
            store.record_sc(
                user_uid=1,
                nickname="调试_阿木木",
                content="第一次",
                amount=30,
                sent_at=100,
                bv=None,
            )
            store.record_sc(
                user_uid=2,
                nickname="调试_阿木木",
                content="第二次",
                amount=50,
                sent_at=101,
                bv=None,
            )

            updated = store.reassign_user_uid_for_nickname("调试_阿木木", -2)

            self.assertEqual(updated, 2)
            self.assertEqual(store.get_user_stats(-2).count, 2)
            self.assertEqual(store.get_user_stats(-2).total_amount, 80)


if __name__ == "__main__":
    unittest.main()
