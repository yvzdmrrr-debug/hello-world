"""Güvenlik ve yetki motoru.

Politika bu dosyada sabittir (salt okunur). Çalışma anında hiçbir bileşen —
Skill, ajan veya LLM çıktısı — bu tabloyu değiştiremez; değiştirme girişimi
'YASAK' sınıfındadır ve her zaman reddedilir.
"""
from types import MappingProxyType

from .db import DB, now

DUSUK, ONAY, YASAK = "DUSUK", "ONAY", "YASAK"

POLICY = MappingProxyType({
    "memory.write": DUSUK, "memory.read": DUSUK, "memory.export": DUSUK,
    "task.run": DUSUK, "skill.run": DUSUK, "skill.install_low": DUSUK,
    "agent.create": DUSUK, "experiment.run": DUSUK, "finance.paper_trade": DUSUK,
    "llm.call": DUSUK,
    "memory.delete": ONAY, "skill.install_high": ONAY, "core.modify": ONAY,
    "version.rollback": ONAY, "connection.add": ONAY, "finance.real_trade": ONAY,
    "spend.money": ONAY, "data.share": ONAY,
    "security.modify": YASAK, "security.disable": YASAK, "audit.delete": YASAK,
})


class Stopped(Exception):
    """Kullanıcı sistemi durdurdu."""


class Denied(Exception):
    """İşlem politikaya göre yasak."""


class ApprovalRequired(Exception):
    def __init__(self, approval_id: int, action: str):
        super().__init__(f"'{action}' için kullanıcı onayı gerekiyor (onay no: {approval_id})")
        self.approval_id = approval_id


class Security:
    def __init__(self, db: DB):
        self.db = db

    # --- durdurma anahtarı ---
    def stop(self):
        self.db.set_setting("stopped", "1")
        self._audit("system.stop", "", "UYGULANDI")

    def resume(self):
        self.db.set_setting("stopped", "0")
        self._audit("system.resume", "", "UYGULANDI")

    @property
    def stopped(self) -> bool:
        return self.db.get_setting("stopped", "0") == "1"

    # --- yetki denetimi ---
    def check(self, action: str, detail: str = "") -> None:
        """İşleme izin varsa sessizce döner; yoksa istisna fırlatır. Her çağrı kayda geçer."""
        if self.stopped:
            self._audit(action, detail, "DURDURULDU")
            raise Stopped("Sistem kullanıcı tarafından durduruldu.")
        level = POLICY.get(action, ONAY)  # bilinmeyen işlem: en az onay ister
        if level == YASAK:
            self._audit(action, detail, "REDDEDILDI")
            raise Denied(f"'{action}' güvenlik politikasına göre yasak.")
        if level == ONAY:
            row = self.db.one("SELECT id FROM approvals WHERE action=? AND detail=? "
                              "AND status='ONAYLANDI'", (action, detail))
            if row:  # onay tek kullanımlıktır
                self.db.run("UPDATE approvals SET status='KULLANILDI' WHERE id=?", (row["id"],))
                self._audit(action, detail, "ONAYLA UYGULANDI")
                return
            pending = self.db.one("SELECT id FROM approvals WHERE action=? AND detail=? "
                                  "AND status='BEKLIYOR'", (action, detail))
            aid = pending["id"] if pending else self.db.run(
                "INSERT INTO approvals(ts,action,detail,status) VALUES(?,?,?,'BEKLIYOR')",
                (now(), action, detail))
            self._audit(action, detail, "ONAY BEKLIYOR")
            raise ApprovalRequired(aid, action)
        self._audit(action, detail, "IZIN VERILDI")

    def decide(self, approval_id: int, approve: bool) -> bool:
        status = "ONAYLANDI" if approve else "REDDEDILDI"
        row = self.db.one("SELECT id FROM approvals WHERE id=? AND status='BEKLIYOR'",
                          (approval_id,))
        if not row:
            return False
        self.db.run("UPDATE approvals SET status=? WHERE id=?", (status, approval_id))
        self._audit("approval.decide", f"{approval_id}:{status}", "UYGULANDI")
        return True

    def pending(self) -> list[dict]:
        return self.db.all("SELECT * FROM approvals WHERE status='BEKLIYOR' ORDER BY id")

    def _audit(self, action, detail, outcome):
        self.db.run("INSERT INTO audit(ts,action,detail,outcome) VALUES(?,?,?,?)",
                    (now(), action, detail[:500], outcome))
