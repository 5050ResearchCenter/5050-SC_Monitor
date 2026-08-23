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


if __name__ == "__main__":
    unittest.main()
