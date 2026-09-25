from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

from sc_store import SCStore
from webui_server import DEFAULT_WEBUI_PORT, WebUIServer


class WebUIServerTests(unittest.TestCase):
    def test_default_port_is_5050(self):
        server = WebUIServer(self.store)

        self.assertEqual(server.port, DEFAULT_WEBUI_PORT)
        self.assertEqual(server.port, 5050)

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        static_path = root / "static"
        static_path.mkdir()
        (static_path / "index.html").write_text("<h1>SC Monitor</h1>", encoding="utf-8")
        self.store = SCStore(root / "sc.sqlite3")
        self.store.record_sc(
            user_uid=42,
            nickname="测试用户",
            content="测试内容",
            amount=30,
            sent_at=int(datetime.now().timestamp()),
            bv=None,
        )
        self.server = WebUIServer(self.store, static_path, port=0)
        self.url = self.server.start()

    def tearDown(self):
        self.server.stop()
        self.temporary_directory.cleanup()

    def get_json(self, path):
        with urlopen(self.url + path, timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_serves_static_frontend_and_paginated_records(self):
        with urlopen(self.url, timeout=2) as response:
            self.assertIn("SC Monitor", response.read().decode("utf-8"))

        result = self.get_json("api/super-chats?page=1&pageSize=20")

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["userUid"], 42)
        self.assertEqual(result["items"][0]["content"], "测试内容")

    def test_summary_and_user_search_endpoints(self):
        selected_date = datetime.now().strftime("%Y-%m-%d")

        summary = self.get_json(f"api/summary?date={selected_date}")
        users = self.get_json("api/users?q=" + quote("测试"))

        self.assertEqual(summary["totalCount"], 1)
        self.assertEqual(summary["totalAmount"], 30)
        self.assertEqual(users["items"][0]["userUid"], 42)
        self.assertEqual(users["items"][0]["amountDistribution"][0]["count"], 1)

    def test_rejects_invalid_parameters(self):
        with self.assertRaises(HTTPError) as context:
            urlopen(self.url + "api/summary?date=invalid", timeout=2)
        self.assertEqual(context.exception.code, 400)
        context.exception.close()

        with self.assertRaises(HTTPError) as context:
            urlopen(self.url + "api/super-chats?pageSize=25", timeout=2)
        self.assertEqual(context.exception.code, 400)
        context.exception.close()

    def test_blacklisted_records_require_explicit_toggle_parameter(self):
        blocked = self.store.record_sc(
            user_uid=42,
            nickname="测试用户",
            content="屏蔽内容",
            amount=50,
            sent_at=int(datetime.now().timestamp()),
            bv=None,
        )
        self.store.update_video_metadata(
            blocked.id,
            title="屏蔽视频",
            tags=("屏蔽",),
            blacklisted=True,
            blacklist_matches=("屏蔽",),
        )

        default_page = self.get_json("api/super-chats?page=1&pageSize=20")
        complete_page = self.get_json(
            "api/super-chats?page=1&pageSize=20&includeBlacklisted=true"
        )
        users = self.get_json("api/users?q=42")

        self.assertEqual(default_page["total"], 1)
        self.assertEqual(complete_page["total"], 2)
        self.assertEqual(users["items"][0]["blacklistedCount"], 1)

if __name__ == "__main__":
    unittest.main()
