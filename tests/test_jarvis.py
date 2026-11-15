import json
import tempfile
import threading
import unittest
import urllib.request
from unittest import mock

from jarvis import finance, registry
from jarvis.__main__ import safe
from jarvis.core import Jarvis
from jarvis.dashboard import serve
from jarvis.memory import LAYERS
from jarvis.security import ApprovalRequired, Denied, Stopped
from jarvis.skills import SkillError, scan


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.j = Jarvis(self.tmp.name, providers=[])
        self.addCleanup(self.j.db.close)


class TestRegistry(unittest.TestCase):
    def test_v40_counts(self):
        self.assertEqual(len(registry.DEPARTMENTS), 40)
        self.assertEqual(len(registry.COGNITIVE), 20)
        self.assertEqual(len(registry.ENGINES), 15)
        self.assertEqual(len(LAYERS), 20)
        self.assertEqual(len(set(LAYERS)), 20)

    def test_route(self):
        self.assertEqual(registry.route("binance için backtest yap"), "Finansal Strateji")
        self.assertEqual(registry.route("zzz"), "Bilgi ve Öğrenme")


class TestSecurity(Base):
    def test_forbidden_always_denied(self):
        for action in ("security.modify", "security.disable", "audit.delete"):
            with self.assertRaises(Denied):
                self.j.security.check(action)

    def test_policy_is_read_only(self):
        from jarvis.security import POLICY
        with self.assertRaises(TypeError):
            POLICY["security.modify"] = "DUSUK"

    def test_approval_flow_single_use(self):
        with self.assertRaises(ApprovalRequired) as cm:
            self.j.security.check("finance.real_trade", "x")
        self.assertTrue(self.j.security.decide(cm.exception.approval_id, True))
        self.j.security.check("finance.real_trade", "x")  # onayla geçer
        with self.assertRaises(ApprovalRequired):          # onay tek kullanımlık
            self.j.security.check("finance.real_trade", "x")

    def test_rejected_stays_blocked(self):
        with self.assertRaises(ApprovalRequired) as cm:
            self.j.security.check("spend.money", "y")
        self.j.security.decide(cm.exception.approval_id, False)
        with self.assertRaises(ApprovalRequired):
            self.j.security.check("spend.money", "y")

    def test_unknown_action_needs_approval(self):
        with self.assertRaises(ApprovalRequired):
            self.j.security.check("bilinmeyen.islem")

    def test_stop_blocks_everything_and_resume(self):
        self.j.security.stop()
        with self.assertRaises(Stopped):
            self.j.security.check("memory.read")
        self.assertEqual(self.j.handle("2+2")["durum"], "ENGELLENDİ")
        self.j.security.resume()
        self.assertEqual(self.j.handle("2+2")["durum"], "TAMAMLANDI")

    def test_audit_recorded(self):
        with self.assertRaises(Denied):
            self.j.security.check("security.modify")
        row = self.j.db.one("SELECT * FROM audit ORDER BY id DESC LIMIT 1")
        self.assertEqual((row["action"], row["outcome"]), ("security.modify", "REDDEDILDI"))


class TestMemory(Base):
    def test_all_layers_roundtrip(self):
        for layer in LAYERS:
            mid = self.j.memory.add(layer, f"kayıt {layer}", "test", verified=True)
            rec = self.j.memory.get(mid)
            for field in ("id", "source", "created", "verified", "confidence", "version", "access"):
                self.assertIsNotNone(rec[field])
        self.assertTrue(all(v >= 1 for v in self.j.memory.counts().values()))

    def test_unknown_layer(self):
        with self.assertRaises(ValueError):
            self.j.memory.add("yok", "x", "test")

    def test_unverified_confidence_capped(self):
        mid = self.j.memory.add("anlamsal", "dünya düzdür", "söylenti", confidence=1.0)
        rec = self.j.memory.get(mid)
        self.assertEqual(rec["verified"], 0)
        self.assertLessEqual(rec["confidence"], 0.7)

    def test_search_correct_export(self):
        mid = self.j.memory.add("kullanici", "en sevdiği renk mavi", "kullanici", verified=True)
        self.assertEqual(self.j.memory.search("renk")[0]["id"], mid)
        self.j.memory.correct(mid, "en sevdiği renk yeşil")
        rec = self.j.memory.get(mid)
        self.assertEqual((rec["content"], rec["version"]), ("en sevdiği renk yeşil", 2))
        self.assertIn("yeşil", json.loads(self.j.memory.export())[-1]["content"])

    def test_delete_requires_approval(self):
        mid = self.j.memory.add("kullanici", "silinecek", "kullanici")
        with self.assertRaises(ApprovalRequired) as cm:
            self.j.memory.delete(mid)
        self.assertIsNotNone(self.j.memory.get(mid))
        self.j.security.decide(cm.exception.approval_id, True)
        self.j.memory.delete(mid)
        self.assertIsNone(self.j.memory.get(mid))


class TestTasks(Base):
    def test_cannot_complete_without_test(self):
        tid = self.j.tasks.create("x")
        with self.assertRaises(ValueError):
            self.j.tasks.move(tid, "TAMAMLANDI")
        self.j.tasks.move(tid, "ÇALIŞIYOR")
        with self.assertRaises(ValueError):
            self.j.tasks.move(tid, "TAMAMLANDI")
        self.j.tasks.move(tid, "TEST EDİLİYOR")
        self.j.tasks.move(tid, "TAMAMLANDI", "ok")
        self.j.tasks.move(tid, "GERİ ALINDI")
        self.assertEqual(self.j.tasks.get(tid)["status"], "GERİ ALINDI")


GOOD = "def run(girdi):\n    return girdi.upper()\n"


class TestSkills(Base):
    def test_builtins_installed_and_tested(self):
        names = {s["name"] for s in self.j.skills.catalog()}
        self.assertEqual(names, {"hesapla", "metin_istatistik", "ozetle"})
        self.assertTrue(all(s["test_status"].startswith("GEÇTİ") for s in self.j.skills.catalog()))

    def test_scan_flags_dangerous_code(self):
        self.assertTrue(scan("import os\ndef run(g):\n    return g"))
        self.assertTrue(scan("def run(g):\n    return open(g).read()"))
        self.assertTrue(scan("def run(g):\n    return g.__class__"))
        self.assertTrue(scan("def baska(g):\n    return g"))
        self.assertEqual(scan(GOOD), [])

    def test_install_run_and_metrics(self):
        r = self.j.skills.install("buyut", "metni büyük harfe çevirir", GOOD, [("a", "A")])
        self.assertTrue(r["ok"])
        self.assertEqual(self.j.skills.run("buyut", "selam"), "SELAM")
        s = self.j.skills.get("buyut")
        self.assertEqual((s["uses"], s["successes"], s["version"]), (1, 1, 1))

    def test_failing_tests_not_installed(self):
        r = self.j.skills.install("bozuk", "yanlış", GOOD, [("a", "yanlış beklenti")])
        self.assertFalse(r["ok"])
        self.assertIsNone(self.j.skills.get("bozuk"))

    def test_untested_skill_rejected(self):
        with self.assertRaises(SkillError):
            self.j.skills.install("testsiz", "x", GOOD, [])

    def test_dangerous_skill_needs_approval(self):
        code = "import os\ndef run(g):\n    return os.getcwd()\n"
        with self.assertRaises(ApprovalRequired):
            self.j.skills.install("tehlikeli", "x", code, [("a", "b")])
        self.assertIsNone(self.j.skills.get("tehlikeli"))

    def test_timeout_isolated(self):
        code = "def run(g):\n    while True:\n        pass\n"
        with mock.patch("jarvis.skills.execute.__defaults__", (0.5,)):
            r = self.j.skills.install("sonsuz", "x", code, [("a", "b")])
        self.assertFalse(r["ok"])
        self.assertIn("zaman aşımı", r["results"][0]["got"])

    def test_version_and_rollback_keeps_old(self):
        self.j.skills.install("s", "v1", GOOD, [("a", "A")])
        v2 = "def run(girdi):\n    return girdi.lower()\n"
        self.assertEqual(self.j.skills.install("s", "v2", v2, [("A", "a")])["version"], 2)
        self.assertEqual(self.j.skills.run("s", "Ab"), "ab")
        # bozuk bir v3 denemesi çalışan v2'yi bozmaz
        self.assertFalse(self.j.skills.install("s", "v3", v2, [("A", "X")])["ok"])
        self.assertEqual(self.j.skills.get("s")["version"], 2)
        with self.assertRaises(ApprovalRequired) as cm:
            self.j.skills.rollback("s")
        self.j.security.decide(cm.exception.approval_id, True)
        self.assertEqual(self.j.skills.rollback("s"), 1)
        self.assertEqual(self.j.skills.run("s", "Ab"), "AB")

    def test_duplicates_detected(self):
        self.j.skills.install("a1", "metni büyük harfe çevirir", GOOD, [("a", "A")])
        self.j.skills.install("a2", "metni büyük harfe çevirir", GOOD, [("a", "A")])
        self.assertIn(("a1", "a2"), self.j.skills.duplicates())


class TestAgents(Base):
    def test_agent_least_privilege(self):
        self.j.agents.create("hesapci", "hesap yapar", "matematik", ["hesapla"], "doğru sonuç")
        self.assertEqual(self.j.agents.run("hesapci", "hesapla", "6*7"), "42")
        with self.assertRaises(SkillError):
            self.j.agents.run("hesapci", "ozetle", "metin")
        with self.assertRaises(SkillError):
            self.j.agents.create("x", "m", "e", ["olmayan_skill"], "k")
        self.assertEqual(self.j.agents.get("hesapci")["successes"], 1)


class TestFinance(Base):
    UP = [10, 10, 10, 10, 10, 10, 10, 11, 12, 13, 14, 15, 16, 17, 18]
    DOWN = [10, 10, 10, 10, 10, 10, 10, 12, 14, 9, 6, 4, 3, 2, 1]

    def test_uptrend_profit(self):
        bt = finance.backtest(self.UP)
        self.assertGreater(bt.return_pct, 0)
        self.assertEqual(bt.trades[0][0], "AL")

    def test_risk_limit_halts(self):
        bt = finance.backtest(self.DOWN, fast=1, slow=7, max_loss_pct=10)
        self.assertGreater(bt.max_drawdown_pct, 0)
        self.assertGreaterEqual(bt.end, 0)
        loose = finance.backtest([10] * 7 + [20, 30, 5, 5, 5, 5], fast=1, slow=7, max_loss_pct=10)
        self.assertTrue(loose.halted or loose.return_pct > -100)

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            finance.backtest([1, 2, 3])
        with self.assertRaises(ValueError):
            finance.backtest(self.UP, fast=7, slow=3)

    def test_experiment_recorded_as_virtual(self):
        r = self.j.experiment("SMA kesişimi kâr eder", "getiri > 0", self.UP)
        self.assertGreater(r["getiri_yuzde"], 0)
        row = self.j.db.one("SELECT * FROM experiments")
        self.assertIn("sanal", row["environment"])

    def test_real_trade_gated(self):
        with self.assertRaises(ApprovalRequired):
            self.j.security.check("finance.real_trade", "BTC al")


class TestCore(Base):
    def test_math_goal_completes_and_is_remembered(self):
        r = self.j.handle("hesapla (12+8)*3")
        self.assertEqual((r["durum"], r["sonuc"]), ("TAMAMLANDI", "60"))
        mem = self.j.memory.search("60", layer="konusma")
        self.assertEqual(mem[0]["verified"], 1)

    def test_summary_goal(self):
        r = self.j.handle("özetle: Tek cümle.")
        self.assertEqual((r["durum"], r["sonuc"]), ("TAMAMLANDI", "Tek cümle."))

    def test_without_llm_is_blocked_not_faked(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            r = self.j.handle("Bana bir iş planı yaz")
        self.assertEqual(r["durum"], "ENGELLENDİ")
        self.assertIn("LLM", r["sonuc"])

    def test_failure_recorded(self):
        r = self.j.handle("1/0")
        self.assertEqual(r["durum"], "BAŞARISIZ")
        self.assertEqual(self.j.memory.counts()["hata_cozum"], 1)

    def test_evolve_skill_goes_through_factory(self):
        draft = {"name": "ters", "description": "metni ters çevirir",
                 "code": "def run(girdi):\n    return girdi[::-1]\n",
                 "tests": [{"input": "abc", "expected": "cba"}]}
        with mock.patch.object(type(self.j.llm), "draft_skill", return_value=draft):
            self.assertTrue(self.j.evolve_skill("metni ters çevir")["ok"])
        self.assertEqual(self.j.skills.run("ters", "xyz"), "zyx")
        bad = dict(draft, name="ters2", tests=[{"input": "abc", "expected": "abc"}])
        with mock.patch.object(type(self.j.llm), "draft_skill", return_value=bad):
            self.assertFalse(self.j.evolve_skill("yanlış taslak")["ok"])
        self.assertIsNone(self.j.skills.get("ters2"))

    def test_persistence_across_restart(self):
        self.j.handle("2+3")
        again = Jarvis(self.tmp.name, providers=[])
        self.addCleanup(again.db.close)
        self.assertEqual(again.status()["metrikler"]["gorev_toplam"], 1)
        self.assertEqual(len(again.db.all("SELECT * FROM versions")), 1)

    def test_metrics_from_real_records(self):
        self.j.handle("2+2")
        self.j.handle("1/0")
        m = self.j.status()["metrikler"]
        self.assertEqual((m["gorev_toplam"], m["gorev_basari_orani"]), (2, 50.0))

    def test_cli(self):
        self.assertIn("40", safe(self.j, "durum"))
        self.assertIn("hesapla", safe(self.j, "skills"))
        self.assertIn("SONUÇ: 4", safe(self.j, "2+2"))
        mid = safe(self.j, "hatirla kahveyi sütsüz içerim").split(": ")[1]
        self.assertIn("sütsüz", safe(self.j, "ara kahve"))
        self.assertIn("onay", safe(self.j, f"sil {mid}"))
        self.assertIn("memory.delete", safe(self.j, "onaylar"))


class TestDashboard(Base):
    def setUp(self):
        super().setUp()
        self.srv = serve(self.j, 0)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)

    def post(self, path, data=""):
        return urllib.request.urlopen(self.url + path, data.encode()).read().decode()

    def test_pages_and_actions(self):
        self.assertIn("JARVIS SUPREME", urllib.request.urlopen(self.url).read().decode())
        self.assertIn("SONUÇ: 42", self.post("/task", "goal=6*7"))
        status = json.load(urllib.request.urlopen(self.url + "/api/status"))
        self.assertEqual(status["metrikler"]["gorev_toplam"], 1)
        self.post("/stop")
        self.assertTrue(self.j.security.stopped)
        self.post("/resume")
        self.assertFalse(self.j.security.stopped)

    def test_html_escaped(self):
        page = self.post("/task", "goal=%3Cscript%3Ealert(1)%3C/script%3E")
        self.assertNotIn("<script>alert", page)

    def test_cross_origin_post_rejected(self):
        req = urllib.request.Request(self.url + "/stop", b"", {"Origin": "http://kotu.example"})
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(req)
        self.assertFalse(self.j.security.stopped)


if __name__ == "__main__":
    unittest.main()
