"""Gelişim metrikleri (Bölüm 23) — yalnızca veritabanındaki gerçek kayıtlardan hesaplanır."""
from .db import DB


def collect(db: DB) -> dict:
    t = {r["status"]: r["n"] for r in
         db.all("SELECT status, COUNT(*) n FROM tasks GROUP BY status")}
    done, failed = t.get("TAMAMLANDI", 0), t.get("BAŞARISIZ", 0)
    finished = done + failed
    s = db.one("SELECT COALESCE(SUM(uses),0) u, COALESCE(SUM(successes),0) ok, "
               "COUNT(*) n, COALESCE(SUM(uses>1),0) reused FROM skills")
    return {
        "gorev_toplam": sum(t.values()),
        "gorev_durumlari": t,
        "gorev_basari_orani": round(done / finished * 100, 1) if finished else None,
        "skill_sayisi": s["n"],
        "skill_calistirma": s["u"],
        "skill_basari_orani": round(s["ok"] / s["u"] * 100, 1) if s["u"] else None,
        "skill_yeniden_kullanim_orani": round(s["reused"] / s["n"] * 100, 1) if s["n"] else None,
        "geri_alinan": t.get("GERİ ALINDI", 0),
        "guvenlik_olaylari": db.one(
            "SELECT COUNT(*) n FROM audit WHERE outcome='REDDEDILDI'")["n"],
        "bekleyen_onay": db.one(
            "SELECT COUNT(*) n FROM approvals WHERE status='BEKLIYOR'")["n"],
    }
