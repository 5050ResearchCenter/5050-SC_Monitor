from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta
import logging
from pathlib import Path
import sys
import threading
from typing import Any

from aiohttp import web

from sc_store import SCStore


logger = logging.getLogger(__name__)
PAGE_SIZES = {20, 50, 100}
WEBUI_HOST = "127.0.0.1"
DEFAULT_WEBUI_PORT = 5050
STORE_KEY = web.AppKey("store", SCStore)
STATIC_PATH_KEY = web.AppKey("static_path", Path)


def get_webui_static_path() -> Path:
    if getattr(sys, "frozen", False):
        base_path = Path(getattr(sys, "_MEIPASS"))
        return base_path / "webui"
    return Path(__file__).resolve().parent / "webui" / ".output" / "public"


def _date_timestamp_range(value: str) -> tuple[int, int]:
    selected_date = date.fromisoformat(value)
    start = datetime.combine(selected_date, time.min).astimezone()
    end = datetime.combine(selected_date + timedelta(days=1), time.min).astimezone()
    return int(start.timestamp()), int(end.timestamp())


def _error(message: str, *, status: int = 400) -> web.Response:
    return web.json_response({"error": {"message": message}}, status=status)


async def _summary(request: web.Request) -> web.Response:
    selected_date = request.query.get("date", "")
    try:
        start_timestamp, end_timestamp = _date_timestamp_range(selected_date)
    except ValueError:
        return _error("date 必须是有效的 YYYY-MM-DD 日期")

    store = request.app[STORE_KEY]
    result = await asyncio.to_thread(
        store.get_daily_summary,
        start_timestamp,
        end_timestamp,
    )
    result["date"] = selected_date
    return web.json_response(result)


async def _users(request: web.Request) -> web.Response:
    query = request.query.get("q", "").strip()
    if not query:
        return web.json_response({"items": []})
    store = request.app[STORE_KEY]
    users = await asyncio.to_thread(store.search_users, query)
    return web.json_response({"items": users})


def _positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是整数") from exc
    if parsed < 1:
        raise ValueError(f"{name} 必须大于 0")
    return parsed


def _boolean_query(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true"}:
        return True
    if normalized in {"0", "false"}:
        return False
    raise ValueError(f"{name} 仅支持 0、1、false 或 true")


async def _super_chats(request: web.Request) -> web.Response:
    try:
        page = _positive_int(request.query.get("page", "1"), "page")
        page_size = _positive_int(request.query.get("pageSize", "20"), "pageSize")
        if page_size not in PAGE_SIZES:
            raise ValueError("pageSize 仅支持 20、50 或 100")
        user_uid_value = request.query.get("userUid")
        user_uid = int(user_uid_value) if user_uid_value not in (None, "") else None
        include_blacklisted = _boolean_query(
            request.query.get("includeBlacklisted", "false"),
            "includeBlacklisted",
        )
    except ValueError as exc:
        return _error(str(exc))

    store = request.app[STORE_KEY]
    result = await asyncio.to_thread(
        store.get_super_chats_page,
        page=page,
        page_size=page_size,
        user_uid=user_uid,
        include_blacklisted=include_blacklisted,
    )
    return web.json_response(result)


@web.middleware
async def _api_error_middleware(request: web.Request, handler):
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception:
        logger.exception("WebUI 请求处理失败: %s", request.path_qs)
        if request.path.startswith("/api/"):
            return _error("读取数据失败，请稍后重试", status=500)
        raise


async def _frontend(request: web.Request) -> web.StreamResponse:
    static_path = request.app[STATIC_PATH_KEY]
    relative_path = request.match_info.get("path", "") or "index.html"
    requested_path = (static_path / relative_path).resolve()
    try:
        requested_path.relative_to(static_path.resolve())
    except ValueError:
        raise web.HTTPNotFound()

    if requested_path.is_file():
        response = web.FileResponse(requested_path)
        if relative_path.startswith("_nuxt/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
    return web.FileResponse(static_path / "index.html", headers={"Cache-Control": "no-cache"})


def create_web_app(store: SCStore, static_path: Path | None = None) -> web.Application:
    resolved_static_path = Path(static_path or get_webui_static_path()).resolve()
    if not (resolved_static_path / "index.html").is_file():
        raise FileNotFoundError(
            f"未找到 WebUI 静态文件: {resolved_static_path}。请先运行 pnpm --dir webui generate。"
        )

    app = web.Application(middlewares=[_api_error_middleware])
    app[STORE_KEY] = store
    app[STATIC_PATH_KEY] = resolved_static_path
    app.router.add_get("/api/summary", _summary)
    app.router.add_get("/api/users", _users)
    app.router.add_get("/api/super-chats", _super_chats)
    app.router.add_get("/{path:.*}", _frontend)
    return app


class WebUIServer:
    """Own an aiohttp server running on a dedicated background event loop."""

    def __init__(
        self,
        store: SCStore,
        static_path: Path | None = None,
        *,
        port: int = DEFAULT_WEBUI_PORT,
    ):
        self.store = store
        self.static_path = static_path
        self.port = int(port)
        self.url: str | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._runner: web.AppRunner | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._start_error: BaseException | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and self.url)

    def start(self, timeout: float = 10) -> str:
        if self.running:
            assert self.url is not None
            return self.url
        self._ready.clear()
        self._start_error = None
        self._thread = threading.Thread(
            target=self._run,
            name="webui",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout):
            self.stop()
            raise TimeoutError("WebUI 服务启动超时")
        if self._start_error is not None:
            error = self._start_error
            self.stop()
            raise RuntimeError(f"WebUI 服务启动失败: {error}") from error
        assert self.url is not None
        return self.url

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._start())
        except BaseException as exc:
            self._start_error = exc
            self._ready.set()
            loop.close()
            return

        self._ready.set()
        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(self._cleanup())
            loop.close()

    async def _start(self) -> None:
        app = create_web_app(self.store, self.static_path)
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, WEBUI_HOST, self.port)
        await site.start()
        sockets = getattr(site._server, "sockets", None)
        if not sockets:
            raise RuntimeError("无法获取 WebUI 监听端口")
        port = int(sockets[0].getsockname()[1])
        self.url = f"http://{WEBUI_HOST}:{port}/"
        logger.info("WebUI 已启动: %s", self.url)

    async def _cleanup(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
        self.url = None
        logger.info("WebUI 已停止")

    def stop(self, timeout: float = 5) -> None:
        loop = self._loop
        thread = self._thread
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        self._thread = None
        self._loop = None
        self.url = None
