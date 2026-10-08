
from dataclasses import dataclass
from enum import IntEnum

class UserVipLevel(IntEnum):
    Normal = 0
    VIP1 = 3
    VIP2 = 2
    VIP3 = 1

    @classmethod
    def from_guard_level(cls, value) -> "UserVipLevel":
        """Convert Bilibili's current-room guard value without dropping messages."""
        try:
            return cls(int(value))
        except (TypeError, ValueError):
            return cls.Normal


@dataclass
class UserInfo:
    uname: str
    uid: int
    vip_level: UserVipLevel
