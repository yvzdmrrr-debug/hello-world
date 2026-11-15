# hello-world
Bu depo GitHub Flow'u uygulamak içindir.
uykuyu seviyorum
çok severim hem

---

# JARVIS SUPREME V40.0

Tek merkezli, denetlenebilir dijital zekâ çekirdeği. Python 3.10+ ile çalışır; çekirdeğin
dış bağımlılığı yoktur.

## Çalıştırma

```bash
python -m jarvis            # sohbet (komutlar için: yardim)
python -m jarvis panel      # Dashboard: http://127.0.0.1:8040
python -m unittest discover -s tests   # testler
```

Serbest sorular ve otomatik Skill üretimi için Claude bağlantısı gerekir:

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...     # anahtarı koda veya depoya yazmayın
```

Bağlantı yokken JARVIS çevrimdışı çalışır; dil modeli gerektiren işleri uydurmaz,
`ENGELLENDİ` olarak bildirir.

## Ne çalışıyor (testli)

| Bileşen | Dosya | Özet |
|---|---|---|
| Güvenlik ve yetki | `jarvis/security.py` | Sabit politika, tek kullanımlık onay, durdurma anahtarı, denetim kaydı |
| 20 katmanlı hafıza | `jarvis/memory.py` | SQLite; ekle, ara, düzelt, sil (onaylı), dışa aktar |
| Görev doğrulama | `jarvis/tasks.py` | 8 durum; test edilmeden `TAMAMLANDI` olunamaz |
| Skill fabrikası | `jarvis/skills.py` | Güvenlik taraması, izole süreçte test, sürümleme, geri alma |
| Ajan fabrikası | `jarvis/agents.py` | Ajan yalnızca kendisine verilen Skill'leri kullanır |
| Sanal işlem | `jarvis/finance.py` | Hareketli ortalama backtest'i, kayıp limiti |
| Dashboard | `jarvis/dashboard.py` | Gerçek durum, hedef verme, onay, durdurma |
| Claude bağlantısı | `jarvis/llm.py` | Canlı API ile **denenmedi** (anahtar yoktu); testlerde taklit edildi |

## Bilinen sınırlar

- **40 departman / 20 bilişsel sistem / 15 evrim motoru** `jarvis/registry.py` içinde
  listelenir ve her biri `KOD`, `LLM` ya da `PLAN` olarak işaretlidir. Ayrı ayrı 40 uzman
  yazılım değil; çoğu bir yönlendirme etiketidir. Panel gerçek dağılımı gösterir.
- V40 anayasası 25–40. departmanları, 11–20. bilişsel sistemleri, 13–20. hafıza
  katmanlarını ve evrim motorlarını adlandırmıyor. Buradaki adlar V30 bölümlerinden
  türetilmiş bir **öneridir**; değiştirmek için `registry.py` ve `memory.py` yeterli.
- **Henüz yok:** Binance / e-ticaret / MCP bağlantıları, gerçek para ile işlem, web
  araştırması, Windows kontrolü, ses-görüntü, zamanlanmış otomatik çalışma. Sistem
  yalnızca siz komut verdiğinizde çalışır.
- Skill izolasyonu süreç düzeyindedir (ayrı Python süreci, zaman aşımı, kod taraması);
  işletim sistemi düzeyinde bir kum havuzu değildir.
- Hafıza araması kelime eşleşmesidir, anlamsal (vektör) arama değildir.
