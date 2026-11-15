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
-- V40 LLM ve token ekonomisi
CREATE TABLE IF NOT EXISTS providers(
  name TEXT PRIMARY KEY, kind TEXT, base_url TEXT, auth_env TEXT, status TEXT,
  last_error TEXT, last_ok TEXT);
CREATE TABLE IF NOT EXISTS models(
  id TEXT PRIMARY KEY, provider TEXT, model TEXT, tier INTEGER, capabilities TEXT,
  context INTEGER, max_output INTEGER, available INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS model_pricing(
  id INTEGER PRIMARY KEY AUTOINCREMENT, model_id TEXT, version INTEGER, input_per_m REAL,
  output_per_m REAL, cache_read_per_m REAL, cache_write_per_m REAL, currency TEXT,
  source TEXT, verified_at TEXT);
CREATE TABLE IF NOT EXISTS model_quotas(
  model_id TEXT PRIMARY KEY, daily_requests INTEGER, reset_hour_utc INTEGER DEFAULT 0,
  used INTEGER DEFAULT 0, day TEXT, exhausted_day TEXT, estimated INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS subtasks(
  id INTEGER PRIMARY KEY AUTOINCREMENT, goal_hash TEXT, idx INTEGER, task_id TEXT,
  title TEXT, tier INTEGER, kind TEXT, status TEXT, result TEXT, model_id TEXT);
CREATE TABLE IF NOT EXISTS task_checkpoints(
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, ts TEXT, state TEXT);
CREATE TABLE IF NOT EXISTS task_handoffs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, subtask_id INTEGER, ts TEXT,
  from_model TEXT, to_model TEXT, reason TEXT, package TEXT, memory_ids TEXT);
CREATE TABLE IF NOT EXISTS model_attempts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, subtask_id INTEGER, model_id TEXT,
  kind TEXT, ts TEXT, ok INTEGER, test_ok INTEGER, error TEXT, duration REAL);
CREATE TABLE IF NOT EXISTS token_usage(
  id TEXT PRIMARY KEY, task_id TEXT, subtask_id INTEGER, agent TEXT, provider TEXT,
  model_id TEXT, started TEXT, ended TEXT, input_tokens INTEGER, output_tokens INTEGER,
  cache_write_tokens INTEGER, cache_read_tokens INTEGER, reasoning_tokens INTEGER,
  tool_cost REAL, cost REAL, currency TEXT, pricing_version INTEGER, status TEXT,
  estimated INTEGER, purpose TEXT);
CREATE TABLE IF NOT EXISTS memory_embeddings(
  memory_id TEXT PRIMARY KEY, content_hash TEXT, vector TEXT);
CREATE TABLE IF NOT EXISTS memory_retrievals(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, task_id TEXT, query TEXT, memory_ids TEXT,
  sent_tokens INTEGER, pool_tokens INTEGER);
CREATE TABLE IF NOT EXISTS solutions(
  goal_hash TEXT PRIMARY KEY, task_id TEXT, result TEXT, models TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS locks(resource TEXT PRIMARY KEY, owner TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS test_results(
  test_no INTEGER PRIMARY KEY, name TEXT, ok INTEGER, ts TEXT);
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
