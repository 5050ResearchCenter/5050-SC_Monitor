from dataclasses import dataclass
from typing import *
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import time
import json
import threading
import asyncio
import sys
import os
import queue
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from PIL import Image, ImageTk
import logging

from utils import extract_bv, BV_URL_TEMPLATE
from blive_handler import run_blivedm
from dpsk_client import DPSKClient, DPSK_MAX_CONCURRENCY
from models import UserInfo, UserVipLevel

if TYPE_CHECKING:
    from config import AppConfig

logger = logging.getLogger(__name__)

WINDOW_WIDTH_MIN = 1280
WINDOW_HEIGHT_MIN = 800
APP_TITLE_NAME = "5050 SC 监听器"
VERSION_ENV_VAR = "SC_MONITOR_VERSION"


def get_app_version():
    return os.environ.get(VERSION_ENV_VAR, "dev")


class SCMonitorApp:
    def __init__(self, root, config):
        self.root = root
        self.config: AppConfig = config

        self._resize_after_id = None
        self.root.bind("<Configure>", self._on_window_configure)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._topmost = False
        self._filter_2_yuan_var = tk.BooleanVar(value=self.config.filter_2_yuan)
        self._sc_records = []
        self._alloc_sc_idx = 1
        self._clicked_bv_items = []
        self._selected_item = None
        self._status_var = tk.StringVar(value="等待连接...")
        self._sc_log_file = None
        self._sc_log_path = self._setup_sc_log()
        self._is_closing = False
        self._dpsk_result_queue = queue.SimpleQueue()
        self._dpsk_poll_after_id = None
        self._tip_window = None
        self._tip_after_id = None
        dpsk_api_token = self.config.dpsk_api_token.strip()
        self._dpsk_client = DPSKClient(dpsk_api_token) if dpsk_api_token else None
        self._dpsk_executor = (
            ThreadPoolExecutor(
                max_workers=DPSK_MAX_CONCURRENCY,
                thread_name_prefix="dpsk",
            )
            if self._dpsk_client
            else None
        )

        self._user_info: Dict[str, UserInfo] = {}

        self._set_icon()
        self._setup_window()
        self._build_ui()
        if self._dpsk_client:
            self._dpsk_poll_after_id = self.root.after(100, self._poll_dpsk_results)
        else:
            logger.warning("未配置 DPSK_API_TOKEN，将跳过 Steam ID 分析")
        self._start_blivedm_thread()

    def _setup_sc_log(self):
        try:
            log_dir = Path("data")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / f"sclog-{time.strftime('%y-%m-%d-%H-%M')}.jsonl"
            self._sc_log_file = log_path.open("a", encoding="utf-8")
            logger.info(f"SC 日志文件: {log_path}")
            return log_path
        except Exception as e:
            logger.warning(f"创建 SC 日志文件失败: {e}")
            return None

    def _set_icon(self):
        try:
            base = getattr(sys, "_MEIPASS", "") if getattr(sys, "frozen", False) else os.path.dirname(__file__)
            icon_path = os.path.join(base, "resources", "favicon.ico")
            if os.path.exists(icon_path):
                img = Image.open(icon_path).resize((32, 32), Image.LANCZOS)
                self.root.iconphoto(True, ImageTk.PhotoImage(img))
        except Exception as e:
            logger.warning(f"设置图标失败: {e}")

    def _setup_window(self):
        self.root.title(f"{APP_TITLE_NAME} [{get_app_version()}]")

        self.config.window_width = max(self.config.window_width, WINDOW_WIDTH_MIN)
        self.config.window_height = max(self.config.window_height, WINDOW_HEIGHT_MIN)
        self.root.geometry(f"{self.config.window_width}x{self.config.window_height}")
        self.root.minsize(WINDOW_WIDTH_MIN, WINDOW_HEIGHT_MIN)

        self.root.configure(bg=self.config.color_bg)
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - self.config.window_width) // 2
        y = (self.root.winfo_screenheight() - self.config.window_height) // 2
        self.root.geometry(f"+{x}+{y}")

    def _build_ui(self):
        c = self.config  # 颜色缩写
        bar = tk.Frame(self.root, bg=c.color_bg)
        bar.pack(side=tk.TOP, fill=tk.X, padx=8, pady=6)

        tk.Label(bar, text=f"🎙️ 直播间 {c.room_id}", font=("微软雅黑", 10, "bold"),
                 fg=c.color_text, bg=c.color_bg).pack(side=tk.LEFT, padx=4)

        btn_style = {
            "bg": c.color_bar, "fg": c.color_text, "relief": tk.FLAT, "bd": 0,
            "padx": 10, "pady": 4, "font": ("微软雅黑", 9),
            "activebackground": "#C8E6C9", "activeforeground": c.color_text,
            "cursor": "hand2"
        }
        # 顶部按钮
        self._btn_top = tk.Button(bar, text="📌 置顶", command=self._toggle_top, **btn_style)
        self._btn_top.pack(side=tk.LEFT, padx=3)

        self._btn_filter_2_yuan = tk.Checkbutton(
            bar,
            text=self.get_filter_2_yuan_text(),
            variable=self._filter_2_yuan_var,
            command=self._filter_2_yuan,
            indicatoron=False,
            selectcolor=c.color_main,
            **btn_style,
        )
        self._btn_filter_2_yuan.pack(side=tk.LEFT, padx=3)

        tk.Button(bar, text="🧹 清空", command=self._clear_list, **btn_style).pack(side=tk.LEFT, padx=3)
        tk.Button(bar, text="📍 回到跳转", command=self._goto_last,
                  bg=c.color_main, fg="white", relief=tk.FLAT, bd=0, padx=10, pady=4,
                  font=("微软雅黑", 9, "bold"), activebackground="#388E3C", cursor="hand2"
                  ).pack(side=tk.LEFT, padx=3)
        tk.Button(bar, text="🔑 Cookie", command=self._change_cookie, **btn_style).pack(side=tk.LEFT, padx=3)

        # Treeview 列表
        f = tk.Frame(self.root, bg=c.color_bg)
        f.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        cols = ("time", "user", "price", "msg", "bv")
        self.tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=c.color_card, fieldbackground=c.color_card,
                        foreground="#424242", rowheight=28, borderwidth=0, font=("微软雅黑", 9))
        style.map("Treeview", background=[("selected", "#C8E6C9")],
                  foreground=[("selected", c.color_text)])
        style.configure("Treeview.Heading", background=c.color_bar, foreground=c.color_text,
                        relief="flat", borderwidth=0, font=("微软雅黑", 9, "bold"))
        self.tree.tag_configure("clicked_bv", background="#FFF9C4", foreground=c.color_text)
        self.tree.tag_configure("special_danmaku", background="#FFF1F6", foreground=c.color_text)

        self.tree.tag_configure("vip1", foreground=self.config.color_user_vip1)
        self.tree.tag_configure("vip2", foreground=self.config.color_user_vip2)
        self.tree.tag_configure("vip3", foreground=self.config.color_user_vip3)

        for col, width, text in [
            ("time", 20, "时间"), ("user", 100, "用户"),
            ("price", 70, "金额(¥)"), ("msg", 400, "SC 内容"),
            ("bv", 230, "BV号 / Steam ID (点击跳转/复制)")
        ]:
            anchor = tk.CENTER if col in ("price", "bv") else tk.W
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=anchor, minwidth=60)

        sb = tk.Scrollbar(f, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<ButtonRelease-1>", self._on_click)
        self.tree.bind("<Button-3>", self._on_right)

        self._menu = tk.Menu(self.root, tearoff=0, bg=c.color_card, fg=c.color_text)
        self._menu.add_command(label="📋 复制 SC 内容", command=self._copy_msg)
        self._menu.add_command(label="🔗 复制 BV 号", command=self._copy_bv)
        self._menu.add_command(label="🎮 复制 Steam ID", command=self._copy_steam_id)

        # 状态栏
        st = tk.Frame(self.root, bg=c.color_bg)
        st.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=4)
        tk.Label(st, textvariable=self._status_var, anchor=tk.W,
                 font=("微软雅黑", 9), fg=c.color_text, bg=c.color_bg).pack(side=tk.LEFT, fill=tk.X)
    # ----------------- 工具 -----------------
    def get_filter_2_yuan_text(self):
        return "过滤两元店: 开" if self._filter_2_yuan_var.get() else "过滤两元店: 关"

    # ----------------- 监听 -----------------
    def _on_close(self):
        self._is_closing = True
        self._hide_tip()
        if self._dpsk_poll_after_id is not None:
            try:
                self.root.after_cancel(self._dpsk_poll_after_id)
            except Exception:
                pass
            self._dpsk_poll_after_id = None
        if self._dpsk_executor is not None:
            self._dpsk_executor.shutdown(wait=False, cancel_futures=True)
        if self._sc_log_file is not None:
            try:
                self._sc_log_file.close()
            except Exception:
                pass
            self._sc_log_file = None
        self.config.save()
        self.root.destroy()

    def _on_window_configure(self, event):
        if event.widget is not self.root:
            return

        if self._resize_after_id is not None:
            self.root.after_cancel(self._resize_after_id)

        self._resize_after_id = self.root.after(300, self._save_window_size)

    def _save_window_size(self):
        self._resize_after_id = None
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()
        logger.info(f"窗口大小变化: {window_width}x{window_height}")
        self.config.window_width = window_width
        self.config.window_height = window_height

    # ----------------- 交互 -----------------
    def set_status(self, text):
        self._status_var.set(text)

    def _toggle_top(self):
        self._topmost = not self._topmost
        self.root.attributes("-topmost", self._topmost)
        self._btn_top.config(text="📌 已置顶" if self._topmost else "📌 置顶")

    def _filter_2_yuan(self):
        is_filtering_2_yuan = self._filter_2_yuan_var.get()
        self.config.filter_2_yuan = is_filtering_2_yuan
        self.config.save()
        self._btn_filter_2_yuan.config(
            text=self.get_filter_2_yuan_text()
        )
        self._refresh_sc_list()

    def _clear_list(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._sc_records.clear()
        self._alloc_sc_idx = 1
        self._clicked_bv_items = []
        self._selected_item = None

    def _latest_clicked_bv_item(self):
        return self._clicked_bv_items[-1] if self._clicked_bv_items else None

    def _goto_last(self):
        latest_item = self._latest_clicked_bv_item()
        if latest_item and self.tree.exists(latest_item):
            self.tree.see(latest_item)
            self._select_item(latest_item)
            self.set_status("📍 已定位")
        else:
            self.set_status("⚠️ 暂无记录")

    def _change_cookie(self):
        w = tk.Toplevel(self.root)
        w.title("修改 Cookie")
        w.geometry("500x220")
        x = (self.root.winfo_screenwidth() - 500) // 2
        y = (self.root.winfo_screenheight() - 220) // 2
        w.geometry(f"+{x}+{y}")
        w.configure(bg=self.config.color_bg)
        w.transient(self.root)
        w.grab_set()

        tk.Label(w, text="粘贴新的 SESSDATA：", font=("微软雅黑", 10),
                 fg=self.config.color_text, bg=self.config.color_bg).pack(pady=(15, 5))

        e = tk.Entry(w, width=55, font=("Consolas", 10), show="*",
                     highlightbackground="#A5D6A7", highlightcolor=self.config.color_main,
                     highlightthickness=2, relief="flat", bd=1)
        e.pack(pady=5, padx=20, ipady=6)
        e.insert(0, self.config.sessdata)
        e.focus()

        def save():
            self.config.sessdata = e.get().strip()
            self.config.save()
            messagebox.showinfo("提示", "已保存，重启生效")
            w.destroy()

        tk.Button(w, text="保存", command=save, bg=self.config.color_main, fg="white",
                  width=10, font=("微软雅黑", 10), relief=tk.FLAT, bd=0, cursor="hand2").pack(pady=12)

    def _on_click(self, ev):
        if self.tree.identify_region(ev.x, ev.y) != "cell":
            return
        item = self.tree.identify_row(ev.y)
        if not item:
            return

        self._select_item(item)
        if self.tree.identify_column(ev.x) != "#5":
            return

        record = self._record_for_item(item)
        steam_id = record.get("steam_id") if record else None
        if steam_id:
            self._mark_row(item)
            self._copy_to_clipboard(steam_id)
            self.set_status(f"📋 已复制 Steam ID: {steam_id}")
            return

        bv = record.get("bv", "-") if record else self.tree.set(item, "bv")
        user = self.tree.set(item, "user")
        if bv and ("bv" in bv.lower()):
            self._mark_row(item)
            webbrowser.open(BV_URL_TEMPLATE.format(bv))
            self._show_tip("已跳转")
            self.set_status(f"🔗 已跳转: {bv}")
        else:
            if item in self._clicked_bv_items:
                self._unmark_row(item)
                self._show_tip("已取消标记")
                self.set_status(f"🔗 已取消: {user}")
            else:
                self._mark_row(item)
                self._show_tip("已标记")
                self.set_status(f"🔗 已标记: {user}")

    def _mark_row(self, item):
        if item in self._clicked_bv_items:
            self._clicked_bv_items.remove(item)
        self._clicked_bv_items.append(item)
        self._apply_highlights()
        record = self._record_for_item(item)
        bv = record.get("bv", "-") if record else self.tree.set(item, "bv")
        return bv if bv and bv != "-" else None

    def _unmark_row(self, item):
        if item in self._clicked_bv_items:
            self._clicked_bv_items.remove(item)
            self._apply_highlights()

    def _apply_highlights(self):
        for item in self.tree.get_children():
            userinfo = self._user_info.get(self.tree.set(item, "user"))
            # logger.info("debugging: userinfo: %s", userinfo.uname if userinfo else "None")
            if float(self.tree.set(item, "price")[1::]) < 0.1:
                if userinfo:
                    processed = False
                    if userinfo.vip_level == UserVipLevel.VIP3 and self.config.show_user_vip3:
                        logger.info("debugging: 高亮总督用户弹幕: %s", userinfo.uname)
                        self.tree.item(item, tags=("vip3",))
                        processed = True
                    elif userinfo.vip_level == UserVipLevel.VIP2 and self.config.show_user_vip2:
                        logger.info("debugging: 高亮提督用户弹幕: %s", userinfo.uname)
                        self.tree.item(item, tags=("vip2",))
                        processed = True
                    elif userinfo.vip_level == UserVipLevel.VIP1 and self.config.show_user_vip1:
                        logger.info("debugging: 高亮舰长用户弹幕: %s", userinfo.uname)
                        self.tree.item(item, tags=("vip1",))
                        processed = True

                    if not processed:
                        self.tree.item(item, tags=("special_danmaku",))
            else:
                self.tree.item(item, tags=())

        for item in self._clicked_bv_items:
            if self.tree.exists(item):
                self.tree.item(item, tags=("clicked_bv",))

    def _current_selected_item(self):
        selection = self.tree.selection()
        if selection:
            self._selected_item = selection[0]
        return self._selected_item

    def _select_item(self, item):
        self.tree.selection_set(item)
        self.tree.focus(item)
        self._selected_item = item

    def _restore_selected_item(self, item):
        if item and self.tree.exists(item):
            self._select_item(item)

    def _on_right(self, ev):
        item = self.tree.identify_row(ev.y)
        if item:
            self._select_item(item)
            self._menu.post(ev.x_root, ev.y_root)

    def _copy_msg(self):
        sel = self.tree.selection()
        if sel:
            self._copy_to_clipboard(self.tree.set(sel[0], "msg"))
            self.set_status("📋 已复制")

    def _copy_to_clipboard(self, value):
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self._show_tip("已复制")

    def _show_tip(self, text, duration=1200):
        self._hide_tip()

        tip = tk.Toplevel(self.root)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.configure(bg=self.config.color_main)
        tk.Label(
            tip,
            text=text,
            bg=self.config.color_main,
            fg="white",
            font=("微软雅黑", 9, "bold"),
            padx=10,
            pady=5,
        ).pack()
        tip.update_idletasks()

        pointer_x = self.root.winfo_pointerx()
        pointer_y = self.root.winfo_pointery()
        tip_width = tip.winfo_reqwidth()
        tip_height = tip.winfo_reqheight()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = min(pointer_x + 14, screen_width - tip_width - 8)
        y = min(pointer_y + 18, screen_height - tip_height - 8)
        tip.geometry(f"+{max(8, x)}+{max(8, y)}")

        self._tip_window = tip
        self._tip_after_id = self.root.after(duration, self._hide_tip)

    def _hide_tip(self):
        if self._tip_after_id is not None:
            try:
                self.root.after_cancel(self._tip_after_id)
            except Exception:
                pass
            self._tip_after_id = None
        if self._tip_window is not None:
            try:
                self._tip_window.destroy()
            except Exception:
                pass
            self._tip_window = None

    def _copy_bv(self):
        sel = self.tree.selection()
        if sel:
            record = self._record_for_item(sel[0])
            bv = record.get("bv", "-") if record else self.tree.set(sel[0], "bv")
            if bv and bv != "-":
                self._copy_to_clipboard(bv)
                self.set_status("📋 已复制 BV")

    def _copy_steam_id(self):
        sel = self.tree.selection()
        if not sel:
            return
        record = self._record_for_item(sel[0])
        steam_id = record.get("steam_id") if record else None
        if steam_id:
            self._copy_to_clipboard(steam_id)
            self.set_status(f"📋 已复制 Steam ID: {steam_id}")
        else:
            self.set_status("⚠️ 该条记录没有 Steam ID")

    def add_sc(self, user: UserInfo, price, message, timestamp):
        uname = user.uname
        uid = user.uid
        vip_level = user.vip_level
        self._user_info[uname] = user

        try:
            price_value = float(price)
        except (TypeError, ValueError):
            price_value = None
        bv = extract_bv(message) or "-"
        steam_analysis_status = "disabled"
        if bv != "-":
            steam_analysis_status = "skipped_bv"
        elif self._dpsk_client:
            steam_analysis_status = "pending"
        record_id = self._alloc_sc_idx
        self._alloc_sc_idx += 1
        self.root.after(0, self._append_sc_record, {
            "id": record_id,
            "uname": uname,
            "vip_level": vip_level,
            "price": price,
            "price_value": price_value,
            "message": message,
            "timestamp": timestamp,
            "bv": bv,
            "steam_id": None,
            "steam_analysis_status": steam_analysis_status,
        })

    def add_danmaku(self, user: UserInfo, message, timestamp):
        uname = user.uname
        uid = user.uid
        vip_level = user.vip_level

        # if uid == 774288:
        #     vip_level = UserVipLevel.VIP1
        #     user.vip_level = vip_level
        #     logger.info("debugging: 用户弹幕: %s", user)

        process_flag = False
        # 昵称触发关键词
        if any(special_user in uname for special_user in self.config.special_users):
            process_flag = True

        # 用户 UID 在列表
        if any(str(uid) == str(special_uid) for special_uid in self.config.special_users_uid):
            process_flag = True

        # 是 VIP 用户
        if int(vip_level) == UserVipLevel.VIP1 and self.config.show_user_vip1:
            process_flag = True
        elif int(vip_level) == UserVipLevel.VIP2 and self.config.show_user_vip2:
            process_flag = True
        elif int(vip_level) == UserVipLevel.VIP3 and self.config.show_user_vip3:
            process_flag = True

        if not process_flag:
            return

        self._user_info[uname] = user
        record_id = self._alloc_sc_idx
        self._alloc_sc_idx += 1
        self.root.after(0, self._append_sc_record, {
            "id": record_id,
            "uname": uname,
            "vip_level": vip_level,
            "price": 0,
            "price_value": 0,
            "message": message,
            "timestamp": timestamp,
            "bv": "弹幕",
        })
        return

    def _append_sc_record(self, record):
        self._sc_records.append(record)
        self._write_sc_log(record)
        self._refresh_sc_list()
        if record.get("steam_analysis_status") == "pending":
            self._start_steam_id_analysis(record)

    def _start_steam_id_analysis(self, record):
        if self._is_closing or self._dpsk_client is None or self._dpsk_executor is None:
            return
        future = self._dpsk_executor.submit(
            self._dpsk_client.extract_steam_id,
            record["message"],
        )
        future.add_done_callback(
            lambda completed, record_id=record["id"]: self._queue_dpsk_result(record_id, completed)
        )

    def _queue_dpsk_result(self, record_id: int, future: Future):
        try:
            steam_id = future.result()
            error = None
        except Exception as exc:
            steam_id = None
            error = str(exc)
        self._dpsk_result_queue.put((record_id, steam_id, error))

    def _poll_dpsk_results(self):
        self._dpsk_poll_after_id = None
        if self._is_closing:
            return

        updated = False
        latest_error = None
        while True:
            try:
                record_id, steam_id, error = self._dpsk_result_queue.get_nowait()
            except queue.Empty:
                break

            record = next((item for item in self._sc_records if item["id"] == record_id), None)
            if record is None:
                continue
            record["steam_id"] = steam_id
            record["steam_analysis_status"] = "error" if error else "done"
            updated = True
            if error:
                latest_error = error
                logger.warning("SC %s 的 Steam ID 分析失败: %s", record_id, error)

        if updated:
            self._refresh_sc_list()
        if latest_error:
            self.set_status(f"⚠️ Steam ID 分析失败: {latest_error}")
        self._dpsk_poll_after_id = self.root.after(100, self._poll_dpsk_results)

    def _write_sc_log(self, record):
        if self._sc_log_file is None:
            return
        try:
            self._sc_log_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._sc_log_file.flush()
        except Exception as e:
            logger.warning(f"写入 SC 日志失败: {e}")

    def get_visible_scs(self):
        is_filtering_2_yuan = self._filter_2_yuan_var.get()
        latest_item = self._selected_item
        visible_scs = []
        for record in self._sc_records:
            price_value = None
            try:
                price_value = float(record["price_value"])
            except Exception:
                price_value = None
            # always show the latest clicked BV item even if it is filtered out
            if latest_item != self._sc_item_id(record) \
                and is_filtering_2_yuan \
                and price_value is not None \
                and 0 < price_value and price_value < 29.9:
                continue
            visible_scs.append(record)
        return visible_scs

    def _sc_item_id(self, record):
        return f"sc_{record['id']}"

    def _record_for_item(self, item):
        return next(
            (record for record in self._sc_records if self._sc_item_id(record) == item),
            None,
        )

    @staticmethod
    def _bv_column_value(record):
        bv = record.get("bv") or "-"
        steam_id = record.get("steam_id")
        status = record.get("steam_analysis_status")
        if steam_id:
            return f"{bv} | {steam_id}" if bv != "-" else steam_id
        if status == "pending":
            return f"{bv} | 分析中…" if bv != "-" else "分析中…"
        if status == "error":
            return f"{bv} | 分析失败" if bv != "-" else "分析失败"
        return bv

    def _refresh_sc_list(self):
        selected_item = self._current_selected_item()
        visible_scs = self.get_visible_scs()
        visible_count = len(visible_scs)

        for i in self.tree.get_children():
            self.tree.delete(i)

        for record in reversed(visible_scs):
            t_str = time.strftime("%H:%M:%S", time.localtime(record["timestamp"]))
            msg = record["message"]
            display_msg = (msg[:80] + "...") if len(msg) > 80 else msg
            self.tree.insert(
                "",
                tk.END,
                iid=self._sc_item_id(record),
                values=(
                    t_str,
                    record["uname"],
                    f"¥{record['price']}",
                    display_msg,
                    self._bv_column_value(record),
                )
            )

        self._apply_highlights()
        self._restore_selected_item(selected_item)

        total_count = len(self._sc_records)
        self.set_status(f"✅ 已连接 | 共 {total_count} 条 SC | 实际显示 {visible_count} 条")

    def on_danmaku_heartbeat(self):
        total_count = len(self._sc_records)
        visible_count = len(self.get_visible_scs())
        self.set_status(f"✅ 已连接 | 共 {total_count} 条 SC | 实际显示 {visible_count} 条")

    def _start_blivedm_thread(self):
        threading.Thread(target=lambda: asyncio.run(run_blivedm(self, self.config)),
                         daemon=True).start()
