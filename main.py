import tkinter as tk
import logging
from config import AppConfig
from gui import SCMonitorApp


def main():
    # 日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("sc_monitor.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info("程序启动")

    config = AppConfig.load()
    root = tk.Tk()
    app = SCMonitorApp(root, config)
    root.mainloop()


if __name__ == "__main__":
    main()
