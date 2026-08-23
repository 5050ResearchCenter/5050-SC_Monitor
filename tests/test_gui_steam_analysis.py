import unittest
import queue
from unittest.mock import Mock, patch

from gui import SCMonitorApp
from models import UserInfo, UserVipLevel
from sc_store import StoredSC, UserSCStats


class SteamAnalysisDispatchTests(unittest.TestCase):
    @staticmethod
    def _make_app(has_dpsk_client=True):
        app = SCMonitorApp.__new__(SCMonitorApp)
        app._dpsk_client = object() if has_dpsk_client else None
        app._alloc_sc_idx = 1
        app._user_info = {}
        app._sc_store = Mock()
        app._sc_store.record_sc.return_value = StoredSC(
            id=17,
            stats=UserSCStats(count=4, total_amount=95),
        )
        app.root = Mock()
        return app

    @staticmethod
    def _user():
        return UserInfo(uname="测试用户", uid=1, vip_level=UserVipLevel.Normal)

    def test_sc_with_bv_skips_steam_analysis(self):
        app = self._make_app()

        app.add_sc(self._user(), 30, "看看这个 BV1vK411K7ZF", 1)

        record = app.root.after.call_args.args[2]
        self.assertEqual(record["bv"], "BV1vK411K7ZF")
        self.assertEqual(record["steam_analysis_status"], "skipped_bv")

    def test_sc_without_bv_is_queued_for_steam_analysis(self):
        app = self._make_app()

        app.add_sc(self._user(), 30, "求好友，id:player_one", 1)

        record = app.root.after.call_args.args[2]
        self.assertEqual(record["bv"], "-")
        self.assertEqual(record["steam_analysis_status"], "pending")

    def test_sc_is_persisted_and_database_stats_are_attached(self):
        app = self._make_app()

        app.add_sc(self._user(), 30, "看看 BV1NoNN6MEse", 123)

        app._sc_store.record_sc.assert_called_once_with(
            user_uid=1,
            nickname="测试用户",
            content="看看 BV1NoNN6MEse",
            amount=30.0,
            sent_at=123,
            bv="BV1NoNN6MEse",
        )
        record = app.root.after.call_args.args[2]
        self.assertEqual(record["db_id"], 17)
        self.assertEqual(record["user_sc_count"], 4)
        self.assertEqual(record["user_sc_total"], 95)

    def test_clicking_steam_id_marks_row_and_copies_id(self):
        app = SCMonitorApp.__new__(SCMonitorApp)
        app.tree = Mock()
        app.tree.identify_region.return_value = "cell"
        app.tree.identify_row.return_value = "sc_1"
        app.tree.identify_column.return_value = "#5"
        app._sc_records = [{"id": 1, "steam_id": "player_one", "bv": "-"}]
        app._select_item = Mock()
        app._mark_row = Mock()
        app._copy_to_clipboard = Mock()
        app.set_status = Mock()
        event = Mock(x=10, y=10)

        app._on_click(event)

        app._mark_row.assert_called_once_with("sc_1")
        app._copy_to_clipboard.assert_called_once_with("player_one")
        app.set_status.assert_called_once_with("📋 已复制 Steam ID: player_one")

    def test_copying_to_clipboard_shows_tip(self):
        app = SCMonitorApp.__new__(SCMonitorApp)
        app.root = Mock()
        app._show_tip = Mock()

        app._copy_to_clipboard("player_one")

        app.root.clipboard_clear.assert_called_once_with()
        app.root.clipboard_append.assert_called_once_with("player_one")
        app._show_tip.assert_called_once_with("已复制")

    def test_new_sc_updates_all_visible_rows_for_the_same_user(self):
        app = SCMonitorApp.__new__(SCMonitorApp)
        app._sc_records = [{
            "id": 1,
            "uid": 42,
            "user_sc_count": 1,
            "user_sc_total": 30,
        }]
        app._write_sc_log = Mock()
        app._refresh_sc_list = Mock()
        new_record = {
            "id": 2,
            "uid": 42,
            "user_sc_count": 2,
            "user_sc_total": 80,
        }

        app._append_sc_record(new_record)

        self.assertEqual(app._sc_records[0]["user_sc_count"], 2)
        self.assertEqual(app._sc_records[0]["user_sc_total"], 80)
        self.assertEqual(new_record["user_sc_count"], 2)
        self.assertEqual(new_record["user_sc_total"], 80)

    @patch("gui.messagebox.showwarning")
    def test_dpsk_warning_is_a_closeable_modal_dialog(self, mock_showwarning):
        app = SCMonitorApp.__new__(SCMonitorApp)
        app.root = Mock()

        app._show_dpsk_token_warning("未填写 DPSK_API_TOKEN。")

        mock_showwarning.assert_called_once_with(
            "DeepSeek API Token 警告",
            "未填写 DPSK_API_TOKEN。\n\n请在 sc_config.json 中填写有效 token 后重启程序。",
            parent=app.root,
        )

    def test_invalid_dpsk_token_disables_analysis_and_shows_warning(self):
        app = SCMonitorApp.__new__(SCMonitorApp)
        app._dpsk_client = object()
        app._dpsk_validation_queue = queue.SimpleQueue()
        app._dpsk_validation_queue.put((False, None))
        app._show_dpsk_token_warning = Mock()

        app._poll_dpsk_validation_results()

        self.assertIsNone(app._dpsk_client)
        app._show_dpsk_token_warning.assert_called_once()

    def test_network_error_does_not_claim_token_is_invalid(self):
        app = SCMonitorApp.__new__(SCMonitorApp)
        client = object()
        app._dpsk_client = client
        app._dpsk_validation_queue = queue.SimpleQueue()
        app._dpsk_validation_queue.put((None, "网络超时"))
        app._show_dpsk_token_warning = Mock()

        app._poll_dpsk_validation_results()

        self.assertIs(app._dpsk_client, client)
        app._show_dpsk_token_warning.assert_not_called()


if __name__ == "__main__":
    unittest.main()
