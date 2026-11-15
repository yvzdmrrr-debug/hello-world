"""JARVIS çekirdeği: hedefi alır, yönlendirir, çalıştırır, doğrular, kaydeder."""
import re
from pathlib import Path

from . import VERSION, finance, metrics, registry
from .agents import Agents
from .db import DB, now
from .llm import LLM, LLMUnavailable
from .memory import Memory
from .security import ApprovalRequired, Denied, Security, Stopped
from .skills import BUILTIN, SkillError, Skills
from .tasks import Tasks

_MATH = re.compile(r"[\d\s.,()+\-*/^%]+")


class Jarvis:
    def __init__(self, home: str = "."):
        home = Path(home)
        home.mkdir(parents=True, exist_ok=True)
        self.db = DB(str(home / "jarvis.db"))
        self.security = Security(self.db)
        self.memory = Memory(self.db, self.security)
        self.tasks = Tasks(self.db)
        self.skills = Skills(self.db, self.security, str(home / "skills"))
        self.agents = Agents(self.db, self.security, self.skills)
        self.llm = LLM()
        self._bootstrap()

    def _bootstrap(self):
        """İlk açılışta hazır Skill'leri fabrikadan geçirerek kurar ve sürümü kaydeder."""
        if self.db.get_setting("version") == VERSION or self.security.stopped:
            return
        results = {}
        for name, (desc, code, tests) in BUILTIN.items():
            if not self.skills.get(name):
                results[name] = self.skills.install(name, desc, code, tests)["ok"]
        self.db.run(
            "INSERT INTO versions(version,date,changes,components,tests,security,approval,"
            "rollback) VALUES(?,?,?,?,?,?,?,?)",
            (VERSION, now(), "V40.0 çekirdeği ilk kurulum", "çekirdek, hazır Skill'ler",
             f"hazır Skill kurulumu: {results}", "politika sabit, onay kapıları etkin",
             "kullanıcı tarafından kuruldu", "git ile önceki commit'e dönülür"))
        self.db.set_setting("version", VERSION)

    # ------------------------------------------------------------------ görev
    def handle(self, goal: str) -> dict:
        """Bir hedefi baştan sona işler ve Bölüm 26 biçiminde rapor döndürür."""
        goal = goal.strip()
        dept = registry.route(goal)
        tid = self.tasks.create(goal, dept)
        done, learned, approval = [f"Görev '{dept}' departmanına yönlendirildi"], [], []
        try:
            self.security.check("task.run", tid)
            self.tasks.move(tid, "ÇALIŞIYOR")
            result, verified = self._execute(goal, done)
            self.tasks.move(tid, "TEST EDİLİYOR")
            if not result.strip():
                raise SkillError("boş sonuç üretildi")
            self.tasks.move(tid, "TAMAMLANDI", result)
            self.memory.add("konusma", f"Hedef: {goal}\nSonuç: {result}", "jarvis",
                            task_id=tid, verified=verified,
                            confidence=0.95 if verified else 0.6)
            learned.append("Görev ve sonucu konuşma hafızasına kaydedildi"
                           + ("" if verified else " (doğrulanmamış olarak işaretli)"))
        except ApprovalRequired as e:
            self.tasks.move(tid, "ONAY BEKLİYOR", str(e))
            result = str(e)
            approval.append(f"Onay no {e.approval_id}: `onay {e.approval_id}` ile onaylayın")
        except (LLMUnavailable, Stopped, Denied) as e:
            self.tasks.move(tid, "ENGELLENDİ", str(e))
            result = f"Yapılamadı: {e}"
        except Exception as e:  # beklenmeyen hata: görev BAŞARISIZ, kayıt hata hafızasında
            self.tasks.move(tid, "BAŞARISIZ", str(e))
            result = f"Hata: {e}"
            if not self.security.stopped:
                self.memory.add("hata_cozum", f"Hedef: {goal}\nHata: {e}", "jarvis",
                                task_id=tid, verified=True, confidence=0.9)
                learned.append("Hata, hata-çözüm hafızasına kaydedildi")
        status = self.tasks.get(tid)["status"]
        return {"gorev": tid, "durum": status, "hedef": goal, "yapilanlar": done,
                "sonuc": result, "ogrenilenler": learned, "onay_gerekenler": approval}

    def _execute(self, goal: str, done: list) -> tuple[str, bool]:
        """(sonuç, doğrulandı mı) döndürür. Skill çıktıları deterministik ve testlidir."""
        low = goal.lower()
        expr = re.sub(r"hesapla|kaç eder|kaç|eder|[=?:]", "", low).strip()
        if _MATH.fullmatch(expr) and any(c.isdigit() for c in expr) \
                and any(o in expr for o in "+-*/^%"):
            done.append("'hesapla' Skill'i izole süreçte çalıştırıldı")
            return self.skills.run("hesapla", expr), True
        for trigger, skill in (("özetle", "ozetle"), ("ozetle", "ozetle"),
                               ("kelime say", "metin_istatistik"),
                               ("istatistik", "metin_istatistik")):
            if low.startswith(trigger):
                text = goal[len(trigger):].lstrip(" :")
                if text:
                    done.append(f"'{skill}' Skill'i izole süreçte çalıştırıldı")
                    return self.skills.run(skill, text), True
        self.security.check("llm.call", self.llm.model)
        context = "\n".join(f"- {m['content'][:300]}" for m in self.memory.search(goal, limit=5))
        answer = self.llm.ask(goal, context)
        done.append(f"Yanıt {self.llm.model} modeliyle üretildi")
        return answer, False  # model çıktısı bağımsız doğrulanmadı

    # ------------------------------------------------------------ evrim
    def evolve_skill(self, need: str) -> dict:
        """İhtiyaçtan yeni Skill üretir: LLM taslak yazar, fabrika test eder, geçerse kurulur."""
        draft = self.llm.draft_skill(need)
        tests = [(t["input"], t["expected"]) for t in draft["tests"]]
        report = self.skills.install(draft["name"], draft["description"], draft["code"], tests)
        self.memory.add("meta_ogrenme",
                        f"İhtiyaç: {need}\nSkill: {draft['name']}\nBaşarılı: {report['ok']}",
                        "skill_fabrikasi", verified=True, confidence=0.9)
        return {"name": draft["name"], **report}

    def experiment(self, hypothesis: str, criterion: str, prices: list[float], **params) -> dict:
        """Deney laboratuvarı: bir işlem stratejisi hipotezini sanal ortamda sınar."""
        self.security.check("experiment.run", hypothesis)
        self.security.check("finance.paper_trade", hypothesis)
        bt = finance.backtest(prices, **params)
        self.db.run(
            "INSERT INTO experiments(ts,hypothesis,criterion,environment,result,success,lessons)"
            " VALUES(?,?,?,?,?,?,?)",
            (now(), hypothesis, criterion, "sanal işlem (backtest)",
             f"getiri %{bt.return_pct}, en büyük düşüş %{bt.max_drawdown_pct}, "
             f"{len(bt.trades)} işlem", int(bt.return_pct > 0),
             "Geçmiş performans gelecekteki sonucu garanti etmez."))
        return {"getiri_yuzde": bt.return_pct, "en_buyuk_dusus_yuzde": bt.max_drawdown_pct,
                "islemler": bt.trades, "risk_limiti_durdurdu": bt.halted,
                "baslangic": bt.start, "bitis": bt.end}

    # ----------------------------------------------------------- durum
    def status(self) -> dict:
        return {
            "surum": VERSION,
            "durduruldu": self.security.stopped,
            "llm": {"model": self.llm.model, "bagli": self.llm.available},
            "bilesenler": registry.summary(),
            "metrikler": metrics.collect(self.db),
            "hafiza": self.memory.counts(),
            "skills": self.skills.catalog(),
            "ajanlar": self.agents.all(),
            "gorevler": self.tasks.recent(15),
            "onaylar": self.security.pending(),
            "surumler": self.db.all("SELECT * FROM versions ORDER BY id DESC LIMIT 5"),
            "denetim": self.db.all("SELECT * FROM audit ORDER BY id DESC LIMIT 15"),
        }


def format_report(r: dict) -> str:
    lines = [f"HEDEF: {r['hedef']}", f"DURUM: {r['durum']}", "YAPILANLAR:"]
    lines += [f"  - {x}" for x in r["yapilanlar"]]
    lines.append(f"SONUÇ: {r['sonuc']}")
    if r["ogrenilenler"]:
        lines.append("ÖĞRENİLENLER:")
        lines += [f"  - {x}" for x in r["ogrenilenler"]]
    if r["onay_gerekenler"]:
        lines.append("ONAY GEREKENLER:")
        lines += [f"  - {x}" for x in r["onay_gerekenler"]]
    return "\n".join(lines)
