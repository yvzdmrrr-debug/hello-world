"""V40 LLM / token ekonomisi kabul testleri (Bölüm 26, TEST 01-30).

Sağlayıcılar burada benzetimdir (sahte adaptör ya da yerel HTTP sunucusu). Bu testler
mantığı doğrular; gerçek sağlayıcılarla canlı doğrulamanın yerini tutmaz.
"""
import json
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from jarvis import acceptance
from jarvis.core import Jarvis
from jarvis.dashboard import render
from jarvis.providers import (BULUT, YEREL, Completion, GeminiProvider, OpenAICompatProvider,
                              Provider, ProviderError, QuotaError, scrub)
from jarvis.retrieval import cosine, embed
from jarvis.router import classify, goal_hash, split

SECRET = "sk-test-SECRET1234567890"


class Fake(Provider):
    def __init__(self, name, kind=BULUT, models=("m",), behavior=None, auth_env=""):
        self.name, self.kind, self.base_url, self.auth_env = name, kind, f"fake://{name}", auth_env
        self.models, self.behavior = list(models), behavior or {}
        self.calls, self.listed = [], 0

    def list_models(self):
        self.listed += 1
        return [{"id": m, "context": 8000, "max_output": 1000} for m in self.models]

    def complete(self, model, prompt, system, timeout):
        self.calls.append((model, prompt))
        b = self.behavior.get(model, "ok")
        if callable(b):
            return b(prompt)
        if b == "hang":
            time.sleep(3)
        if b == "error":
            raise ProviderError(f"sunucu hatası, anahtar {SECRET}")
        if b == "quota":
            raise QuotaError("429 günlük kota doldu")
        return Completion("" if b == "empty" else f"yanıt[{model}]", 100, 50)


class Base(unittest.TestCase):
    def make(self, *providers, prices=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = tmp.name
        j = Jarvis(tmp.name, providers=list(providers))
        self.addCleanup(j.db.close)
        j.router.timeouts = {YEREL: 0.3, BULUT: 0.3}
        j.router.discover()
        for mid, (i, o) in (prices or {}).items():
            j.economy.set_price(mid, i, o, source="test")
        return j

    def local_cloud(self, local_behavior=None, cloud_behavior=None):
        self.local = Fake("yerel", YEREL, ["kucuk"], local_behavior)
        self.cloud = Fake("bulut", BULUT, ["orta"], cloud_behavior)
        j = self.make(self.local, self.cloud, prices={"bulut/orta": (2.0, 10.0)})
        j.economy.set_tier("bulut/orta", 3)
        return j

    def usage(self, j):
        return j.db.all("SELECT * FROM token_usage ORDER BY started, rowid")


class TestAcceptance(Base):
    def test_01_model_discovery(self):
        gem = Fake("gemini", models=[f"gemini-{i}" for i in range(49)])
        loc = Fake("yerel", YEREL, ["llama"])
        j = self.make(gem, loc)
        ids = [m["id"] for m in j.economy.models()]
        self.assertEqual(len([i for i in ids if i.startswith("gemini/")]), 49)
        self.assertIn("yerel/llama", ids)
        self.assertEqual(gem.calls + loc.calls, [])          # keşif ücretli çıkarım yapmaz
        self.assertIsNone(j.economy.estimate("gemini/gemini-0", 1000))  # bilinmeyen fiyat ≠ 0
        self.assertEqual(j.economy.estimate("yerel/llama", 1000), 0.0)
        bad = Fake("bozuk")
        bad.list_models = mock.Mock(side_effect=ProviderError("erişilemedi"))
        j2 = self.make(bad, Fake("iyi"))
        st = {p["name"]: p["status"] for p in j2.db.all("SELECT * FROM providers")}
        self.assertEqual(st, {"bozuk": "hata", "iyi": "kullanılabilir"})

    def test_02_pricing_and_capabilities_recorded(self):
        j = self.make(Fake("bulut", models=["orta"]))
        j.economy.set_price("bulut/orta", 2.0, 10.0, 0.2, 2.5, source="sağlayıcı fiyat sayfası")
        m = j.economy.models()[0]
        self.assertEqual((m["context"], m["max_output"], m["capabilities"]), (8000, 1000, "metin"))
        p = j.economy.price("bulut/orta")
        self.assertEqual((p["input_per_m"], p["output_per_m"], p["source"]),
                         (2.0, 10.0, "sağlayıcı fiyat sayfası"))
        self.assertTrue(p["verified_at"])

    def test_03_token_accounting(self):
        est = Fake("yerel", YEREL, ["kucuk"], {"kucuk": lambda p: Completion("tamam", 7, 3, estimated=True)})
        j = self.make(Fake("bulut", models=["orta"]), est, prices={"bulut/orta": (2.0, 10.0)})
        j.db.set_setting("manual_model", "bulut/orta")
        r = j.handle("Bana kısa bir slogan öner")
        j.db.set_setting("manual_model", "yerel/kucuk")
        j.handle("Bana başka bir slogan öner")
        a, b = self.usage(j)
        self.assertEqual((a["input_tokens"], a["output_tokens"], a["estimated"], a["task_id"]),
                         (100, 50, 0, r["gorev"]))
        self.assertAlmostEqual(a["cost"], 0.0007)
        self.assertEqual((b["input_tokens"], b["estimated"], b["cost"]), (7, 1, 0.0))
        for row in (a, b):
            for f in ("id", "provider", "model_id", "started", "ended", "status", "pricing_version"):
                self.assertIsNotNone(row[f])

    def test_04_tariffs(self):
        j = self.make(Fake("bulut", models=["orta", "bilinmeyen"]), prices={"bulut/orta": (2.0, 10.0)})
        e = j.economy
        self.assertAlmostEqual(e.cost(e.price("bulut/orta"), 1_000_000, 1_000_000), 12.0)
        e.set_price("bulut/orta", 2.0, 10.0, 0.2, 2.5)
        self.assertAlmostEqual(e.cost(e.price("bulut/orta"), 0, 0, 1_000_000, 1_000_000), 2.7)
        self.assertIsNone(e.cost(e.price("bulut/bilinmeyen"), 10, 10))
        j.db.set_setting("manual_model", "bulut/orta")
        j.handle("Bir slogan öner")
        before = self.usage(j)[0]
        e.set_price("bulut/orta", 200.0, 1000.0)             # fiyat değişti
        after = self.usage(j)[0]
        self.assertEqual((before["cost"], before["pricing_version"]),
                         (after["cost"], after["pricing_version"]))  # geçmiş yeniden yazılmaz
        self.assertEqual(e.price("bulut/orta")["version"], 3)

    def test_05_simple_task_goes_local(self):
        j = self.local_cloud()
        r = j.handle("özetle: uzun bir metin burada duruyor ve kısaltılması gerekiyor")
        self.assertEqual(r["durum"], "TAMAMLANDI")
        self.assertEqual(len(self.local.calls), 1)
        self.assertEqual(self.cloud.calls, [])
        self.assertEqual(j.handle("12*12")["sonuc"], "144")   # seviye 0: hiç LLM yok
        self.assertEqual(len(self.local.calls), 1)

    def test_06_local_hang_times_out(self):
        j = self.local_cloud({"kucuk": "hang"}, {"orta": "error"})
        t0 = time.monotonic()
        r = j.handle("özetle: bir metin")
        self.assertLess(time.monotonic() - t0, 2.5)
        self.assertEqual(r["durum"], "ENGELLENDİ")
        self.assertEqual(self.usage(j)[0]["status"], "zaman_asimi")

    def test_07_switch_to_alternative(self):
        j = self.local_cloud({"kucuk": "hang"})
        r = j.handle("özetle: bir metin")
        self.assertEqual((r["durum"], r["sonuc"]), ("TAMAMLANDI", "yanıt[orta]"))
        h = j.db.one("SELECT * FROM task_handoffs")
        self.assertEqual((h["from_model"], h["to_model"], h["reason"]),
                         ("yerel/kucuk", "bulut/orta", "zaman_asimi"))

    def _two_step(self):
        state = {"n": 0}

        def flaky(prompt):
            state["n"] += 1
            if state["n"] == 1:
                return Completion("ilk kısım hazır", 10, 5)
            raise ProviderError("bellek yetersiz")
        j = self.local_cloud({"kucuk": flaky})
        r = j.handle("özetle: birinci bölüm metni\nözetle: ikinci bölüm metni")
        return j, r

    def test_08_stronger_model_takes_over_half_done_work(self):
        j, r = self._two_step()
        self.assertEqual(r["durum"], "TAMAMLANDI")
        self.assertEqual(len(self.cloud.calls), 1)            # yalnızca eksik kısım
        prompt = self.cloud.calls[0][1]
        self.assertIn("ilk kısım hazır", prompt)              # tamamlanan iş aktarıldı
        self.assertIn("bellek yetersiz", prompt)              # başarısız deneme aktarıldı
        self.assertIn("ikinci bölüm", prompt)
        pkg = json.loads(j.db.one("SELECT package FROM task_handoffs")["package"])
        for key in ("orijinal_talep", "kabul_kriteri", "tamamlanan", "bekleyen",
                    "onceki_denemeler", "hafiza_kayitlari", "kullanilan_token", "harcanan",
                    "kalan_gorev_butcesi", "yapilacak"):
            self.assertIn(key, pkg)

    def test_09_handoff_preserves_existing_output(self):
        j, r = self._two_step()
        subs = j.db.all("SELECT * FROM subtasks ORDER BY idx")
        self.assertEqual((subs[0]["result"], subs[0]["model_id"]), ("ilk kısım hazır", "yerel/kucuk"))
        self.assertEqual(subs[1]["model_id"], "bulut/orta")
        self.assertIn("ilk kısım hazır", r["sonuc"])

    def test_10_previous_models_work_is_found(self):
        j = self.local_cloud()
        j.memory.add("hata_cozum", "Stripe webhook imza hatası: ham gövde kullanılarak çözüldü "
                     "(model: yerel/kucuk)", "yerel/kucuk", verified=True, confidence=0.9)
        j.handle("Stripe webhook imza hatası neden olur, açıkla")
        prompt = (self.local.calls or self.cloud.calls)[0][1]
        self.assertIn("ham gövde", prompt)
        row = j.db.one("SELECT * FROM memory_retrievals ORDER BY id DESC LIMIT 1")
        self.assertTrue(row["memory_ids"])                    # hangi kayıt kullanıldı: denetlenebilir

    def test_11_vector_similarity_search(self):
        a = embed("veritabanı bağlantısı zaman aşımına uğradı")
        self.assertGreater(cosine(a, embed("veritabanı bağlantı zaman aşımı")),
                           cosine(a, embed("kedi mama tarifi ve oyuncak")))
        j = self.make()
        mid = j.memory.add("hata_cozum", "Veritabanı bağlantısı zaman aşımına uğradı; havuz büyütüldü",
                           "test", verified=True)
        j.memory.add("proje", "Logo için turuncu renk seçildi", "test", verified=True)
        hits = j.retrieval.search("veritabanina baglanirken zamanasimi")  # kelime eşleşmesi yok
        self.assertEqual([h["id"] for h in hits], [mid])
        n = j.retrieval.embed_calls
        j.retrieval.search("veritabanina baglanirken zamanasimi")
        self.assertEqual(j.retrieval.embed_calls, n)          # içerik değişmedi: yeniden embedding yok
        j.memory.correct(mid, "Veritabanı bağlantısı zaman aşımı; havuz 20 yapıldı")
        j.retrieval.search("veritabanina baglanirken zamanasimi")
        self.assertEqual(j.retrieval.embed_calls, n + 1)

    def _noisy(self):
        j = self.local_cloud()
        for i in range(20):
            j.memory.add("proje", f"Toplantı notu {i}: ofis kahve makinesi ve park yeri düzeni "
                         "hakkında uzun uzun konuşuldu", "test", verified=True)
        j.memory.add("hata_cozum", "Redis önbellek anahtarı çakışması sürüm ön ekiyle çözüldü",
                     "test", verified=True)
        j.handle("Redis önbellek anahtarı çakışması için öneri ver")
        return j, (self.local.calls or self.cloud.calls)[0][1]

    def test_12_only_relevant_memory_is_sent(self):
        j, prompt = self._noisy()
        self.assertIn("sürüm ön ekiyle", prompt)
        self.assertNotIn("kahve makinesi", prompt)

    def test_13_completed_work_is_reused(self):
        j = self.local_cloud()
        first = j.handle("Bir slogan öner")
        calls = len(self.local.calls) + len(self.cloud.calls)
        again = j.handle("Bir slogan öner")
        self.assertEqual(len(self.local.calls) + len(self.cloud.calls), calls)
        self.assertEqual((again["durum"], again["sonuc"]), ("TAMAMLANDI", first["sonuc"]))
        self.assertIn("yeniden kullanıldı", " ".join(again["yapilanlar"]))
        self.assertEqual(len(self.usage(j)), 1)

    def test_14_failed_solution_not_accepted(self):
        j = self.local_cloud()
        j.router.validator = lambda sub, text: False
        r = j.handle("Bir slogan öner")
        self.assertEqual(r["durum"], "ENGELLENDİ")
        self.assertIsNone(j.db.one("SELECT * FROM solutions"))
        self.assertEqual(j.memory.counts()["konusma"], 0)     # başarısız çözüm hafızaya girmez
        self.assertTrue(all(a["test_ok"] == 0 for a in j.db.all("SELECT * FROM model_attempts")))
        self.assertTrue(all(u["status"] == "test_basarisiz" for u in self.usage(j)))

    def test_15_quota_error_handled(self):
        j = self.local_cloud({"kucuk": "quota"})
        r = j.handle("Bir slogan öner")
        self.assertEqual((r["durum"], r["sonuc"]), ("TAMAMLANDI", "yanıt[orta]"))
        self.assertEqual(self.usage(j)[0]["status"], "kota")
        self.assertFalse(j.economy.quota_ok("yerel/kucuk"))
        j.handle("Başka bir slogan öner")
        self.assertEqual(len(self.local.calls), 1)            # kotası dolan model yeniden denenmez

    def test_16_quota_renewal(self):
        j = self.local_cloud()
        e = j.economy
        t = datetime(2026, 1, 10, 6, 0, tzinfo=timezone.utc)
        e.clock = lambda: t
        e.set_quota("yerel/kucuk", 1, reset_hour_utc=8)
        e.set_quota("bulut/orta", 1, reset_hour_utc=0)
        for m in ("yerel/kucuk", "bulut/orta"):
            self.assertTrue(e.quota_ok(m))
            e.consume_quota(m)
            self.assertFalse(e.quota_ok(m))
        e.clock = lambda: t + timedelta(hours=1)              # 07:00 — henüz yenilenmedi
        self.assertFalse(e.quota_ok("yerel/kucuk"))
        e.clock = lambda: t + timedelta(hours=3)              # 09:00 — yalnızca 08:00'li yenilendi
        self.assertTrue(e.quota_ok("yerel/kucuk"))
        self.assertFalse(e.quota_ok("bulut/orta"))            # sağlayıcılar aynı saatte yenilenmez
        e.consume_quota("yerel/kucuk")
        self.assertFalse(e.quota_ok("yerel/kucuk"))           # kullanılmayan hak devretmez: sınır yine 1

    def test_17_pending_task_resumes(self):
        only = Fake("yerel", YEREL, ["kucuk"], {"kucuk": "quota"})
        j = self.make(only)
        t = datetime(2026, 1, 10, 6, 0, tzinfo=timezone.utc)
        j.economy.clock = lambda: t
        r = j.handle("Bir slogan öner")
        self.assertEqual(r["durum"], "ENGELLENDİ")
        self.assertIn("devam-et", r["sonuc"])
        self.assertEqual(j.resume_pending()[0]["durum"], "ENGELLENDİ")   # kota hâlâ dolu
        only.behavior = {}
        j.economy.clock = lambda: t + timedelta(days=1)
        out = j.resume_pending()[0]
        self.assertEqual((out["gorev"], out["durum"], out["sonuc"]),
                         (r["gorev"], "TAMAMLANDI", "yanıt[kucuk]"))

    def test_18_expensive_model_needs_approval(self):
        pricey = Fake("bulut", models=["guclu"])
        j = self.make(pricey, prices={"bulut/guclu": (100.0, 600.0)})
        r = j.handle("Bir slogan öner")
        self.assertEqual(r["durum"], "ONAY BEKLİYOR")
        self.assertEqual(pricey.calls, [])
        ap = j.security.pending()[0]
        self.assertIn("pahalı işlem", ap["detail"])
        j.security.decide(ap["id"], True)
        self.assertEqual(j.resume_pending()[0]["durum"], "TAMAMLANDI")
        self.assertEqual(len(pricey.calls), 1)

    def test_19_daily_budget_enforced(self):
        cloud = Fake("bulut", models=["orta"])
        j = self.make(cloud, prices={"bulut/orta": (2.0, 10.0)})
        j.economy.set_budget("gunluk", 0.00001)
        r = j.handle("Bir slogan öner")
        self.assertEqual(r["durum"], "ONAY BEKLİYOR")
        self.assertEqual(cloud.calls, [])
        self.assertIn("günlük bütçe aşımı", j.security.pending()[0]["detail"])
        unknown = Fake("x", models=["fiyatsiz"])
        j2 = self.make(unknown)
        self.assertEqual(j2.handle("Bir slogan öner")["durum"], "ONAY BEKLİYOR")
        self.assertIn("fiyatı bilinmeyen", j2.security.pending()[0]["detail"])

    def test_20_task_cost_report(self):
        j = self.local_cloud({"kucuk": "empty"})
        r = j.handle("Bir slogan öner")
        rep = j.economy.task_report(r["gorev"])
        rows = self.usage(j)
        self.assertEqual(rep["istek"], 2)
        self.assertEqual(rep["giris"], sum(u["input_tokens"] for u in rows))
        self.assertAlmostEqual(rep["maliyet"], sum(u["cost"] for u in rows))
        self.assertEqual(rep["basarisiz_token"], 150)         # başarısız denemenin tüketimi
        self.assertEqual((rep["devir"], rep["modeller"]), (1, ["bulut/orta", "yerel/kucuk"]))

    def test_21_dashboard_matches_database(self):
        j = self.local_cloud({"kucuk": "error"})
        j.handle("Bir slogan öner")
        ek = j.status()["ekonomi"]
        raw = j.db.one("SELECT SUM(input_tokens) i, SUM(output_tokens) o, SUM(cost) c, "
                       "COUNT(*) n FROM token_usage")
        self.assertEqual((ek["giris"], ek["cikis"], ek["istek"]), (raw["i"], raw["o"], raw["n"]))
        self.assertAlmostEqual(ek["maliyet"], raw["c"])
        self.assertAlmostEqual(sum(m["maliyet"] for m in ek["model_bazli"]), raw["c"])
        page = render(j)
        self.assertIn("LLM Komuta Merkezi", page)
        self.assertIn("bulut/orta", page)
        self.assertNotIn(SECRET, page)

    def test_22_restart_keeps_task_memory(self):
        j, _ = self._two_step()
        tid = j.tasks.create("yarım kalan iş")
        j.tasks.move(tid, "ÇALIŞIYOR")                        # süreç burada çökmüş gibi
        j.db.run("INSERT INTO locks VALUES('gorev:x','eski','t')")
        again = Jarvis(self.home, providers=[Fake("yerel", YEREL, ["kucuk"])])
        self.addCleanup(again.db.close)
        self.assertEqual(len(again.db.all("SELECT * FROM token_usage")), 3)
        self.assertEqual(len(again.db.all("SELECT * FROM subtasks")), 2)
        self.assertEqual(len(again.db.all("SELECT * FROM task_handoffs")), 1)
        self.assertEqual(again.tasks.get(tid)["status"], "ENGELLENDİ")
        self.assertEqual(again.db.all("SELECT * FROM locks"), [])
        self.assertEqual(again.resume_pending()[0]["durum"], "TAMAMLANDI")

    def test_23_tests_rerun_after_model_switch(self):
        j = self.local_cloud()
        seen = []

        def validator(sub, text):
            seen.append(text)
            return "orta" in text                             # yerel modelin yanıtı testten geçemez
        j.router.validator = validator
        r = j.handle("Bir slogan öner")
        self.assertEqual(seen, ["yanıt[kucuk]", "yanıt[orta]"])
        self.assertEqual((r["durum"], r["sonuc"]), ("TAMAMLANDI", "yanıt[orta]"))

    def test_24_same_task_not_repeated(self):
        self.assertEqual(goal_hash("Bir  slogan ÖNER"), goal_hash("bir slogan öner"))
        j, _ = self._two_step()
        before = len(self.local.calls) + len(self.cloud.calls)
        r = j.handle("özetle: birinci bölüm metni\nözetle: ikinci bölüm metni")
        self.assertEqual(len(self.local.calls) + len(self.cloud.calls), before)
        self.assertEqual(r["durum"], "TAMAMLANDI")

    def test_25_memory_search_token_effect_measured(self):
        j, prompt = self._noisy()
        row = j.db.one("SELECT * FROM memory_retrievals ORDER BY id DESC LIMIT 1")
        self.assertGreater(row["sent_tokens"], 0)
        self.assertLess(row["sent_tokens"], row["pool_tokens"] / 5)   # ölçülen karşılaştırma
        everything = "\n".join(m["content"] for m in j.db.all("SELECT content FROM memory"))
        self.assertLess(len(prompt), len(everything))

    def test_26_local_cloud_local_distribution(self):
        j = self.local_cloud()
        r = j.handle("özetle: giriş metni\nPython ile API entegrasyon kodu yaz\nözetle: kapanış metni")
        self.assertEqual(r["durum"], "TAMAMLANDI")
        self.assertEqual([s["model_id"] for s in j.db.all("SELECT * FROM subtasks ORDER BY idx")],
                         ["yerel/kucuk", "bulut/orta", "yerel/kucuk"])
        self.assertEqual((len(self.local.calls), len(self.cloud.calls)), (2, 1))

    def test_27_multiple_models_work_merged(self):
        j, r = self._two_step()
        self.assertIn("ilk kısım hazır", r["sonuc"])
        self.assertIn("yanıt[orta]", r["sonuc"])
        sol = j.db.one("SELECT * FROM solutions")
        self.assertEqual(sol["models"], "bulut/orta,yerel/kucuk")
        self.assertEqual(j.memory.search("ilk kısım", layer="konusma")[0]["task_id"], r["gorev"])

    def test_28_secrets_do_not_leak(self):
        self.assertNotIn(SECRET, scrub(f"hata {SECRET}"))
        self.assertNotIn("AIzaSyA1234567890abcdef", scrub("key=AIzaSyA1234567890abcdef"))
        with mock.patch.dict("os.environ", {"FAKE_KEY": "ozel-anahtar-degeri-42"}):
            leaky = Fake("bulut", models=["orta"], auth_env="FAKE_KEY",
                         behavior={"orta": lambda p: (_ for _ in ()).throw(
                             ProviderError(f"yetkisiz: ozel-anahtar-degeri-42 / {SECRET}"))})
            ok = Fake("yedek", models=["b"])
            j = self.make(leaky, ok, prices={"bulut/orta": (1.0, 1.0), "yedek/b": (2.0, 2.0)})
            j.memory.add("baglanti", f"eski not: anahtar {SECRET} idi", "test", verified=True)
            r = j.handle("eski not anahtar konusunda bilgi ver")
        self.assertEqual(r["durum"], "TAMAMLANDI")
        dump = json.dumps([j.db.all(f"SELECT * FROM {t}") for t in (
            "audit", "task_handoffs", "task_checkpoints", "model_attempts", "token_usage",
            "providers", "tasks", "approvals", "memory_retrievals")], ensure_ascii=False)
        for secret in (SECRET, "ozel-anahtar-degeri-42"):
            self.assertNotIn(secret, dump)
            self.assertNotIn(secret, " ".join(p for _, p in leaky.calls + ok.calls))
        self.assertEqual(j.db.one("SELECT auth_env FROM providers WHERE name='bulut'")["auth_env"],
                         "FAKE_KEY")                           # yalnızca değişken adı saklanır

    def test_29_concurrent_runs_do_not_collide(self):
        slow = Fake("yerel", YEREL, ["kucuk"],
                    {"kucuk": lambda p: (time.sleep(0.15), Completion("tek sonuç", 5, 5))[1]})
        j = self.make(slow)
        out = []
        ts = [threading.Thread(target=lambda: out.append(j.handle("Bir slogan öner")))
              for _ in range(2)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(sorted(o["durum"] for o in out), ["ENGELLENDİ", "TAMAMLANDI"])
        self.assertEqual(len(slow.calls), 1)
        self.assertEqual(len(j.db.all("SELECT * FROM subtasks")), 1)
        self.assertEqual(j.db.all("SELECT * FROM locks"), [])

    def test_30_everything_is_auditable(self):
        pricey = Fake("bulut", models=["guclu"], behavior={"guclu": "error"})
        j = self.make(pricey, Fake("yedek", models=["b"]),
                      prices={"bulut/guclu": (1.0, 1.0), "yedek/b": (100.0, 600.0)})
        r = j.handle("Bir slogan öner")                       # hata → devir → pahalı model onayı
        self.assertEqual(r["durum"], "ONAY BEKLİYOR")
        j.security.decide(j.security.pending()[0]["id"], True)
        j.resume_pending()
        actions = [a["action"] for a in j.db.all("SELECT * FROM audit")]
        for needed in ("task.run", "llm.call", "spend.money", "approval.decide"):
            self.assertIn(needed, actions)
        self.assertTrue(all(u["task_id"] for u in self.usage(j)))    # her istek bir göreve bağlı
        self.assertTrue(all(h["package"] and h["from_model"] for h in
                            j.db.all("SELECT * FROM task_handoffs")))
        self.assertEqual(j.db.one("SELECT status FROM approvals")["status"], "KULLANILDI")
        with self.assertRaises(Exception):
            j.security.check("audit.delete")


class TestRouting(unittest.TestCase):
    def test_classify_and_split(self):
        self.assertEqual(classify("özetle: metin")[0], 1)
        self.assertEqual(classify("Python ile API entegrasyon kodu yaz"), (3, "kod"))
        self.assertEqual(classify("Sistemin mimari tasarımını çıkar")[0], 4)
        self.assertEqual(split("1. bir\n2) iki\n- üç"), ["bir", "iki", "üç"])
        self.assertEqual(split("tek satır"), ["tek satır"])


class _API(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        _API.seen.append(self.headers)
        if self.path.startswith("/v1/models"):
            return self._json({"data": [{"id": "llama-3", "context_length": 4096}]})
        if "pageToken=p2" in self.path:
            return self._json({"models": [{"name": "models/gemini-b", "inputTokenLimit": 10,
                                           "supportedGenerationMethods": ["generateContent"]}]})
        self._json({"nextPageToken": "p2", "models": [
            {"name": "models/gemini-a", "inputTokenLimit": 99, "outputTokenLimit": 9,
             "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/embed-x", "supportedGenerationMethods": ["embedContent"]}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _API.seen.append(self.headers)
        if self.path.endswith("generateContent"):
            return self._json({"candidates": [{"content": {"parts": [{"text": "selam"}]}}],
                               "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 4,
                                                 "thoughtsTokenCount": 2}})
        if body["model"] == "dolu":
            return self._json({"error": "rate limit"}, 429)
        usage = {} if body["model"] == "sayacsiz" else {
            "usage": {"prompt_tokens": 21, "completion_tokens": 8}}
        self._json({"choices": [{"message": {"content": "merhaba"}}], **usage})


class TestAdaptersOverHTTP(unittest.TestCase):
    """Adaptörleri gerçek HTTP üzerinden, yerel bir taklit sunucuya karşı sınar."""

    def setUp(self):
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), _API)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        env = mock.patch.dict("os.environ", {"no_proxy": "127.0.0.1", "NO_PROXY": "127.0.0.1",
                                             "T_KEY": "anahtar-xyz-123", "GEMINI_API_KEY": "g-key-123456"})
        env.start()
        self.addCleanup(env.stop)
        _API.seen.clear()

    def test_openai_compatible(self):
        p = OpenAICompatProvider("yerel", self.url + "/v1", "T_KEY", YEREL)
        self.assertEqual(p.list_models(), [{"id": "llama-3", "context": 4096, "max_output": None}])
        c = p.complete("llama-3", "selam", "sistem", 5)
        self.assertEqual((c.text, c.input_tokens, c.output_tokens, c.estimated), ("merhaba", 21, 8, False))
        self.assertTrue(p.complete("sayacsiz", "selam", "sistem", 5).estimated)
        with self.assertRaises(QuotaError):
            p.complete("dolu", "selam", "sistem", 5)
        self.assertEqual(_API.seen[0]["Authorization"], "Bearer anahtar-xyz-123")

    def test_gemini(self):
        p = GeminiProvider(self.url)
        self.assertEqual([m["id"] for m in p.list_models()], ["gemini-a", "gemini-b"])
        c = p.complete("gemini-a", "selam", "sistem", 5)
        self.assertEqual((c.text, c.input_tokens, c.output_tokens, c.reasoning), ("selam", 11, 4, 2))
        self.assertEqual(_API.seen[0]["x-goog-api-key"], "g-key-123456")

    def test_end_to_end_through_router(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        j = Jarvis(tmp.name, providers=[OpenAICompatProvider("yerel", self.url + "/v1", kind=YEREL)])
        self.addCleanup(j.db.close)
        r = j.handle("Bir slogan öner")
        self.assertEqual((r["durum"], r["sonuc"]), ("TAMAMLANDI", "merhaba"))
        u = j.db.one("SELECT * FROM token_usage")
        self.assertEqual((u["model_id"], u["input_tokens"], u["cost"]), ("yerel/llama-3", 21, 0.0))


class TestAcceptanceLedger(Base):
    def test_status_requires_recorded_results_and_live_flag(self):
        j = self.make()
        st = acceptance.status(j.db)
        self.assertEqual((st["dogrulanan"], st["toplam"]), (0, 30))
        j.db.run("INSERT INTO test_results VALUES(1,'t',1,'x')")   # canlı gerektirir
        j.db.run("INSERT INTO test_results VALUES(2,'t',1,'x')")
        j.db.run("INSERT INTO test_results VALUES(4,'t',0,'x')")
        st = acceptance.status(j.db)
        states = {t["no"]: t["durum"] for t in st["testler"]}
        self.assertIn("canlı doğrulama yok", states[1])
        self.assertEqual((states[2], states[4], states[5]),
                         ("Doğrulandı", "Test başarısız", "Test bekliyor"))
        self.assertEqual(st["dogrulanan"], 1)

    def test_live_check_per_provider(self):
        good = Fake("iyi", models=["a"])
        bad = Fake("bozuk", models=["b"], behavior={"b": "error"})
        j = self.make(good)
        j.db.run("INSERT INTO test_results VALUES(1,'t',1,'x')")
        out = acceptance.live(j)
        self.assertIn("iyi/a yanıt verdi (100 giriş / 50 çıkış", out)
        self.assertEqual({t["no"]: t["durum"] for t in acceptance.status(j.db)["testler"]}[1], "Doğrulandı")
        self.assertEqual(j.db.one("SELECT purpose, task_id FROM token_usage")["purpose"], "canli-test")
        j2 = self.make(good, bad)
        out = acceptance.live(j2)
        self.assertIn("ÇAĞRI BAŞARISIZ", out)
        self.assertNotIn(SECRET, out)
        self.assertEqual(j2.db.get_setting("canli.3"), "0")

    def test_run_records_real_results(self):
        import os
        if os.environ.get("JARVIS_KABUL_ICINDE"):  # kendi kendini sonsuz çağırmasın
            self.skipTest("kabul çalıştırması içinde")
        j = self.make()
        with mock.patch.dict("os.environ", {"JARVIS_KABUL_ICINDE": "1"}):
            st = acceptance.run(j.db)
        self.assertEqual(len(j.db.all("SELECT * FROM test_results WHERE ok=1")), 30)
        self.assertEqual(st["dogrulanan"], sum(not live for _, _, live in acceptance.TESTS))


if __name__ == "__main__":
    unittest.main()
