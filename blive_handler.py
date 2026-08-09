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
DEBUG_FALLBACK_MESSAGES = (
    "BV1hXuV62Eg4",
    "id：naogenggeng刚刚完美错过我了5555",
    "从盘丝洞开始看的，求个好友位：Scene",
    "张哥想要检核盖章，谢谢张哥，ID：桑果君",
    "张哥求个好友位，代码：272960172. id：你是一个个",
    "张哥根据之前b站活动显示今年九月我就晋升为十年老兵了。感谢十年前的自己点开了埃德蒙的视频。顺便求个好友ID：",
    "ID：依然鹏殇 关注好多年了，老张活久点",
    "张哥查查我的",
    "张哥，求你了[表情][表情][表情]，求个好友位。查查我的，id:宝生妖梦",
    "重新发一次，十年老粉求个好友，id：我一直都是羽那P",
    "张哥张哥我也是老粉，求个好友位ID：MendelTheF1sh",
    "张哥这次能加上嘛，之前大失败 id：Senrashi",
    "张哥十年老粉求个好友位，id：Xiaokeai，感谢！！",
    "张哥我来求好友位了，这个月才重新找到工作，也祝5050以后越来越好，id：樱羽",
    "（史）前老粉求个好友位，Thx，ID Az404🎵",
    "张哥 也给我盖个章，ID：God Hand Crash",
    "id：his Theme 代码195042680张哥张哥 求生老粉",
    "阿鹅，盖个章，id:overlordxu0",
    "看了张哥快八年了，求个好友位张哥，id：休比·多拉，975626500",
    "张哥，从你求生黑白一拖三开始关注你的多年老粉，蹭个好友位。ID张无忌。数字ID91430803",
    "脏哥给我盖个章",
    "张哥我也要盖章！",
    "张哥求个好友位，前面两次都错过了，ID：疾风浪过不折草",
    "查查我的，ID：mxddx41121",
    "霁蓝泉刀",
    "张哥求好友位名字冷 冽谷の安和 昴",
    "昨天没加上 今天有机会吗 id KellTA",
    "从初中看张哥白piao到现在快30了第一次给张哥上供，求个好友位ID：哎哟锅锅^^",
    "我也想要用个赞",
    "张哥十年老粉求个好友位，ID：心無",
    "来晚了希望还能加上，ID:celester",
    "张哥给个机会，错过好几次了，id:决心丶",
    "茫茫人海能看到我吗张哥 id：danyasviel",
    "张哥给个好友位，id：plastic",
    "张哥十年老粉求个好友位，id:我一直都是羽那P",
    "张哥，求个好友位 id：Violet",
    "张哥刚刚发错了 id是 榆酱",
    "张哥张哥 小登录坑位 id：花开富贵",
    "张哥，十年老粉不请自来，求个好友位ID：萨乌",
    "张哥求加，ID:果咩nie",
    "张哥加加我的 ID：ALEKO",
    "张哥查查我的，ID：凌小糕",
    "张哥，求个好友位，id：东篱长歌儿",
    "求个好友 325533107 Ingrid，老粉啦",
    "张哥十年老粉，求坑位",
    "张哥加加我的，ID：六一",
    "张哥我是刚才那个只有id辣个 我名字是DR12W",
    "张哥，十年老粉，求个坑位：DEVILdxy",
    "张哥 求加个好友 id:泽野冲",
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
    debug_messages = DEBUG_FALLBACK_MESSAGES
    logger.info("DEBUG=on，使用 %s 条 SC 测试样例", len(debug_messages))
    app.root.after(0, lambda: app.set_status("DEBUG 假数据源将在 1 秒后开始..."))

    try:
        await asyncio.sleep(1)
        index = 1
        while True:
            price = random.choice(DEBUG_FAKE_PRICES)
            uname = random.choice(DEBUG_FAKE_USERS)
            message = debug_messages[(index - 1) % len(debug_messages)]
            timestamp = int(time.time())
            user = UserInfo(
                uname=uname,
                uid=index,
                vip_level=UserVipLevel.Normal,
            )

            app.root.after(0, lambda: app.on_danmaku_heartbeat())
            app.add_sc(
                user=user,
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
