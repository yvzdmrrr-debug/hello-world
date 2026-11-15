"""Görev durum makinesi (Bölüm 25)."""
import uuid

from .db import DB, now

STATES = ("PLANLANDI", "ÇALIŞIYOR", "TEST EDİLİYOR", "ONAY BEKLİYOR", "TAMAMLANDI",
          "BAŞARISIZ", "ENGELLENDİ", "GERİ ALINDI")
TRANSITIONS = {
    "PLANLANDI": {"ÇALIŞIYOR", "ENGELLENDİ", "ONAY BEKLİYOR"},
    "ÇALIŞIYOR": {"TEST EDİLİYOR", "ONAY BEKLİYOR", "BAŞARISIZ", "ENGELLENDİ"},
    "TEST EDİLİYOR": {"TAMAMLANDI", "BAŞARISIZ"},
    "ONAY BEKLİYOR": {"ÇALIŞIYOR", "ENGELLENDİ"},
    "TAMAMLANDI": {"GERİ ALINDI"},
    "BAŞARISIZ": {"PLANLANDI"},
    "ENGELLENDİ": {"PLANLANDI"},
    "GERİ ALINDI": set(),
}


class Tasks:
    def __init__(self, db: DB):
        self.db = db

    def create(self, goal: str, department: str = "") -> str:
        tid = uuid.uuid4().hex[:10]
        self.db.run("INSERT INTO tasks VALUES(?,?,?,?,?,?,?)",
                    (tid, goal, "PLANLANDI", department, "", now(), now()))
        return tid

    def get(self, tid: str):
        return self.db.one("SELECT * FROM tasks WHERE id=?", (tid,))

    def move(self, tid: str, status: str, result: str | None = None):
        """TAMAMLANDI'ya yalnızca TEST EDİLİYOR üzerinden, yani doğrulamadan sonra geçilir."""
        cur = self.get(tid)["status"]
        if status not in TRANSITIONS[cur]:
            raise ValueError(f"Geçersiz durum geçişi: {cur} → {status}")
        if result is None:
            self.db.run("UPDATE tasks SET status=?, updated=? WHERE id=?", (status, now(), tid))
        else:
            self.db.run("UPDATE tasks SET status=?, result=?, updated=? WHERE id=?",
                        (status, result, now(), tid))

    def recent(self, limit: int = 20) -> list[dict]:
        return self.db.all("SELECT * FROM tasks ORDER BY created DESC LIMIT ?", (limit,))
