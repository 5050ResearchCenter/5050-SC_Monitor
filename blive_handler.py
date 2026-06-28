import asyncio
from enum import IntEnum
import http.cookies
import logging
import os
import random
import time

import aiohttp
import blivedm
from blivedm.models.web import DanmakuMessage, SuperChatMessage

from models import UserInfo, UserVipLevel

logger = logging.getLogger(__name__)

DEBUG_FAKE_PRICES = (2, 30, 50, 100)
DEBUG_FAKE_USERS = (
    "调试_阿木木",
    "调试_男搓背",
    "调试_KurikoMoe",
    "调试_Ebe",
    "调试_EdmundDZhang",
)
DEBUG_FAKE_MESSAGES = (
    "调试 SC：测试醒目留言展示",
    "调试 SC：BV1vK411K7ZF",
    "调试 SC：分隔BV.1.G.S.4.y.1.J.7.e.J测试",
    "调试 SC：阿巴阿巴BV1E阿坝f4y1X7er",
)


def _is_debug_fake_source_enabled():
    return os.getenv("DEBUG", "").strip().lower() == "on"



BaseHandler = blivedm.BaseHandler if blivedm else object
class SCHandler(BaseHandler): # type: ignore
    def __init__(self, app):
        super().__init__()
        self._app = app

    def _on_heartbeat(self, client, message):
        self._app.root.after(0, lambda: self._app.on_danmaku_heartbeat())
        pass

    def _on_super_chat(self, client, message: SuperChatMessage):
        user = UserInfo(
            uname=message.uname,
            uid=message.uid,
            vip_level=UserVipLevel(message.guard_level),
        )

        self._app.add_sc(
            user=user,
            price=message.price,
            message=message.message,
            timestamp=message.start_time,
        )

    def _on_danmaku(self, client, message: DanmakuMessage):
        # logger.info(f"收到弹幕: {message.uname}({message.uid}): {message.msg}")
        user = UserInfo(
            uname=message.uname,
            uid=message.uid,
            vip_level=UserVipLevel(message.privilege_type),
        )

        self._app.add_danmaku(
            user=user,
            message=message.msg,
            timestamp=int(time.time()),
        )


async def _run_fake_blivedm(app, config):
    logger.info("DEBUG=on，使用假的直播数据源")
    app.root.after(0, lambda: app.set_status("DEBUG 假数据源将在 1 秒后开始..."))

    try:
        await asyncio.sleep(1)
        index = 1
        while True:
            price = random.choice(DEBUG_FAKE_PRICES)
            uname = random.choice(DEBUG_FAKE_USERS)
            message = random.choice(DEBUG_FAKE_MESSAGES)
            is_special = random.random() < 0.5
            timestamp = int(time.time())

            app.root.after(0, lambda: app.on_danmaku_heartbeat())
            if is_special:
                app.add_danmaku(
                    uname=f"{uname}",
                    message=message,
                    timestamp=timestamp,
                )
            else:
                app.add_sc(
                    uname=f"{uname}",
                    price=price,
                    message=message,
                    timestamp=timestamp,
                )

            index += 1
            await asyncio.sleep(2)
    except asyncio.CancelledError:
        pass


async def run_blivedm(app, config):
    if _is_debug_fake_source_enabled():
        await _run_fake_blivedm(app, config)
        return

    if aiohttp is None or blivedm is None:
        logger.error("缺少 blivedm/aiohttp 依赖，无法连接真实直播数据源")
        app.root.after(0, lambda: app.set_status("❌ 缺少 blivedm/aiohttp 依赖"))
        return

    cookies = http.cookies.SimpleCookie()
    if config.sessdata:
        cookies["SESSDATA"] = config.sessdata
        cookies["SESSDATA"]["domain"] = "bilibili.com"

    async with aiohttp.ClientSession() as session:
        if config.sessdata:
            session.cookie_jar.update_cookies(cookies)

        client = blivedm.BLiveClient(config.room_id, session=session)
        client.set_handler(SCHandler(app))

        try:
            logger.info(f"正在连接直播间 {config.room_id} ...")
            app.root.after(0, lambda: app.set_status(f"🔗 连接中 {config.room_id}..."))
            client.start()
            await client.join()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"连接异常: {e}")
            app.root.after(0, lambda: app.set_status("❌ 连接失败，请检查网络或 Cookie"))
        finally:
            await client.stop_and_close()
            logger.info("直播客户端已关闭")
