"""SQLite altyapısı: tüm kalıcı kayıtlar tek dosyada tutulur."""
import sqlite3
import threading
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS memory(
  id TEXT PRIMARY KEY, layer TEXT NOT NULL, content TEXT NOT NULL, source TEXT NOT NULL,
  created TEXT NOT NULL, task_id TEXT, verified INTEGER NOT NULL DEFAULT 0,
  confidence REAL NOT NULL DEFAULT 0.5, version INTEGER NOT NULL DEFAULT 1,
  access TEXT NOT NULL DEFAULT 'kullanici');
CREATE TABLE IF NOT EXISTS tasks(
  id TEXT PRIMARY KEY, goal TEXT NOT NULL, status TEXT NOT NULL, department TEXT,
  result TEXT, created TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS skills(
  name TEXT PRIMARY KEY, description TEXT, version INTEGER, tools TEXT, deps TEXT,
  permission TEXT, test_status TEXT, last_used TEXT, uses INTEGER DEFAULT 0,
  successes INTEGER DEFAULT 0, projects TEXT, path TEXT);
CREATE TABLE IF NOT EXISTS agents(
  name TEXT PRIMARY KEY, mission TEXT, expertise TEXT, skills TEXT, tools TEXT,
  criteria TEXT, created TEXT, runs INTEGER DEFAULT 0, successes INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS versions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, version TEXT, date TEXT, changes TEXT,
  components TEXT, tests TEXT, security TEXT, approval TEXT, rollback TEXT);
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, action TEXT, detail TEXT, outcome TEXT);
CREATE TABLE IF NOT EXISTS approvals(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, action TEXT, detail TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS experiments(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, hypothesis TEXT, criterion TEXT,
  environment TEXT, result TEXT, success INTEGER, lessons TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DB:
    """Tek bağlantı + kilit: panel sunucusunun iş parçacıklarıyla güvenle paylaşılır."""

    def __init__(self, path: str = "jarvis.db"):
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def close(self):
        self._conn.close()

    def run(self, sql: str, params=()) -> int:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur.lastrowid

    def all(self, sql: str, params=()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def one(self, sql: str, params=()):
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def get_setting(self, key: str, default=None):
        row = self.one("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        self.run("INSERT INTO settings(key,value) VALUES(?,?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
