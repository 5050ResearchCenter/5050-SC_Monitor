import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from blive_handler import SCHandler
from gui import SCMonitorApp
from models import UserInfo, UserVipLevel


class GuardIdentityTests(unittest.TestCase):
    def test_sc_uses_sender_guard_level_from_current_room(self):
        app = Mock()
        handler = SCHandler.__new__(SCHandler)
        handler._app = app
        message = SimpleNamespace(
            uname="舰长用户",
            uid=42,
            guard_level=3,
            price=30,
            message="测试 SC",
            start_time=123,
        )

        handler._on_super_chat(None, message)

        user = app.add_sc.call_args.kwargs["user"]
        self.assertEqual(user.vip_level, UserVipLevel.VIP1)

    def test_unknown_guard_level_falls_back_to_normal(self):
        self.assertEqual(
            UserVipLevel.from_guard_level(None),
            UserVipLevel.Normal,
        )
        self.assertEqual(
            UserVipLevel.from_guard_level(99),
            UserVipLevel.Normal,
        )


class GuardHighlightTests(unittest.TestCase):
    def test_sc_rows_use_configured_guard_color_tags(self):
        cases = (
            (UserVipLevel.VIP1, "vip1"),
            (UserVipLevel.VIP2, "vip2"),
            (UserVipLevel.VIP3, "vip3"),
        )
        for vip_level, expected_tag in cases:
            with self.subTest(vip_level=vip_level):
                app = SCMonitorApp.__new__(SCMonitorApp)
                app.tree = Mock()
                app.tree.get_children.return_value = ("sc_1",)
                app._sc_records = [{
                    "id": 1,
                    "vip_level": vip_level,
                    "price_value": 30,
                }]
                app._clicked_bv_items = []

                app._apply_highlights()

                app.tree.item.assert_called_once_with(
                    "sc_1",
                    tags=(expected_tag,),
                )

    def test_each_guard_danmaku_switch_updates_its_own_config(self):
        cases = (
            (UserVipLevel.VIP1, "show_user_vip1", "舰长弹幕: 开"),
            (UserVipLevel.VIP2, "show_user_vip2", "提督弹幕: 开"),
            (UserVipLevel.VIP3, "show_user_vip3", "总督弹幕: 开"),
        )
        for vip_level, config_attr, expected_text in cases:
            with self.subTest(vip_level=vip_level):
                app = SCMonitorApp.__new__(SCMonitorApp)
                app.config = SimpleNamespace(
                    show_user_vip1=False,
                    show_user_vip2=False,
                    show_user_vip3=False,
                    save=Mock(),
                )
                app._show_user_vip_vars = {vip_level: Mock()}
                app._show_user_vip_vars[vip_level].get.return_value = True
                app._btn_show_user_vip = {vip_level: Mock()}

                app._toggle_vip_danmaku(vip_level)

                self.assertTrue(getattr(app.config, config_attr))
                app.config.save.assert_called_once_with()
                app._btn_show_user_vip[vip_level].config.assert_called_once_with(
                    text=expected_text
                )

    def test_guard_danmaku_switches_filter_each_level_independently(self):
        app = SCMonitorApp.__new__(SCMonitorApp)
        app.config = SimpleNamespace(
            special_users=[],
            special_users_uid=[],
            show_user_vip1=False,
            show_user_vip2=True,
            show_user_vip3=False,
        )
        app._alloc_sc_idx = 1
        app.root = Mock()

        app.add_danmaku(
            UserInfo("舰长用户", 1, UserVipLevel.VIP1),
            "舰长弹幕",
            100,
        )
        app.root.after.assert_not_called()

        app.add_danmaku(
            UserInfo("提督用户", 2, UserVipLevel.VIP2),
            "提督弹幕",
            101,
        )
        record = app.root.after.call_args.args[2]
        self.assertEqual(record["uid"], 2)
        self.assertEqual(record["vip_level"], UserVipLevel.VIP2)
        self.assertEqual(record["message"], "提督弹幕")


if __name__ == "__main__":
    unittest.main()
