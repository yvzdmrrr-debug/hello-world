"""V40 kabul politikası (Bölüm 27): durumlar gerçek test kayıtlarına dayanır.

`python -m jarvis kabul` test paketini çalıştırır ve sonuçları veritabanına yazar.
Gerçek sağlayıcı gerektiren senaryolar benzetimle geçse bile "Doğrulandı" sayılmaz.
"""
import unittest
from pathlib import Path

from .db import DB, now

# (no, başlık, canlı sağlayıcı gerekir mi)
TESTS = [
    (1, "Bağlı sağlayıcıların model keşfi", True),
    (2, "Model fiyat ve yeteneklerinin kaydı", False),
    (3, "Gerçek giriş/çıkış token muhasebesi", True),
    (4, "Farklı fiyat tarifelerinin doğru hesabı", False),
    (5, "Basit görevin yerel modele yönlendirilmesi", True),
    (6, "Yerel model donduğunda güvenli zaman aşımı", True),
    (7, "Alternatif modele otomatik geçiş", True),
    (8, "Üst modelin yarım kalan işi devralması", True),
    (9, "Devralmada mevcut çıktıların korunması", False),
    (10, "Önceki modellerin ilgili çalışmalarının bulunması", False),
    (11, "Vektör tabanlı benzer görev araması", False),
    (12, "Yalnızca ilgili hafıza parçalarının gönderilmesi", False),
    (13, "Tamamlanmış işin yeniden kullanılması", False),
    (14, "Başarısız çözümün başarılı sayılmaması", False),
    (15, "API kota hatasının yönetimi", True),
    (16, "Günlük kota yenilenmesinin değerlendirilmesi", True),
    (17, "Bekleyen görevin yeniden başlatılması", False),
    (18, "Pahalı model için kullanıcı onayı", False),
    (19, "Günlük bütçe sınırının uygulanması", False),
    (20, "Görev bazlı maliyet raporu", False),
    (21, "Dashboard verilerinin veritabanıyla tutarlılığı", False),
    (22, "Yeniden başlatmada görev hafızasının korunması", False),
    (23, "Model değişiminden sonra testlerin tekrar çalışması", False),
    (24, "Aynı görevin gereksiz tekrar edilmemesi", False),
    (25, "Hafıza aramasının token tüketimine etkisinin ölçümü", False),
    (26, "Yerel → bulut → yerel görev dağıtımı", True),
    (27, "Birden fazla modelin geçmiş çalışmalarının birleştirilmesi", False),
    (28, "API anahtarlarının log ve devir paketlerine sızmaması", False),
    (29, "Eşzamanlı çalıştırıcıların aynı görevi bozmasının engellenmesi", False),
    (30, "Token, maliyet, devir ve onayların denetlenebilirliği", False),
]


def status(db: DB) -> dict:
    got = {r["test_no"]: r for r in db.all("SELECT * FROM test_results")}
    rows, verified = [], 0
    for no, title, live in TESTS:
        r = got.get(no)
        if not r:
            state = "Test bekliyor"
        elif not r["ok"]:
            state = "Test başarısız"
        elif live and db.get_setting(f"canli.{no}") != "1":
            state = "Test bekliyor (benzetimle geçti, canlı doğrulama yok)"
        else:
            state = "Doğrulandı"
            verified += 1
        rows.append({"no": no, "baslik": title, "durum": state})
    return {"testler": rows, "dogrulanan": verified, "toplam": len(TESTS),
            "yuzde": round(verified / len(TESTS) * 100)}


def run(db: DB, tests_dir: str | None = None) -> dict:
    """Kabul testlerini çalıştırır; `test_NN_...` adlı her testin sonucunu kaydeder."""
    tests_dir = tests_dir or str(Path(__file__).resolve().parent.parent / "tests")
    suite = unittest.defaultTestLoader.discover(tests_dir, pattern="test_economy.py")

    def walk(s):
        for t in s:
            if isinstance(t, unittest.TestSuite):
                yield from walk(t)
            else:
                yield t
    names = [t.id().split(".")[-1] for t in walk(suite)]  # çalıştırmadan önce topla
    result = unittest.TestResult()
    suite.run(result)
    failed = {t.id().split(".")[-1] for t, _ in result.failures + result.errors}
    for name in names:
        parts = name.split("_")
        if len(parts) > 1 and parts[1].isdigit():
            db.run("INSERT OR REPLACE INTO test_results VALUES(?,?,?,?)",
                   (int(parts[1]), name, int(name not in failed), now()))
    return status(db)


def live(j) -> str:
    """Her bağlı sağlayıcıyı kendi modeliyle dener: model keşfi + tek küçük gerçek çağrı.

    Tüm sağlayıcılarda keşif başarılıysa TEST 01, sağlayıcının bildirdiği gerçek token
    sayılarıyla muhasebe kaydı oluştuysa TEST 03 canlı doğrulanmış sayılır.
    """
    import time
    from .llm import SYSTEM
    from .providers import scrub
    if not j.router.providers:
        return "Bağlı sağlayıcı yok. Önce bir sağlayıcı anahtarı ya da JARVIS_LOCAL_URL tanımlayın."
    found = j.router.discover()
    lines, kesif_ok, sayim_ok = [], True, True
    secrets = [p.key() for p in j.router.providers.values()]
    for name, p in j.router.providers.items():
        if isinstance(found[name], str):
            kesif_ok = sayim_ok = False
            lines.append(f"{name}: KEŞİF BAŞARISIZ — {found[name]}")
            continue
        models = [m for m in j.economy.models() if m["provider"] == name and m["available"]]
        if not models:
            kesif_ok = sayim_ok = False
            lines.append(f"{name}: model bulunamadı")
            continue
        m = min(models, key=lambda x: (x["tier"], j.economy.estimate(x["id"], 100) or 1e9))
        started, t0 = now(), time.monotonic()
        try:
            comp = p.complete(m["model"], "Yalnızca 'tamam' yaz.", SYSTEM, 60)
        except Exception as e:
            sayim_ok = False
            j.economy.record_usage(task_id="canli-test", subtask_id=None, model_id=m["id"],
                                   started=started, status="hata", purpose="canli-test")
            lines.append(f"{name}: {found[name]} model; {m['id']} ÇAĞRI BAŞARISIZ — "
                         f"{scrub(str(e), secrets)[:200]}")
            continue
        j.economy.record_usage(task_id="canli-test", subtask_id=None, model_id=m["id"],
                               started=started, status="basarili", comp=comp, purpose="canli-test")
        sayim_ok = sayim_ok and not comp.estimated
        lines.append(f"{name}: {found[name]} model; {m['id']} yanıt verdi "
                     f"({comp.input_tokens} giriş / {comp.output_tokens} çıkış token"
                     f"{', TAHMİNİ' if comp.estimated else ''}, {time.monotonic() - t0:.1f} sn)")
    j.db.set_setting("canli.1", "1" if kesif_ok else "0")
    j.db.set_setting("canli.3", "1" if sayim_ok else "0")
    lines.append(f"TEST 01 canlı: {'doğrulandı' if kesif_ok else 'doğrulanmadı'} | "
                 f"TEST 03 canlı: {'doğrulandı' if sayim_ok else 'doğrulanmadı'}")
    return "\n".join(lines)
