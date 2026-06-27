from typing import *
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import time
import threading
import asyncio
import sys
import os
from PIL import Image, ImageTk
import logging
from importlib import metadata as importlib_metadata

from utils import extract_bv, BV_URL_TEMPLATE
from blive_handler import run_blivedm

if TYPE_CHECKING:
    from config import AppConfig

logger = logging.getLogger(__name__)

WINDOW_WIDTH_MIN = 1280
WINDOW_HEIGHT_MIN = 800
APP_DISTRIBUTION_NAME = "5050-sc-monitor"
APP_TITLE_NAME = "5050 SC 监听器"


def get_app_version():
    try:
        return importlib_metadata.version(APP_DISTRIBUTION_NAME)
    except importlib_metadata.PackageNotFoundError:
        if getattr(sys, "frozen", False):
            logger.warning("未找到包元数据，无法获取应用版本")
            return "未知版本"
        return "dev"


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
        self._status_var = tk.StringVar(value="等待连接...")

        self._set_icon()
        self._setup_window()
        self._build_ui()
        self._start_blivedm_thread()

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
            text="过滤 2 元店: 关",
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
                        foreground="#424242", rowheight=28, borderwidth=0)
        style.map("Treeview", background=[("selected", "#C8E6C9")],
                  foreground=[("selected", c.color_text)])
        style.configure("Treeview.Heading", background=c.color_bar, foreground=c.color_text,
                        relief="flat", borderwidth=0, font=("微软雅黑", 9, "bold"))
        self.tree.tag_configure("clicked_bv", background="#FFF9C4", foreground=c.color_text)

        for col, width, text in [
            ("time", 80, "时间"), ("user", 100, "用户"),
            ("price", 70, "金额(¥)"), ("msg", 400, "SC 内容"), ("bv", 160, "BV号 (点击跳转)")
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

        # 状态栏
        st = tk.Frame(self.root, bg=c.color_bg)
        st.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=4)
        tk.Label(st, textvariable=self._status_var, anchor=tk.W,
                 font=("微软雅黑", 9), fg=c.color_text, bg=c.color_bg).pack(side=tk.LEFT, fill=tk.X)

    # ----------------- 监听 -----------------
    def _on_close(self):
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
            text="过滤 2 元店: 开" if is_filtering_2_yuan else "过滤 2 元店: 关"
        )
        self._refresh_sc_list()

    def _clear_list(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._sc_records.clear()
        self._alloc_sc_idx = 1
        self._clicked_bv_items = []

    def _latest_clicked_bv_item(self):
        return self._clicked_bv_items[-1] if self._clicked_bv_items else None

    def _goto_last(self):
        latest_item = self._latest_clicked_bv_item()
        if latest_item and self.tree.exists(latest_item):
            self.tree.see(latest_item)
            self._select_latest_bv_item(latest_item)
            self.set_status("📍 已定位")
        else:
            self.set_status("⚠️ 暂无记录")

    def _change_cookie(self):
        w = tk.Toplevel(self.root)
        w.title("修改 Cookie")
        w.geometry("500x220")
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
        if self.tree.identify_column(ev.x) != "#5":
            return
        item = self.tree.identify_row(ev.y)
        if not item:
            return
        bv = self.tree.set(item, "bv")
        if bv and bv != "-":
            if item in self._clicked_bv_items:
                self._clicked_bv_items.remove(item)
            self._clicked_bv_items.append(item)
            self._apply_clicked_bv_highlights()
            self._select_latest_bv_item(item)
            webbrowser.open(BV_URL_TEMPLATE.format(bv))
            self.set_status(f"🔗 已跳转: {bv}")

    def _apply_clicked_bv_highlights(self):
        for item in self.tree.get_children():
            self.tree.item(item, tags=())
        for item in self._clicked_bv_items:
            if self.tree.exists(item):
                self.tree.item(item, tags=("clicked_bv",))

    def _select_latest_bv_item(self, item):
        self.tree.selection_set(item)
        self.tree.focus(item)

    def _on_right(self, ev):
        item = self.tree.identify_row(ev.y)
        if item:
            self.tree.selection_set(item)
            self._menu.post(ev.x_root, ev.y_root)

    def _copy_msg(self):
        sel = self.tree.selection()
        if sel:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.tree.set(sel[0], "msg"))
            self.set_status("📋 已复制")

    def _copy_bv(self):
        sel = self.tree.selection()
        if sel:
            bv = self.tree.set(sel[0], "bv")
            if bv and bv != "-":
                self.root.clipboard_clear()
                self.root.clipboard_append(bv)
                self.set_status("📋 已复制 BV")

    def add_sc(self, uname, price, message, timestamp):
        try:
            price_value = float(price)
        except (TypeError, ValueError):
            price_value = None
        bv = extract_bv(message) or "-"
        record_id = self._alloc_sc_idx
        self._alloc_sc_idx += 1
        self.root.after(0, self._append_sc_record, {
            "id": record_id,
            "uname": uname,
            "price": price,
            "price_value": price_value,
            "message": message,
            "timestamp": timestamp,
            "bv": bv,
        })

    def _append_sc_record(self, record):
        self._sc_records.append(record)
        self._refresh_sc_list()

    def get_visible_scs(self):
        is_filtering_2_yuan = self._filter_2_yuan_var.get()
        latest_item = self._latest_clicked_bv_item()
        visible_scs = []
        for record in self._sc_records:
            price_value = None
            try:
                price_value = float(record["price_value"])
            except Exception:
                price_value = None
            # always show the latest clicked BV item even if it is filtered out
            if latest_item != self._sc_item_id(record) \
                and is_filtering_2_yuan and price_value is not None and price_value < 30:
                continue
            visible_scs.append(record)
        return visible_scs

    def _sc_item_id(self, record):
        return f"sc_{record['id']}"

    def _refresh_sc_list(self):
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
                values=(t_str, record["uname"], f"¥{record['price']}", display_msg, record["bv"])
            )

        self._apply_clicked_bv_highlights()
        latest_item = self._latest_clicked_bv_item()
        if latest_item and self.tree.exists(latest_item):
            self._select_latest_bv_item(latest_item)

        total_count = len(self._sc_records)
        self.set_status(f"✅ 已连接 | 共 {total_count} 条 SC | 实际显示 {visible_count} 条")

    def on_danmaku_heartbeat(self):
        total_count = len(self._sc_records)
        visible_count = len(self.get_visible_scs())
        self.set_status(f"✅ 已连接 | 共 {total_count} 条 SC | 实际显示 {visible_count} 条")

    def _start_blivedm_thread(self):
        threading.Thread(target=lambda: asyncio.run(run_blivedm(self, self.config)),
                         daemon=True).start()

