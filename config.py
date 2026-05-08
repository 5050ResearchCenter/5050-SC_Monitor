import json
import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

CONFIG_FILE = "sc_config.json"

@dataclass
class AppConfig:
    room_id: int = 5050
    sessdata: str = ""
    window_width: int = 900
    window_height: int = 500
    # 颜色
    color_bg: str = "#F0FFF4"
    color_card: str = "#FAFFFB"
    color_bar: str = "#E8F5E9"
    color_main: str = "#4CAF50"
    color_text: str = "#2E7D32"

    @classmethod
    def load(cls) -> "AppConfig":
        cfg = cls()
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cfg.sessdata = data.get("sessdata", "")
                logger.info("配置文件加载成功")
            except Exception as e:
                logger.error(f"配置文件解析失败: {e}")
        else:
            logger.warning("未找到配置文件，将使用空 SESSDATA")
        return cfg

    def save(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"sessdata": self.sessdata}, f, indent=2)
        logger.info("配置文件已保存")