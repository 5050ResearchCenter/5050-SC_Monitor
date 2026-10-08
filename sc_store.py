from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Sequence


DEFAULT_DATABASE_PATH = Path("data") / "sc_monitor.sqlite3"


@dataclass(frozen=True)
class UserSCStats:
    count: int
    total_amount: float


@dataclass(frozen=True)
class StoredSC:
    id: int
    stats: UserSCStats


class SCStore:
    """SQLite-backed SC history and aggregate statistics."""

    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS super_chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_uid INTEGER NOT NULL,
                    nickname TEXT NOT NULL,
                    content TEXT NOT NULL,
                    amount REAL NOT NULL,
                    sent_at INTEGER NOT NULL,
                    bv TEXT,
                    video_title TEXT,
                    video_tags TEXT NOT NULL DEFAULT '[]',
                    blacklisted INTEGER NOT NULL DEFAULT 0,
                    blacklist_matches TEXT NOT NULL DEFAULT '[]'
                );

                CREATE INDEX IF NOT EXISTS idx_super_chats_user_uid
                ON super_chats(user_uid);

                CREATE INDEX IF NOT EXISTS idx_super_chats_bv
                ON super_chats(bv);

                CREATE INDEX IF NOT EXISTS idx_super_chats_sent_at
                ON super_chats(sent_at DESC, id DESC);
                """
            )

    def record_sc(
        self,
        *,
        user_uid: int,
        nickname: str,
        content: str,
        amount: float,
        sent_at: int,
        bv: str | None,
    ) -> StoredSC:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO super_chats (
                    user_uid, nickname, content, amount, sent_at, bv
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    int(user_uid),
                    str(nickname),
                    str(content),
                    float(amount),
                    int(sent_at),
                    bv,
                ),
            )
            row = connection.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(amount), 0)
                FROM super_chats
                WHERE user_uid = ?
                """,
                (int(user_uid),),
            ).fetchone()
            assert row is not None
            return StoredSC(
                id=int(cursor.lastrowid),
                stats=UserSCStats(count=int(row[0]), total_amount=float(row[1])),
            )

    def get_user_stats(self, user_uid: int) -> UserSCStats:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(amount), 0)
                FROM super_chats
                WHERE user_uid = ?
                """,
                (int(user_uid),),
            ).fetchone()
        assert row is not None
        return UserSCStats(count=int(row[0]), total_amount=float(row[1]))

    def reassign_user_uid_for_nickname(self, nickname: str, user_uid: int) -> int:
        """Repair historical rows created by a source that used unstable user IDs."""
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE super_chats
                SET user_uid = ?
                WHERE nickname = ? AND user_uid != ?
                """,
                (int(user_uid), str(nickname), int(user_uid)),
            )
            return int(cursor.rowcount)

    def update_video_metadata(
        self,
        record_id: int,
        *,
        title: str,
        tags: Sequence[str],
        blacklisted: bool,
        blacklist_matches: Sequence[str],
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE super_chats
                SET video_title = ?,
                    video_tags = ?,
                    blacklisted = ?,
                    blacklist_matches = ?
                WHERE id = ?
                """,
                (
                    str(title),
                    json.dumps(list(tags), ensure_ascii=False),
                    int(bool(blacklisted)),
                    json.dumps(list(blacklist_matches), ensure_ascii=False),
                    int(record_id),
                ),
            )

    def get_daily_summary(
        self,
        start_timestamp: int,
        end_timestamp: int,
        *,
        ranking_limit: int = 10,
    ) -> dict[str, Any]:
        """Return all dashboard metrics for one half-open timestamp range."""
        range_parameters = (int(start_timestamp), int(end_timestamp))
        with self._connection() as connection:
            totals = connection.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(amount), 0)
                FROM super_chats
                WHERE sent_at >= ? AND sent_at < ?
                """,
                range_parameters,
            ).fetchone()
            assert totals is not None
            total_count = int(totals[0])

            distribution_rows = connection.execute(
                """
                SELECT amount, COUNT(*), SUM(amount)
                FROM super_chats
                WHERE sent_at >= ? AND sent_at < ?
                GROUP BY amount
                ORDER BY amount ASC
                """,
                range_parameters,
            ).fetchall()

            ranking_query = """
                SELECT
                    daily.user_uid,
                    (
                        SELECT latest.nickname
                        FROM super_chats AS latest
                        WHERE latest.user_uid = daily.user_uid
                        ORDER BY latest.sent_at DESC, latest.id DESC
                        LIMIT 1
                    ) AS nickname,
                    COUNT(*) AS sc_count,
                    SUM(daily.amount) AS total_amount
                FROM super_chats AS daily
                WHERE daily.sent_at >= ? AND daily.sent_at < ?
                GROUP BY daily.user_uid
            """
            count_ranking_rows = connection.execute(
                ranking_query
                + " ORDER BY sc_count DESC, total_amount DESC, daily.user_uid ASC LIMIT ?",
                (*range_parameters, int(ranking_limit)),
            ).fetchall()
            amount_ranking_rows = connection.execute(
                ranking_query
                + " ORDER BY total_amount DESC, sc_count DESC, daily.user_uid ASC LIMIT ?",
                (*range_parameters, int(ranking_limit)),
            ).fetchall()

        def ranking(rows):
            return [
                {
                    "userUid": int(row[0]),
                    "nickname": str(row[1]),
                    "count": int(row[2]),
                    "totalAmount": float(row[3]),
                }
                for row in rows
            ]

        return {
            "totalCount": total_count,
            "totalAmount": float(totals[1]),
            "amountDistribution": [
                {
                    "amount": float(row[0]),
                    "count": int(row[1]),
                    "totalAmount": float(row[2]),
                    "percentage": (int(row[1]) / total_count * 100) if total_count else 0,
                }
                for row in distribution_rows
            ],
            "countRanking": ranking(count_ranking_rows),
            "amountRanking": ranking(amount_ranking_rows),
        }

    def search_users(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Find users by exact UID or nickname and return their all-time stats."""
        query = str(query).strip()
        if not query:
            return []

        with self._connection() as connection:
            try:
                exact_uid = int(query)
            except ValueError:
                exact_uid = None

            if exact_uid is not None:
                uid_rows = connection.execute(
                    """
                    SELECT user_uid, MAX(sent_at) AS last_seen
                    FROM super_chats
                    WHERE user_uid = ?
                    GROUP BY user_uid
                    LIMIT ?
                    """,
                    (exact_uid, int(limit)),
                ).fetchall()
            else:
                escaped_query = (
                    query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                )
                uid_rows = connection.execute(
                    """
                    SELECT
                        user_uid,
                        MAX(sent_at) AS last_seen,
                        MAX(CASE WHEN nickname = ? COLLATE NOCASE THEN 1 ELSE 0 END) AS exact_match
                    FROM super_chats
                    WHERE nickname LIKE ? ESCAPE '\\' COLLATE NOCASE
                    GROUP BY user_uid
                    ORDER BY exact_match DESC, last_seen DESC, user_uid ASC
                    LIMIT ?
                    """,
                    (query, f"%{escaped_query}%", int(limit)),
                ).fetchall()

            users = []
            for uid_row in uid_rows:
                user_uid = int(uid_row[0])
                stats = connection.execute(
                    """
                    SELECT
                        COUNT(*),
                        COALESCE(SUM(amount), 0),
                        COALESCE(SUM(CASE WHEN blacklisted != 0 THEN 1 ELSE 0 END), 0)
                    FROM super_chats
                    WHERE user_uid = ?
                    """,
                    (user_uid,),
                ).fetchone()
                aliases = connection.execute(
                    """
                    SELECT nickname, MAX(sent_at) AS last_seen, MAX(id) AS last_id
                    FROM super_chats
                    WHERE user_uid = ?
                    GROUP BY nickname
                    ORDER BY last_seen DESC, last_id DESC
                    """,
                    (user_uid,),
                ).fetchall()
                distribution_rows = connection.execute(
                    """
                    SELECT amount, COUNT(*), SUM(amount)
                    FROM super_chats
                    WHERE user_uid = ?
                    GROUP BY amount
                    ORDER BY amount ASC
                    """,
                    (user_uid,),
                ).fetchall()
                assert stats is not None and aliases
                total_count = int(stats[0])
                users.append(
                    {
                        "userUid": user_uid,
                        "nickname": str(aliases[0][0]),
                        "aliases": [str(row[0]) for row in aliases],
                        "count": total_count,
                        "totalAmount": float(stats[1]),
                        "blacklistedCount": int(stats[2]),
                        "amountDistribution": [
                            {
                                "amount": float(row[0]),
                                "count": int(row[1]),
                                "totalAmount": float(row[2]),
                                "percentage": int(row[1]) / total_count * 100,
                            }
                            for row in distribution_rows
                        ],
                    }
                )
        return users

    def get_super_chats_page(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        user_uid: int | None = None,
        include_blacklisted: bool = False,
    ) -> dict[str, Any]:
        """Return a newest-first page of complete stored SC rows."""
        conditions = []
        parameters = []
        if user_uid is not None:
            conditions.append("user_uid = ?")
            parameters.append(int(user_uid))
        if not include_blacklisted:
            conditions.append("blacklisted = 0")
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        offset = (int(page) - 1) * int(page_size)
        with self._connection() as connection:
            total_row = connection.execute(
                "SELECT COUNT(*) FROM super_chats" + where_clause,
                tuple(parameters),
            ).fetchone()
            assert total_row is not None
            rows = connection.execute(
                """
                SELECT id, user_uid, nickname, content, amount, sent_at, bv,
                       video_title, video_tags, blacklisted, blacklist_matches
                FROM super_chats
                """
                + where_clause
                + " ORDER BY sent_at DESC, id DESC LIMIT ? OFFSET ?",
                (*parameters, int(page_size), offset),
            ).fetchall()

        def decode_json_list(value: str) -> list[str]:
            try:
                decoded = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                return []
            return [str(item) for item in decoded] if isinstance(decoded, list) else []

        return {
            "items": [
                {
                    "id": int(row[0]),
                    "userUid": int(row[1]),
                    "nickname": str(row[2]),
                    "content": str(row[3]),
                    "amount": float(row[4]),
                    "sentAt": int(row[5]),
                    "bv": row[6],
                    "videoTitle": row[7],
                    "videoTags": decode_json_list(row[8]),
                    "blacklisted": bool(row[9]),
                    "blacklistMatches": decode_json_list(row[10]),
                }
                for row in rows
            ],
            "total": int(total_row[0]),
            "page": int(page),
            "pageSize": int(page_size),
            "pageCount": max(1, (int(total_row[0]) + int(page_size) - 1) // int(page_size)),
        }
