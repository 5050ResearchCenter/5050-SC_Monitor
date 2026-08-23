import queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from bilibili_client import VideoMetadata
from gui import SCMonitorApp
from sc_store import UserSCStats
from utils import match_blacklist


class BlacklistTests(unittest.TestCase):
    def test_example_bv_metadata_matches_both_configured_keywords(self):
        matches = match_blacklist(
            "荒野大啾比",
            ["搞笑", "菲比啾比", "鸣潮"],
            ["啾比", "鸣潮"],
        )

        self.assertEqual(matches, ["啾比", "鸣潮"])

    def test_match_is_case_insensitive_and_ignores_empty_keywords(self):
        self.assertEqual(match_blacklist("ABC title", [], [" abc ", "", "ABC"]), ["abc"])

    def test_blacklisted_sc_is_not_visible_even_when_selected(self):
        app = SCMonitorApp.__new__(SCMonitorApp)
        blocked = {
            "id": 1,
            "bv": "BV1NoNN6MEse",
            "blacklisted": True,
            "price_value": 30,
        }
        visible = {
            "id": 2,
            "bv": "BV1Another01",
            "blacklisted": False,
            "price_value": 30,
        }
        app._sc_records = [blocked, visible]
        app.config = SimpleNamespace(blacklist=["啾比", "鸣潮"])
        app._selected_item = "sc_1"
        app._filter_2_yuan_var = Mock()
        app._filter_2_yuan_var.get.return_value = False

        self.assertEqual(app.get_visible_scs(), [visible])

    def test_bv_sc_waits_for_blacklist_check_before_becoming_visible(self):
        app = SCMonitorApp.__new__(SCMonitorApp)
        pending = {
            "id": 1,
            "bv": "BV1NoNN6MEse",
            "blacklisted": False,
            "video_metadata_status": "pending",
            "price_value": 30,
        }
        app._sc_records = [pending]
        app.config = SimpleNamespace(blacklist=["啾比", "鸣潮"])
        app._selected_item = None
        app._filter_2_yuan_var = Mock()
        app._filter_2_yuan_var.get.return_value = False

        self.assertEqual(app.get_visible_scs(), [])

        pending["video_metadata_status"] = "done"
        self.assertEqual(app.get_visible_scs(), [pending])

    def test_video_result_updates_ui_record_and_database(self):
        app = SCMonitorApp.__new__(SCMonitorApp)
        record = {
            "id": 1,
            "db_id": 9,
            "bv": "BV1NoNN6MEse",
            "video_metadata_status": "pending",
        }
        metadata = VideoMetadata(
            title="荒野大啾比",
            tags=("菲比啾比", "鸣潮"),
        )
        app._video_result_queue = queue.SimpleQueue()
        app._video_result_queue.put((1, 9, metadata, None))
        app._sc_records = [record]
        app.config = SimpleNamespace(blacklist=["啾比", "鸣潮"])
        app._sc_store = Mock()
        app._refresh_sc_list = Mock()
        app.set_status = Mock()
        app.root = Mock()
        app._is_closing = False

        app._poll_video_results()

        self.assertTrue(record["blacklisted"])
        self.assertEqual(record["blacklist_matches"], ["啾比", "鸣潮"])
        self.assertEqual(record["video_title"], "荒野大啾比")
        app._sc_store.update_video_metadata.assert_called_once_with(
            9,
            title="荒野大啾比",
            tags=("菲比啾比", "鸣潮"),
            blacklisted=True,
            blacklist_matches=["啾比", "鸣潮"],
        )

    def test_hover_text_includes_stats_and_metadata(self):
        content = SCMonitorApp._format_bv_tooltip({
            "uname": "投稿人",
            "user_sc_count": 3,
            "user_sc_total": 80,
            "video_metadata_status": "done",
            "video_title": "荒野大啾比",
            "video_tags": ["鸣潮"],
        })

        self.assertIn("累计发送：3 次", content)
        self.assertIn("累计金额：¥80", content)
        self.assertIn("标题：荒野大啾比", content)
        self.assertIn("标签：鸣潮", content)

    def test_hovering_bv_cell_opens_statistics_tooltip(self):
        app = SCMonitorApp.__new__(SCMonitorApp)
        app.tree = Mock()
        app.tree.identify_region.return_value = "cell"
        app.tree.identify_column.return_value = "#5"
        app.tree.identify_row.return_value = "sc_1"
        app._sc_records = [{
            "id": 1,
            "uid": 42,
            "uname": "投稿人",
            "bv": "BV1NoNN6MEse",
            "user_sc_count": 3,
            "user_sc_total": 80,
            "video_metadata_status": "done",
            "video_title": "荒野大啾比",
            "video_tags": ["鸣潮"],
            "blacklist_matches": ["啾比", "鸣潮"],
        }]
        app._sc_store = Mock()
        app._sc_store.get_user_stats.return_value = UserSCStats(
            count=4,
            total_amount=110,
        )
        app._hover_item = None
        app._hover_content = None
        app._show_hover_tip = Mock()
        event = Mock(x=5, y=6, x_root=100, y_root=200)

        app._on_tree_motion(event)

        app._show_hover_tip.assert_called_once()
        call = app._show_hover_tip.call_args.args
        self.assertEqual(call[0], "sc_1")
        self.assertIn("累计发送：4 次", call[1])
        self.assertIn("累计金额：¥110", call[1])
        app._sc_store.get_user_stats.assert_called_once_with(42)


if __name__ == "__main__":
    unittest.main()
