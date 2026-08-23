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


class _FakeStore:
    def __init__(self):
        self.reassignments = []

    def reassign_user_uid_for_nickname(self, nickname, user_uid):
        self.reassignments.append((nickname, user_uid))
        return 1


class DebugSamplesTests(unittest.TestCase):
    def test_all_real_sc_samples_are_embedded(self):
        self.assertIn("BV1NoNN6MEse", DEBUG_FALLBACK_MESSAGES)
        self.assertTrue(any("272960172" in message for message in DEBUG_FALLBACK_MESSAGES))

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

    def test_repeated_debug_user_has_a_stable_uid_for_statistics(self):
        app = _FakeApp()
        app._sc_store = _FakeStore()
        sleep_count = 0

        async def stop_after_two_messages(_seconds):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count >= 3:
                raise asyncio.CancelledError

        with (
            patch("blive_handler.DEBUG_FALLBACK_MESSAGES", ("第一条", "第二条")),
            patch("blive_handler.DEBUG_FAKE_USERS", ("固定测试用户",)),
            patch("blive_handler.random.choice", side_effect=lambda values: values[0]),
            patch("blive_handler.asyncio.sleep", side_effect=stop_after_two_messages),
        ):
            asyncio.run(_run_fake_blivedm(app, config=None))

        self.assertEqual([record["user"].uid for record in app.records], [-1, -1])
        self.assertEqual(app._sc_store.reassignments, [("固定测试用户", -1)])


if __name__ == "__main__":
    unittest.main()
