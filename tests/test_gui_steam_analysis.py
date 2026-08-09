import unittest
from unittest.mock import Mock

from gui import SCMonitorApp
from models import UserInfo, UserVipLevel


class SteamAnalysisDispatchTests(unittest.TestCase):
    @staticmethod
    def _make_app(has_dpsk_client=True):
        app = SCMonitorApp.__new__(SCMonitorApp)
        app._dpsk_client = object() if has_dpsk_client else None
        app._alloc_sc_idx = 1
        app._user_info = {}
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


if __name__ == "__main__":
    unittest.main()
