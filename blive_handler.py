import asyncio
import http.cookies
import time
import aiohttp
import blivedm
import logging

logger = logging.getLogger(__name__)

class SCHandler(blivedm.BaseHandler):
    def __init__(self, app):
        super().__init__()
        self._app = app

    def _on_heartbeat(self, client, message):
        pass

    def _on_super_chat(self, client, message):
        self._app.add_sc(
            uname=message.uname,
            price=message.price,
            message=message.message,
            timestamp=message.start_time,
        )

async def run_blivedm(app, config):
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