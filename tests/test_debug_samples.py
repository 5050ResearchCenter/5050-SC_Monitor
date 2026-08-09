import asyncio
import unittest
from unittest.mock import patch

from blive_handler import DEBUG_FALLBACK_MESSAGES, _run_fake_blivedm


class _FakeRoot:
    def after(self, _delay, callback):
        callback()


class _FakeApp:
    def __init__(self):
        self.root = _FakeRoot()
        self.records = []

    def set_status(self, _status):
        pass

    def on_danmaku_heartbeat(self):
        pass

    def add_sc(self, **record):
        self.records.append(record)

    def add_danmaku(self, **_record):
        raise AssertionError("内置的真实 SC 不应作为普通弹幕发送")


class DebugSamplesTests(unittest.TestCase):
    def test_all_real_sc_samples_are_embedded(self):
        self.assertEqual(len(DEBUG_FALLBACK_MESSAGES), 48)
        self.assertTrue(any("272960172" in message for message in DEBUG_FALLBACK_MESSAGES))
        self.assertTrue(any("ID：MendelTheF1sh" in message for message in DEBUG_FALLBACK_MESSAGES))

    def test_debug_source_sends_samples_as_scs_in_file_order(self):
        app = _FakeApp()
        sleep_count = 0

        async def stop_after_two_messages(_seconds):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count >= 3:
                raise asyncio.CancelledError

        with (
            patch("blive_handler.DEBUG_FALLBACK_MESSAGES", ("第一条 SC", "第二条 SC")),
            patch("blive_handler.asyncio.sleep", side_effect=stop_after_two_messages),
        ):
            asyncio.run(_run_fake_blivedm(app, config=None))

        self.assertEqual(
            [record["message"] for record in app.records],
            ["第一条 SC", "第二条 SC"],
        )


if __name__ == "__main__":
    unittest.main()
