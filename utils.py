import re

BV_PATTERN = re.compile(r"BV[a-zA-Z0-9]{10}")
BV_URL_TEMPLATE = "https://www.bilibili.com/video/{}"

def extract_bv(text: str) -> str:
    """从文本中提取 BV 号，找不到返回 None"""
    m = BV_PATTERN.search(text)
    if m:
        return m.group(0)
    # 去除干扰字符
    idx = text.find("BV")
    if idx >= 0:
        clean = re.sub(r"[^a-zA-Z0-9]", "", text[idx:idx+30])
        m = BV_PATTERN.search(clean)
        if m:
            return m.group(0)
    return None