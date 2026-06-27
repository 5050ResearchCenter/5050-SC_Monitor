import json
import os
import logging
from dataclasses import asdict, dataclass, field, fields

from gui import WINDOW_HEIGHT_MIN, WINDOW_WIDTH_MIN

logger = logging.getLogger(__name__)

CONFIG_FILE = "sc_config.json"

@dataclass
class AppConfig:
    room_id: int = 5050
    sessdata: str = ""

    # 配置
    filter_2_yuan: bool = False
    special_users: list[str] = field(default_factory=lambda: [
        "クリ", "男搓背", "阿木木"
    ])

    window_width: int = WINDOW_WIDTH_MIN
    window_height: int = WINDOW_HEIGHT_MIN
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
                valid_keys = {field.name for field in fields(cls)}
                merged_data = asdict(cfg)
                merged_data.update({key: value for key, value in data.items() if key in valid_keys})
                cfg = cls(**merged_data)
                logger.info("配置文件加载成功")
            except Exception as e:
                logger.error(f"配置文件解析失败: {e}")
        else:
            logger.warning("未找到配置文件，将使用空 SESSDATA")
        return cfg

    def save(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        logger.info("配置文件已保存")
