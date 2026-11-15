"""V40.0 bileşen envanteri: 40 departman, 20 bilişsel sistem, 15 evrim motoru.

Durumlar dürüstçe üç sınıfa ayrılır:
  KOD  — bu depoda çalışan ve testi olan kodla karşılanıyor
  LLM  — iş, Claude bağlantısı varken dil modeliyle yapılıyor (bağlantı yoksa çalışmaz)
  PLAN — henüz uygulanmadı (dış bağlantı veya ek altyapı gerekiyor)

Not: V40 anayasası 25-40. departmanları, 11-20. bilişsel sistemleri ve 15 evrim motorunu
adlandırmıyor. Aşağıdaki adlar V30 bölümlerinden türetilmiş bir öneridir; kullanıcı onayına
tabidir (bkz. README).
"""
KOD, LLM, PLAN = "KOD", "LLM", "PLAN"

# (ad, durum, yönlendirme anahtar kelimeleri)
DEPARTMENTS = [
    ("Ajan Üretim Fabrikası", KOD, "ajan"),
    ("Skill Mühendisliği", KOD, "skill beceri yetenek"),
    ("Yazılım Mühendisliği", LLM, "kod yazılım python javascript program fonksiyon"),
    ("Yapay Zekâ Araştırma", LLM, "model algoritma yapay"),
    ("Kalıcı Hafıza", KOD, "hafıza hatırla kaydet unutma"),
    ("Bilgi ve Öğrenme", LLM, "öğren bilgi açıkla nedir"),
    ("Test ve Simülasyon", KOD, "test simülasyon doğrula"),
    ("Siber Güvenlik", KOD, "güvenlik yetki şifre izin"),
    ("API ve MCP", PLAN, "api mcp entegrasyon bağlantı"),
    ("Bilgisayar Operasyonları", PLAN, "windows dosya klasör uygulama"),
    ("Web ve Araştırma", PLAN, "araştır internet web kaynak"),
    ("Veritabanı Yönetimi", KOD, "veritabanı sqlite sql tablo"),
    ("Model Orkestrasyonu", KOD, "llm claude model seçimi"),
    ("Otomasyon", PLAN, "zamanla otomatik tetikle her gün"),
    ("Performans", KOD, "performans hız metrik ölç"),
    ("Finans ve Kaynak", LLM, "maliyet bütçe kaynak"),
    ("Proje Yönetimi", KOD, "proje görev teslimat plan"),
    ("Arayüz ve Tasarım", KOD, "dashboard panel arayüz tasarım"),
    ("Ses ve Görüntü", PLAN, "ses görüntü resim video"),
    ("Sürüm ve Yedekleme", KOD, "sürüm yedek geri al"),
    ("Kalite Denetimi", KOD, "kalite denetim gereksinim"),
    ("Hata Analizi", LLM, "hata bug sorun neden çalışmıyor"),
    ("Stratejik Planlama", LLM, "strateji uzun vade hedef"),
    ("İnovasyon Laboratuvarı", LLM, "fikir prototip yenilik"),
    # --- V40 önerileri ---
    ("Evrim Yönetimi", KOD, "evrim gelişim iyileştir"),
    ("Meta-Öğrenme", KOD, "meta tekrar eden birleştir"),
    ("Deney Laboratuvarı", KOD, "deney hipotez"),
    ("E-Ticaret", PLAN, "satış ürün mağaza sipariş stok seo"),
    ("Finansal Strateji", KOD, "binance kripto borsa backtest al sat"),
    ("Risk Yönetimi", KOD, "risk kayıp limit"),
    ("Hedef Genişletme", LLM, "daha fazla büyüt artır"),
    ("Öngörü ve Yetenek Planlama", LLM, "gelecek öngör ihtiyaç"),
    ("Veri Analizi", KOD, "analiz istatistik hesapla veri"),
    ("İçerik ve Dil", KOD, "özet özetle metin çeviri yaz"),
    ("Müşteri Deneyimi", PLAN, "müşteri destek şikayet"),
    ("Hukuk ve Uyum", LLM, "mevzuat vergi yasa sözleşme"),
    ("Denetim ve Kayıt", KOD, "kayıt log denetim izi"),
    ("Bağımlılık ve Ortam Yönetimi", PLAN, "bağımlılık kurulum paket ortam"),
    ("Dokümantasyon", LLM, "doküman belge kılavuz"),
    ("Kullanıcı Onay ve Yetki", KOD, "onay onayla reddet yetki"),
]

# (ad, durum, karşılayan modül)
COGNITIVE = [
    ("Bilişsel Çekirdek", KOD, "core"), ("Stratejik Akıl Yürütme", LLM, "llm"),
    ("Kalıcı Hafıza", KOD, "memory"), ("Evrensel Skill Motoru", KOD, "skills"),
    ("Yazılım Üretim Motoru", LLM, "llm"), ("Dinamik Ajan Motoru", KOD, "agents"),
    ("Evrensel Bağlantı Motoru", PLAN, "-"), ("Test ve Simülasyon Motoru", KOD, "skills"),
    ("Güvenlik ve Yetki Motoru", KOD, "security"), ("Sürekli Gelişim Motoru", KOD, "metrics"),
    # --- V40 önerileri ---
    ("Meta-Öğrenme", KOD, "skills"), ("Hedef Genişletme", LLM, "llm"),
    ("Öngörülü Yetenek Geliştirme", LLM, "llm"), ("Dijital Deney Laboratuvarı", KOD, "core"),
    ("Çoklu Model Orkestrasyonu", KOD, "llm"), ("Proaktif Operasyon", PLAN, "-"),
    ("Görev Doğrulama", KOD, "tasks"), ("Sürüm ve Geri Alma", KOD, "skills"),
    ("Gelişim Metrikleri", KOD, "metrics"), ("Kullanıcı İletişimi ve Raporlama", KOD, "core"),
]

ENGINES = [
    ("İhtiyaç Analizi", KOD, "core"), ("Skill Fabrikası", KOD, "skills"),
    ("Kod Üretimi", LLM, "llm"), ("İzole Test", KOD, "skills"),
    ("Güvenlik Denetimi", KOD, "skills"), ("Sürümleme", KOD, "skills"),
    ("Geri Alma", KOD, "skills"), ("Meta-Öğrenme", KOD, "skills"),
    ("Ajan Fabrikası", KOD, "agents"), ("Bağlantı Uzmanlaşması", PLAN, "-"),
    ("Deney", KOD, "core"), ("Metrik", KOD, "metrics"), ("Öngörü", LLM, "llm"),
    ("Hedef Genişletme", LLM, "llm"), ("Onay", KOD, "security"),
]


def route(goal: str) -> str:
    """Hedef metnini anahtar kelime eşleşmesiyle bir departmana yönlendirir."""
    text = goal.lower()
    best, score = "Bilgi ve Öğrenme", 0
    for name, _, keywords in DEPARTMENTS:
        s = sum(k in text for k in keywords.split())
        if s > score:
            best, score = name, s
    return best


def summary() -> dict:
    out = {}
    for label, items in (("departman", DEPARTMENTS), ("bilissel", COGNITIVE),
                         ("motor", ENGINES)):
        out[label] = {s: sum(1 for i in items if i[1] == s) for s in (KOD, LLM, PLAN)}
        out[label]["toplam"] = len(items)
    return out
