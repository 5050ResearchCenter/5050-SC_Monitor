import io
import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from unittest.mock import patch

from blive_handler import DEBUG_FALLBACK_MESSAGES
from dpsk_client import (
    DPSKClient,
    DPSK_MAX_CONCURRENCY,
    DPSK_MODEL,
    DPSK_MODELS_URL,
    DPSK_PROMPT,
    normalize_steam_id,
)


class _FakeResponse:
    def __init__(self, content):
        self._body = json.dumps({
            "choices": [{"message": {"content": content}}],
        }).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self._body


class _FakeJSONResponse(_FakeResponse):
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")


class NormalizeSteamIdTests(unittest.TestCase):
    def test_none_markers_and_friend_codes_are_ignored(self):
        for content in (None, "", "无", "无。", " 123456789 ", "123456。", "123456\n这是好友码", "未找到"):
            with self.subTest(content=content):
                self.assertIsNone(normalize_steam_id(content))

    def test_steam_id_is_cleaned(self):
        self.assertEqual(normalize_steam_id("Steam ID： player_one "), "player_one")
        self.assertEqual(normalize_steam_id("`player-two`"), "player-two")


class DPSKClientTests(unittest.TestCase):
    @patch("dpsk_client.urlopen")
    def test_token_validation_uses_models_endpoint(self, mock_urlopen):
        mock_urlopen.return_value = _FakeJSONResponse({
            "object": "list",
            "data": [{"id": DPSK_MODEL, "object": "model", "owned_by": "deepseek"}],
        })

        is_valid = DPSKClient("test-token").validate_token()

        self.assertTrue(is_valid)
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, DPSK_MODELS_URL)
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")

    @patch("dpsk_client.urlopen")
    def test_token_validation_returns_false_for_http_401(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url=DPSK_MODELS_URL,
            code=401,
            msg="Authentication Fails",
            hdrs={},
            fp=io.BytesIO(),
        )

        self.assertFalse(DPSKClient("invalid-token").validate_token())

    @patch("dpsk_client.urlopen")
    def test_token_validation_does_not_call_api_when_token_is_blank(self, mock_urlopen):
        self.assertFalse(DPSKClient("  ").validate_token())
        mock_urlopen.assert_not_called()

    @patch("dpsk_client.urlopen")
    def test_flash_model_request_and_result(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse("player_one")

        result = DPSKClient("test-token").extract_steam_id("Steam 是 player_one")

        self.assertEqual(result, "player_one")
        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], DPSK_MODEL)
        self.assertEqual(payload["messages"][0]["content"], DPSK_PROMPT)
        self.assertEqual(payload["thinking"], {"type": "enabled"})
        self.assertEqual(payload["reasoning_effort"], "high")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")

    @patch("dpsk_client.urlopen")
    def test_all_real_sc_samples_are_forwarded_unchanged(self, mock_urlopen):
        samples = DEBUG_FALLBACK_MESSAGES
        mock_urlopen.side_effect = [_FakeResponse("无") for _ in samples]
        client = DPSKClient("test-token")

        results = [client.extract_steam_id(sample) for sample in samples]

        self.assertTrue(all(result is None for result in results))
        forwarded_samples = [
            json.loads(call.args[0].data.decode("utf-8"))["messages"][1]["content"]
            for call in mock_urlopen.call_args_list
        ]
        self.assertEqual(forwarded_samples, list(samples))

    @patch("dpsk_client.time.sleep")
    @patch("dpsk_client.urlopen")
    def test_http_429_uses_retry_after_and_retries(self, mock_urlopen, mock_sleep):
        rate_limited = HTTPError(
            url="https://api.deepseek.com/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "0.25"},
            fp=io.BytesIO(),
        )
        mock_urlopen.side_effect = [rate_limited, _FakeResponse("player_one")]

        result = DPSKClient("test-token").extract_steam_id("id: player_one")

        self.assertEqual(result, "player_one")
        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_called_once_with(0.25)

    def test_requests_are_limited_to_16_concurrent_calls(self):
        active = 0
        maximum_active = 0
        lock = threading.Lock()
        release = threading.Event()

        def tracked_urlopen(_request, timeout):
            nonlocal active, maximum_active
            self.assertGreater(timeout, 0)
            with lock:
                active += 1
                maximum_active = max(maximum_active, active)
                if active == DPSK_MAX_CONCURRENCY:
                    release.set()
            release.wait(timeout=1)
            with lock:
                active -= 1
            return _FakeResponse("无")

        client = DPSKClient("test-token")
        with (
            patch("dpsk_client.urlopen", side_effect=tracked_urlopen),
            ThreadPoolExecutor(max_workers=20) as executor,
        ):
            results = list(executor.map(client.extract_steam_id, ["无 ID"] * 20))

        self.assertTrue(all(result is None for result in results))
        self.assertEqual(maximum_active, DPSK_MAX_CONCURRENCY)


if __name__ == "__main__":
    unittest.main()
