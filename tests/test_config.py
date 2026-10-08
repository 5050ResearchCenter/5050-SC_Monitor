import unittest

from config import AppConfig


class ConfigTests(unittest.TestCase):
    def test_blacklist_loads_from_chinese_config_key(self):
        config = AppConfig.model_validate({"黑名单关键词": ["啾比", "鸣潮"]})

        self.assertEqual(config.blacklist, ["啾比", "鸣潮"])
        self.assertEqual(
            config.model_dump(by_alias=True)["黑名单关键词"],
            ["啾比", "鸣潮"],
        )

    def test_guard_danmaku_switches_and_colors_load_independently(self):
        config = AppConfig.model_validate({
            "显示舰长弹幕": True,
            "显示提督弹幕": False,
            "显示总督弹幕": True,
            "颜色_舰长弹幕": "#111111",
            "颜色_提督弹幕": "#222222",
            "颜色_总督弹幕": "#333333",
        })

        self.assertTrue(config.show_user_vip1)
        self.assertFalse(config.show_user_vip2)
        self.assertTrue(config.show_user_vip3)
        self.assertEqual(config.color_user_vip1, "#111111")
        self.assertEqual(config.color_user_vip2, "#222222")
        self.assertEqual(config.color_user_vip3, "#333333")


if __name__ == "__main__":
    unittest.main()
