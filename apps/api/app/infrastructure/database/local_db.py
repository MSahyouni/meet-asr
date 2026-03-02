import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import settings


DB_PATH = settings.DATA_DIR / "meetasr.sqlite3"


def _conn() -> sqlite3.Connection:
    connection = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def init_db() -> None:
    with _conn() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT NOT NULL,
                email TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                bio TEXT,
                avatar_url TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                token_version INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        cols = {row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()}
        if "token_version" not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS activities (
                activity_id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                description TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata_json TEXT,
                FOREIGN KEY(user_email) REFERENCES users(email)
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activities_email ON activities(user_email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activities_timestamp ON activities(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activities_user_time ON activities(user_email, timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activities_user_type ON activities(user_email, activity_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activities_type_time ON activities(activity_type, timestamp)")
        connection.commit()


def create_user(email: str, user_payload: Dict[str, Any]) -> None:
    with _conn() as connection:
        connection.execute(
            """
            INSERT INTO users (id, email, full_name, password_hash, bio, avatar_url, is_active, token_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_payload["id"],
                email,
                user_payload["full_name"],
                user_payload["password_hash"],
                user_payload.get("bio") or "",
                user_payload.get("avatar_url") or "",
                1 if user_payload.get("is_active", True) else 0,
                int(user_payload.get("token_version", 0)),
                user_payload["created_at"],
            ),
        )
        connection.commit()


def get_user(email: str, include_password: bool = False) -> Optional[Dict[str, Any]]:
    with _conn() as connection:
        row = connection.execute(
            """
            SELECT id, email, full_name, password_hash, bio, avatar_url, is_active, token_version, created_at
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["is_active"] = bool(payload.get("is_active", 1))
        payload["token_version"] = int(payload.get("token_version", 0) or 0)
        if not include_password:
            payload.pop("password_hash", None)
        return payload


def update_user_profile(email: str, profile_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    user = get_user(email, include_password=True)
    if not user:
        return None

    full_name = profile_data.get("full_name", user["full_name"])
    bio = profile_data.get("bio", user.get("bio") or "")
    avatar_url = profile_data.get("avatar_url", user.get("avatar_url") or "")

    with _conn() as connection:
        connection.execute(
            """
            UPDATE users
            SET full_name = ?, bio = ?, avatar_url = ?
            WHERE email = ?
            """,
            (full_name, bio, avatar_url, email),
        )
        connection.commit()
    return get_user(email, include_password=False)


def update_password(email: str, password_hash: str) -> bool:
    with _conn() as connection:
        cursor = connection.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (password_hash, email),
        )
        connection.commit()
        return cursor.rowcount > 0


def set_user_active(email: str, is_active: bool) -> bool:
    with _conn() as connection:
        cursor = connection.execute(
            "UPDATE users SET is_active = ? WHERE email = ?",
            (1 if is_active else 0, email),
        )
        connection.commit()
        return cursor.rowcount > 0


def list_users(skip: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
    with _conn() as connection:
        rows = connection.execute(
            """
            SELECT id, email, full_name, bio, avatar_url, is_active, created_at
            FROM users
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, skip),
        ).fetchall()
        users = [dict(r) for r in rows]
        for user in users:
            user["is_active"] = bool(user.get("is_active", 1))
        return users


def rotate_token_version(email: str) -> int:
    with _conn() as connection:
        connection.execute(
            """
            UPDATE users
            SET token_version = COALESCE(token_version, 0) + 1
            WHERE email = ?
            """,
            (email,),
        )
        connection.commit()
        row = connection.execute(
            "SELECT token_version FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        return int(row["token_version"] if row else 0)


def count_users(active_only: bool = False) -> int:
    with _conn() as connection:
        if active_only:
            row = connection.execute("SELECT COUNT(*) AS cnt FROM users WHERE is_active = 1").fetchone()
        else:
            row = connection.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
        return int(row["cnt"] if row else 0)


def add_activity(
    activity_id: str,
    user_email: str,
    activity_type: str,
    description: str,
    timestamp: datetime,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    with _conn() as connection:
        connection.execute(
            """
            INSERT INTO activities (activity_id, user_email, activity_type, description, timestamp, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                activity_id,
                user_email,
                activity_type,
                description,
                timestamp.isoformat(),
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )
        connection.commit()


def get_activities(user_email: str, limit: int = 20) -> List[Dict[str, Any]]:
    with _conn() as connection:
        rows = connection.execute(
            """
            SELECT activity_id, user_email, activity_type, description, timestamp, metadata_json
            FROM activities
            WHERE user_email = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (user_email, limit),
        ).fetchall()
        activities: List[Dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["metadata"] = json.loads(payload.pop("metadata_json") or "{}")
            payload["timestamp"] = datetime.fromisoformat(payload["timestamp"])
            activities.append(payload)
        return activities


def count_activities() -> int:
    with _conn() as connection:
        row = connection.execute("SELECT COUNT(*) AS cnt FROM activities").fetchone()
        return int(row["cnt"] if row else 0)


def count_activities_by_type(activity_type: str) -> int:
    with _conn() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS cnt FROM activities WHERE activity_type = ?",
            (activity_type,),
        ).fetchone()
        return int(row["cnt"] if row else 0)


def count_activities_by_type_for_user(user_email: str, activity_type: str) -> int:
    with _conn() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM activities
            WHERE user_email = ? AND activity_type = ?
            """,
            (user_email, activity_type),
        ).fetchone()
        return int(row["cnt"] if row else 0)


def get_usage_by_date(user_email: str, days: int = 30) -> List[Dict[str, Any]]:
    window_days = max(1, int(days))
    since_expr = f"-{window_days} days"
    with _conn() as connection:
        rows = connection.execute(
            """
            SELECT
                substr(timestamp, 1, 10) AS day,
                SUM(CASE WHEN activity_type = 'asr' THEN 1 ELSE 0 END) AS asr_calls,
                SUM(CASE WHEN activity_type = 'tts' THEN 1 ELSE 0 END) AS tts_calls,
                SUM(CASE WHEN activity_type = 'nlp' THEN 1 ELSE 0 END) AS nlp_calls,
                COUNT(*) AS total_calls
            FROM activities
                        WHERE user_email = ?
                            AND timestamp >= datetime('now', ?)
            GROUP BY day
            ORDER BY day DESC
            LIMIT ?
            """,
                        (user_email, since_expr, window_days),
        ).fetchall()
        return [dict(r) for r in rows]


def count_active_users_today() -> int:
    with _conn() as connection:
        row = connection.execute(
            """
            SELECT COUNT(DISTINCT user_email) AS cnt
            FROM activities
            WHERE timestamp >= datetime(date('now'))
              AND timestamp < datetime(date('now', '+1 day'))
            """
        ).fetchone()
        return int(row["cnt"] if row else 0)


def count_new_users_this_month() -> int:
    with _conn() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM users
            WHERE created_at >= strftime('%Y-%m-01T00:00:00', 'now')
              AND created_at < strftime('%Y-%m-01T00:00:00', 'now', '+1 month')
            """
        ).fetchone()
        return int(row["cnt"] if row else 0)


init_db()
