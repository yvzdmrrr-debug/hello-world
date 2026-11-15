"""Token muhasebesi, fiyat tarifeleri, kota ve bütçe yönetimi.

Kurallar: bilinmeyen fiyat sıfır sayılmaz; geçmiş kayıtlar yeni fiyatla yeniden yazılmaz
(her kullanım, o andaki tarife sürümüyle saklanır); tahmini değerler `estimated` ile işaretlenir.
"""
import uuid
from datetime import datetime, timedelta, timezone

from .db import DB, now
from .providers import YEREL
from .security import Security

DEFAULT_BUDGETS = {"gunluk": 5.0, "aylik": 50.0, "gorev": 1.0, "onay_esigi": 0.5}

# Kaynak: Anthropic fiyat tablosu (claude-api belgesi, 2026-11-03 önbelleği). USD / 1M token.
KNOWN_PRICES = {
    "anthropic/claude-fable-5-2": (8.0, 40.0), "anthropic/claude-opus-5-5": (4.0, 20.0),
    "anthropic/claude-opus-5": (5.0, 25.0), "anthropic/claude-sonnet-5-5": (2.0, 10.0),
    "anthropic/claude-sonnet-5": (2.0, 10.0), "anthropic/claude-haiku-5-5": (0.10, 0.50),
    "anthropic/claude-haiku-4-5": (1.0, 5.0),
}


class Economy:
    def __init__(self, db: DB, security: Security):
        self.db, self.sec = db, security
        self.clock = lambda: datetime.now(timezone.utc)  # testlerde değiştirilebilir

    # ---------------------------------------------------- sağlayıcı ve model
    def add_provider(self, name, kind, base_url, auth_env):
        self.db.run("INSERT INTO providers(name,kind,base_url,auth_env,status) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(name) DO UPDATE SET kind=excluded.kind, "
                    "base_url=excluded.base_url, auth_env=excluded.auth_env",
                    (name, kind, base_url, auth_env, "bilinmiyor"))

    def provider_status(self, name, ok: bool, error: str = ""):
        if ok:
            self.db.run("UPDATE providers SET status='kullanılabilir', last_ok=? WHERE name=?",
                        (now(), name))
        else:
            self.db.run("UPDATE providers SET status='hata', last_error=? WHERE name=?",
                        (error[:300], name))

    def upsert_model(self, provider, model, tier, capabilities="metin", context=None,
                     max_output=None) -> str:
        mid = f"{provider}/{model}"
        self.db.run("INSERT INTO models VALUES(?,?,?,?,?,?,?,1) ON CONFLICT(id) DO UPDATE SET "
                    "context=excluded.context, max_output=excluded.max_output, available=1",
                    (mid, provider, model, tier, capabilities, context, max_output))
        kind = self.db.one("SELECT kind FROM providers WHERE name=?", (provider,))
        if not self.price(mid):
            if kind and kind["kind"] == YEREL:
                self.set_price(mid, 0.0, 0.0, source="yerel model (API ücreti yok)")
            elif mid in KNOWN_PRICES:
                self.set_price(mid, *KNOWN_PRICES[mid],
                               source="Anthropic fiyat tablosu, 2026-11-03")
        return mid

    def models(self) -> list[dict]:
        return self.db.all(
            "SELECT m.*, p.kind FROM models m JOIN providers p ON p.name=m.provider "
            "ORDER BY m.tier, m.id")

    def set_tier(self, model_id, tier: int):
        self.db.run("UPDATE models SET tier=? WHERE id=?", (tier, model_id))

    # ------------------------------------------------------------- fiyat
    def set_price(self, model_id, inp, out, cache_read=None, cache_write=None, *,
                  source="kullanıcı tanımı", currency="USD") -> int:
        prev = self.price(model_id)
        version = (prev["version"] + 1) if prev else 1
        self.db.run("INSERT INTO model_pricing(model_id,version,input_per_m,output_per_m,"
                    "cache_read_per_m,cache_write_per_m,currency,source,verified_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (model_id, version, inp, out, cache_read, cache_write, currency, source, now()))
        return version

    def price(self, model_id):
        return self.db.one("SELECT * FROM model_pricing WHERE model_id=? "
                           "ORDER BY version DESC LIMIT 1", (model_id,))

    @staticmethod
    def cost(price, inp, out, cache_read=0, cache_write=0, tool_cost=0.0):
        """Fiyat bilinmiyorsa None döner (sıfır DEĞİL)."""
        if not price:
            return None
        cr = price["cache_read_per_m"] if price["cache_read_per_m"] is not None else price["input_per_m"]
        cw = price["cache_write_per_m"] if price["cache_write_per_m"] is not None else price["input_per_m"]
        return round((inp * price["input_per_m"] + out * price["output_per_m"]
                      + cache_read * cr + cache_write * cw) / 1_000_000 + tool_cost, 8)

    def estimate(self, model_id, inp, out=1000):
        return self.cost(self.price(model_id), inp, out)

    # ---------------------------------------------------------- muhasebe
    def record_usage(self, *, task_id, subtask_id, model_id, started, status, comp=None,
                     agent="jarvis", purpose="gorev") -> str:
        price = self.price(model_id)
        c = comp
        inp, out = (c.input_tokens, c.output_tokens) if c else (0, 0)
        cr, cw, rs = (c.cache_read, c.cache_write, c.reasoning) if c else (0, 0, 0)
        rid = uuid.uuid4().hex
        self.db.run(
            "INSERT INTO token_usage VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, task_id, subtask_id, agent, model_id.split("/")[0], model_id, started, now(),
             inp, out, cw, cr, rs, 0.0, self.cost(price, inp, out, cr, cw),
             price["currency"] if price else None, price["version"] if price else None,
             status, int(bool(c and c.estimated)), purpose))
        return rid

    def spent(self, since: str | None = None, task_id=None, model_id=None) -> float:
        sql, p = "SELECT COALESCE(SUM(cost),0) s FROM token_usage WHERE 1=1", []
        for cond, v in (("started>=?", since), ("task_id=?", task_id), ("model_id=?", model_id)):
            if v is not None:
                sql += f" AND {cond}"
                p.append(v)
        return self.db.one(sql, p)["s"]

    # ------------------------------------------------------------- bütçe
    def budget(self, key: str) -> float:
        return float(self.db.get_setting(f"butce.{key}", DEFAULT_BUDGETS[key]))

    def set_budget(self, key: str, usd: float):
        if key not in DEFAULT_BUDGETS or usd < 0:
            raise ValueError("Geçersiz bütçe")
        self.db.set_setting(f"butce.{key}", str(usd))

    def remaining(self) -> dict:
        t = self.clock()
        day = t.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
        month = t.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
        return {"gunluk_harcanan": self.spent(day), "aylik_harcanan": self.spent(month),
                "gunluk_kalan": self.budget("gunluk") - self.spent(day),
                "aylik_kalan": self.budget("aylik") - self.spent(month)}

    def check_budget(self, task_id, model_id, est_cost):
        """Sınırı aşacak ya da maliyeti bilinmeyen çağrı, kullanıcı onayı olmadan başlamaz."""
        r = self.remaining()
        reason = None
        if est_cost is None:
            reason = "fiyatı bilinmeyen model"
        elif est_cost > r["gunluk_kalan"]:
            reason = "günlük bütçe aşımı"
        elif est_cost > r["aylik_kalan"]:
            reason = "aylık bütçe aşımı"
        elif self.spent(task_id=task_id) + est_cost > self.budget("gorev"):
            reason = "görev bütçesi aşımı"
        elif est_cost > self.budget("onay_esigi"):
            reason = "pahalı işlem"
        if reason:
            self.sec.check("spend.money", f"{model_id} | {reason}")

    # -------------------------------------------------------------- kota
    def set_quota(self, model_id, daily_requests: int, reset_hour_utc: int = 0, estimated=True):
        self.db.run("INSERT INTO model_quotas(model_id,daily_requests,reset_hour_utc,used,day,"
                    "estimated) VALUES(?,?,?,0,?,?) ON CONFLICT(model_id) DO UPDATE SET "
                    "daily_requests=excluded.daily_requests, "
                    "reset_hour_utc=excluded.reset_hour_utc, estimated=excluded.estimated",
                    (model_id, daily_requests, reset_hour_utc, "", int(estimated)))

    def _quota_day(self, reset_hour: int) -> str:
        return (self.clock() - timedelta(hours=reset_hour)).date().isoformat()

    def quota_ok(self, model_id) -> bool:
        """Kota günü sağlayıcının yenilenme saatine göre döner; kullanılmayan hak devretmez."""
        q = self.db.one("SELECT * FROM model_quotas WHERE model_id=?", (model_id,))
        day = self._quota_day(q["reset_hour_utc"] if q else 0)
        if not q:
            return True
        if q["exhausted_day"] == day:
            return False
        if q["day"] != day:
            self.db.run("UPDATE model_quotas SET used=0, day=? WHERE model_id=?", (day, model_id))
            return True
        return q["daily_requests"] is None or q["used"] < q["daily_requests"]

    def consume_quota(self, model_id):
        self.db.run("UPDATE model_quotas SET used=used+1 WHERE model_id=?", (model_id,))

    def mark_exhausted(self, model_id):
        """Sağlayıcı kota hatası verdi: bu kota günü boyunca aday listesinden çıkar."""
        q = self.db.one("SELECT reset_hour_utc FROM model_quotas WHERE model_id=?", (model_id,))
        day = self._quota_day(q["reset_hour_utc"] if q else 0)
        self.db.run("INSERT INTO model_quotas(model_id,exhausted_day,day,used) VALUES(?,?,?,0) "
                    "ON CONFLICT(model_id) DO UPDATE SET exhausted_day=excluded.exhausted_day",
                    (model_id, day, day))

    # -------------------------------------------------------- performans
    def performance(self, model_id, kind=None) -> dict:
        sql, p = ("SELECT COUNT(*) n, COALESCE(SUM(ok AND test_ok),0) ok, AVG(duration) d "
                  "FROM model_attempts WHERE model_id=?"), [model_id]
        if kind:
            sql += " AND kind=?"
            p.append(kind)
        r = self.db.one(sql, p)
        return {"n": r["n"], "basari": (r["ok"] / r["n"]) if r["n"] else None, "sure": r["d"]}

    # ------------------------------------------------------------ raporlar
    def task_report(self, task_id) -> dict:
        r = self.db.one(
            "SELECT COUNT(*) istek, COALESCE(SUM(input_tokens),0) giris, "
            "COALESCE(SUM(output_tokens),0) cikis, COALESCE(SUM(cache_read_tokens),0) onbellek, "
            "COALESCE(SUM(cost),0) maliyet, "
            "COALESCE(SUM(CASE WHEN status!='basarili' THEN cost ELSE 0 END),0) basarisiz_maliyet, "
            "COALESCE(SUM(CASE WHEN status!='basarili' THEN input_tokens+output_tokens ELSE 0 END),0)"
            " basarisiz_token, COALESCE(SUM(estimated),0) tahmini_kayit, "
            "COALESCE(SUM(cost IS NULL),0) fiyati_bilinmeyen "
            "FROM token_usage WHERE task_id=?", (task_id,))
        r["devir"] = self.db.one("SELECT COUNT(*) n FROM task_handoffs WHERE task_id=?",
                                 (task_id,))["n"]
        r["modeller"] = [x["model_id"] for x in self.db.all(
            "SELECT DISTINCT model_id FROM token_usage WHERE task_id=? ORDER BY model_id", (task_id,))]
        return r

    def totals(self) -> dict:
        t = self.db.one(
            "SELECT COUNT(*) istek, COALESCE(SUM(input_tokens),0) giris, "
            "COALESCE(SUM(output_tokens),0) cikis, COALESCE(SUM(cost),0) maliyet, "
            "COALESCE(SUM(cost IS NULL),0) fiyati_bilinmeyen, "
            "COALESCE(SUM(estimated),0) tahmini FROM token_usage")
        t.update(self.remaining())
        t["devir"] = self.db.one("SELECT COUNT(*) n FROM task_handoffs")["n"]
        t["model_bazli"] = self.db.all(
            "SELECT model_id, COUNT(*) istek, SUM(input_tokens) giris, SUM(output_tokens) cikis, "
            "COALESCE(SUM(cost),0) maliyet FROM token_usage GROUP BY model_id ORDER BY maliyet DESC")
        t["gunluk"] = self.db.all(
            "SELECT substr(started,1,10) gun, SUM(input_tokens) giris, SUM(output_tokens) cikis, "
            "COALESCE(SUM(cost),0) maliyet FROM token_usage GROUP BY gun ORDER BY gun DESC LIMIT 14")
        return t
