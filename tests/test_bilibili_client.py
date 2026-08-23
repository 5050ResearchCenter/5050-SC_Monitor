import json
import unittest
from unittest.mock import patch

from bilibili_client import BilibiliClient


class _FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self._body


class BilibiliClientTests(unittest.TestCase):
    @patch("bilibili_client.urlopen")
    def test_fetches_title_and_tags_for_bv(self, mock_urlopen):
        mock_urlopen.side_effect = [
            _FakeResponse({"code": 0, "data": {"title": "荒野大啾比"}}),
            _FakeResponse({
                "code": 0,
                "data": [
                    {"tag_name": "菲比啾比"},
                    {"tag_name": "鸣潮"},
                ],
            }),
        ]

        metadata = BilibiliClient().fetch_video_metadata("BV1NoNN6MEse")

        self.assertEqual(metadata.title, "荒野大啾比")
        self.assertEqual(metadata.tags, ("菲比啾比", "鸣潮"))
        self.assertIsNone(metadata.tag_error)
        requested_urls = [call.args[0].full_url for call in mock_urlopen.call_args_list]
        self.assertTrue(all("bvid=BV1NoNN6MEse" in url for url in requested_urls))

    @patch("bilibili_client.urlopen")
    def test_result_is_cached_by_bv(self, mock_urlopen):
        mock_urlopen.side_effect = [
            _FakeResponse({"code": 0, "data": {"title": "荒野大啾比"}}),
            _FakeResponse({"code": 0, "data": []}),
        ]
        client = BilibiliClient()

        first = client.fetch_video_metadata("BV1NoNN6MEse")
        second = client.fetch_video_metadata("BV1NoNN6MEse")

        self.assertIs(first, second)
        self.assertEqual(mock_urlopen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
