# ==========================================================
#  DARK ELGENERAL — Database (SQLite, thread-safe)
#  © 2026 Dark Elgeneral • Developed by Adam Elgeneral
# ==========================================================

import json
import sqlite3
import threading
import time
from contextlib import contextmanager

import config
from utils import now_str, today_str

_lock = threading.RLock()

USER_SETTINGS = ("theme", "site_lang")


@contextmanager
def _db():
    with _lock:
        conn = sqlite3.connect(config.DATABASE_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init_db():
    with _db() as conn:
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            pass

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id         INTEGER PRIMARY KEY,
                username        TEXT    DEFAULT '',
                first_name      TEXT    DEFAULT '',
                joined_at       TEXT,
                last_seen       TEXT,
                banned          INTEGER DEFAULT 0,
                theme           TEXT    DEFAULT 'dark',
                site_lang       TEXT    DEFAULT 'ar',
                last_generation REAL    DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                project_id  TEXT PRIMARY KEY,
                user_id     INTEGER,
                name        TEXT,
                type        TEXT,
                idea        TEXT,
                path        TEXT,
                files_count INTEGER DEFAULT 0,
                version     INTEGER DEFAULT 1,
                created_at  TEXT,
                updated_at  TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage (
                user_id INTEGER,
                day     TEXT,
                count   INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, day)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id)")


# ----------------------------------------------------------
#  USERS
# ----------------------------------------------------------

def upsert_user(user):
    """Create/update a user. Returns True when the user is new."""
    username = user.username or ""
    first_name = user.first_name or ""
    with _db() as conn:
        row = conn.execute("SELECT 1 FROM users WHERE user_id=?", (user.id,)).fetchone()
        if row:
            conn.execute(
                "UPDATE users SET username=?, first_name=?, last_seen=? WHERE user_id=?",
                (username, first_name, now_str(), user.id),
            )
            return False
        conn.execute(
            "INSERT INTO users (user_id, username, first_name, joined_at, last_seen) "
            "VALUES (?, ?, ?, ?, ?)",
            (user.id, username, first_name, now_str(), now_str()),
        )
        return True


def get_user(user_id):
    with _db() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def set_setting(user_id, key, value):
    if key not in USER_SETTINGS:
        return False
    with _db() as conn:
        conn.execute(f"UPDATE users SET {key}=? WHERE user_id=?", (value, user_id))
    return True


def is_banned(user_id):
    user = get_user(user_id)
    return bool(user and user["banned"])


def set_banned(user_id, banned):
    """Ban/unban any Telegram ID (even one that never started the bot)."""
    with _db() as conn:
        exists = conn.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not exists:
            if not banned:
                return True
            conn.execute(
                "INSERT INTO users (user_id, joined_at, banned) VALUES (?, ?, 1)",
                (user_id, now_str()),
            )
            return True
        conn.execute("UPDATE users SET banned=? WHERE user_id=?", (1 if banned else 0, user_id))
        return True


def all_user_ids():
    """Active (not banned) users who really started the bot."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT user_id FROM users WHERE banned=0 AND last_seen IS NOT NULL"
        ).fetchall()
        return [row["user_id"] for row in rows]


def count_users():
    with _db() as conn:
        return conn.execute("SELECT COUNT(*) FROM users WHERE last_seen IS NOT NULL").fetchone()[0]


def count_banned():
    with _db() as conn:
        return conn.execute("SELECT COUNT(*) FROM users WHERE banned=1").fetchone()[0]


# ----------------------------------------------------------
#  KEY / VALUE SETTINGS  (maintenance, forced channel, ...)
# ----------------------------------------------------------

def get_kv(key, default=None):
    with _db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except ValueError:
        return default


def set_kv(key, value):
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, json.dumps(value, ensure_ascii=False)),
        )


# ----------------------------------------------------------
#  LIMITS
# ----------------------------------------------------------

def get_usage_today(user_id):
    with _db() as conn:
        row = conn.execute(
            "SELECT count FROM usage WHERE user_id=? AND day=?", (user_id, today_str())
        ).fetchone()
        return row["count"] if row else 0


def register_generation(user_id):
    """Count one successful generation and start the cooldown."""
    with _db() as conn:
        cursor = conn.execute(
            "UPDATE usage SET count = count + 1 WHERE user_id=? AND day=?",
            (user_id, today_str()),
        )
        if cursor.rowcount == 0:
            conn.execute(
                "INSERT INTO usage (user_id, day, count) VALUES (?, ?, 1)",
                (user_id, today_str()),
            )
        conn.execute(
            "UPDATE users SET last_generation=? WHERE user_id=?", (time.time(), user_id)
        )


def cooldown_left(user_id):
    user = get_user(user_id)
    if not user:
        return 0
    left = config.COOLDOWN_SECONDS - (time.time() - (user["last_generation"] or 0))
    return max(0, int(left + 0.999))


# ----------------------------------------------------------
#  PROJECTS
# ----------------------------------------------------------

def add_project(project_id, user_id, name, ptype, idea, path, files_count):
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO projects "
            "(project_id, user_id, name, type, idea, path, files_count, version, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
            (project_id, user_id, name, ptype, idea, path, files_count, now_str(), now_str()),
        )


def update_project(project_id, files_count):
    with _db() as conn:
        conn.execute(
            "UPDATE projects SET files_count=?, version=version+1, updated_at=? WHERE project_id=?",
            (files_count, now_str(), project_id),
        )


def get_project(project_id, user_id=None):
    with _db() as conn:
        if user_id is None:
            row = conn.execute(
                "SELECT * FROM projects WHERE project_id=?", (project_id,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM projects WHERE project_id=? AND user_id=?",
                (project_id, user_id),
            ).fetchone()
        return dict(row) if row else None


def list_projects(user_id, limit=6, offset=0):
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM projects WHERE user_id=? ORDER BY updated_at DESC, created_at DESC "
            "LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        ).fetchall()
        return [dict(row) for row in rows]


def count_projects(user_id):
    with _db() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM projects WHERE user_id=?", (user_id,)
        ).fetchone()[0]


def delete_project(project_id, user_id):
    with _db() as conn:
        cursor = conn.execute(
            "DELETE FROM projects WHERE project_id=? AND user_id=?", (project_id, user_id)
        )
        return cursor.rowcount > 0


# ----------------------------------------------------------
#  ADMIN STATS
# ----------------------------------------------------------

def get_stats():
    today = today_str()
    with _db() as conn:
        one = lambda sql, args=(): conn.execute(sql, args).fetchone()[0]

        stats = {
            "users": one("SELECT COUNT(*) FROM users WHERE last_seen IS NOT NULL"),
            "users_today": one("SELECT COUNT(*) FROM users WHERE joined_at LIKE ?", (today + "%",)),
            "banned": one("SELECT COUNT(*) FROM users WHERE banned=1"),
            "projects": one("SELECT COUNT(*) FROM projects"),
            "projects_today": one(
                "SELECT COUNT(*) FROM projects WHERE created_at LIKE ?", (today + "%",)
            ),
            "generations_today": one(
                "SELECT COALESCE(SUM(count), 0) FROM usage WHERE day=?", (today,)
            ),
        }
        stats["by_type"] = [
            (row["type"], row["total"])
            for row in conn.execute(
                "SELECT type, COUNT(*) AS total FROM projects GROUP BY type ORDER BY total DESC"
            ).fetchall()
        ]
        stats["top_users"] = [
            (row["user_id"], row["first_name"], row["username"], row["total"])
            for row in conn.execute(
                "SELECT u.user_id, u.first_name, u.username, COUNT(p.project_id) AS total "
                "FROM projects p JOIN users u ON u.user_id = p.user_id "
                "GROUP BY u.user_id ORDER BY total DESC LIMIT 5"
            ).fetchall()
        ]
        return stats
