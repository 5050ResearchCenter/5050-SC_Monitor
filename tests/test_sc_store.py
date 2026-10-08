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

    def test_dashboard_summary_groups_amounts_and_ranks_users(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SCStore(Path(directory) / "sc.sqlite3")
            for uid, nickname, amount, timestamp in (
                (1, "甲旧昵称", 30, 100),
                (1, "甲新昵称", 50, 110),
                (2, "乙", 100, 120),
                (3, "范围外", 100, 300),
            ):
                store.record_sc(
                    user_uid=uid,
                    nickname=nickname,
                    content="测试",
                    amount=amount,
                    sent_at=timestamp,
                    bv=None,
                )

            summary = store.get_daily_summary(100, 200)

            self.assertEqual(summary["totalCount"], 3)
            self.assertEqual(summary["totalAmount"], 180)
            self.assertEqual(
                [(item["amount"], item["count"]) for item in summary["amountDistribution"]],
                [(30, 1), (50, 1), (100, 1)],
            )
            self.assertEqual(summary["countRanking"][0]["userUid"], 1)
            self.assertEqual(summary["countRanking"][0]["nickname"], "甲新昵称")
            self.assertEqual(summary["amountRanking"][0]["userUid"], 2)

    def test_user_search_uses_aliases_and_page_filter_uses_uid(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SCStore(Path(directory) / "sc.sqlite3")
            for nickname, timestamp in (("旧名字", 100), ("新名字", 200)):
                store.record_sc(
                    user_uid=42,
                    nickname=nickname,
                    content=nickname,
                    amount=30,
                    sent_at=timestamp,
                    bv=None,
                )
            store.record_sc(
                user_uid=7,
                nickname="其他人",
                content="其他",
                amount=50,
                sent_at=300,
                bv=None,
            )

            matches = store.search_users("旧名")
            page = store.get_super_chats_page(page=1, page_size=20, user_uid=42)

            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["userUid"], 42)
            self.assertEqual(matches[0]["nickname"], "新名字")
            self.assertEqual(matches[0]["aliases"], ["新名字", "旧名字"])
            self.assertEqual(
                [(item["amount"], item["count"]) for item in matches[0]["amountDistribution"]],
                [(30, 2)],
            )
            self.assertEqual(page["total"], 2)
            self.assertEqual([item["nickname"] for item in page["items"]], ["新名字", "旧名字"])

    def test_exact_nickname_match_is_first_for_direct_filtering(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SCStore(Path(directory) / "sc.sqlite3")
            for uid, nickname, timestamp in (
                (1, "目标用户", 100),
                (2, "目标用户的朋友", 200),
            ):
                store.record_sc(
                    user_uid=uid,
                    nickname=nickname,
                    content="测试",
                    amount=30,
                    sent_at=timestamp,
                    bv=None,
                )

            matches = store.search_users("目标用户")

            self.assertEqual(matches[0]["userUid"], 1)

    def test_blacklisted_rows_are_hidden_by_default_but_counted_in_user_stats(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SCStore(Path(directory) / "sc.sqlite3")
            store.record_sc(
                user_uid=42,
                nickname="投稿人",
                content="正常记录",
                amount=30,
                sent_at=100,
                bv=None,
            )
            blocked = store.record_sc(
                user_uid=42,
                nickname="投稿人",
                content="屏蔽记录",
                amount=50,
                sent_at=200,
                bv="BV1NoNN6MEse",
            )
            store.update_video_metadata(
                blocked.id,
                title="屏蔽视频",
                tags=("屏蔽",),
                blacklisted=True,
                blacklist_matches=("屏蔽",),
            )

            default_page = store.get_super_chats_page(page=1, page_size=20, user_uid=42)
            complete_page = store.get_super_chats_page(
                page=1,
                page_size=20,
                user_uid=42,
                include_blacklisted=True,
            )
            user = store.search_users("42")[0]

            self.assertEqual(default_page["total"], 1)
            self.assertEqual(default_page["items"][0]["content"], "正常记录")
            self.assertEqual(complete_page["total"], 2)
            self.assertEqual(user["count"], 2)
            self.assertEqual(user["blacklistedCount"], 1)
            self.assertEqual(
                [(item["amount"], item["count"]) for item in user["amountDistribution"]],
                [(30, 1), (50, 1)],
            )


if __name__ == "__main__":
    unittest.main()
