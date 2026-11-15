# AgentOS Supreme
Bu depo GitHub Flow'u uygulamak içindir.
uykuyu seviyorum
çok severim hem

---

## JARVIS SUPREME V40.0 çekirdeği

Tek merkezli, denetlenebilir dijital zekâ çekirdeği. Python 3.10+ ile çalışır; çekirdeğin
dış bağımlılığı yoktur.

## Çalıştırma

```bash
python -m jarvis            # sohbet (komutlar için: yardim)
python -m jarvis panel      # Dashboard: http://127.0.0.1:8040
python -m unittest discover -s tests   # testler
```

### LLM sağlayıcıları

Tanımlı ortam değişkenlerine göre sağlayıcılar kendiliğinden bağlanır. Anahtarları koda
ya da depoya yazmayın; JARVIS yalnızca değişkenin adını saklar.

| Değişken | Sağlayıcı |
|---|---|
| `JARVIS_LOCAL_URL` | Yerel model (Ollama, llama.cpp vb.), örn. `http://localhost:11434/v1` |
| `GEMINI_API_KEY` | Google Gemini |
| `ANTHROPIC_API_KEY` | Claude (`pip install -r requirements.txt` gerekir) |
| `OPENAI_API_KEY` | OpenAI |
| `OPENROUTER_API_KEY` | OpenRouter |

```bash
python -m jarvis kesfet     # modelleri listele (ücretsiz)
python -m jarvis modeller   # seviye, fiyat, kota
python -m jarvis kabul      # 30 kabul testini çalıştır, sonucu panele yaz
```

Sağlayıcı yokken JARVIS çevrimdışı çalışır; dil modeli gerektiren işleri uydurmaz,
`ENGELLENDİ` olarak bildirir.

### LLM ve token ekonomisi nasıl çalışır

- **Seviye 0:** hesaplama gibi işler LLM'siz, testli Skill'lerle çözülür.
- **Model seçimi:** beklenen maliyet, doğrulanmış başarı oranına bölünerek sıralanır;
  yerel ve ucuz modeller uygunsa öne geçer, kod ve mimari işleri doğrudan üst seviyeden başlar.
- **Model kaçışı ve devir:** zaman aşımı, hata, kota ya da başarısız kabul testinde iş bir
  sonraki uygun modele devredilir. Tamamlanan alt görevler yeniden yapılmaz.
- **Muhasebe:** her istek token, maliyet ve tarife sürümüyle kaydedilir. Fiyatı bilinmeyen
  model sıfır sayılmaz; onay ister. Fiyatı `fiyat <model> <giriş> <çıkış>` ile siz tanımlarsınız
  (yalnızca Claude fiyatları hazır gelir).
- **Bütçe:** günlük 5, aylık 50, görev başına 1 USD; 0,5 USD üstü tek çağrı onay ister.
  `butce` komutuyla değişir.
- **Hafıza araması:** metadata → tam metin → vektör → yeniden sıralama; modele yalnızca
  ilgili kayıtlar, token bütçesi içinde gider.

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
| Sağlayıcı adaptörleri | `jarvis/providers.py` | Yerel/OpenAI uyumlu, Gemini, Claude. Canlı API ile **denenmedi**; yerel taklit sunucuya karşı sınandı |
| Token muhasebesi, bütçe, kota | `jarvis/economy.py` | Tarife sürümleri, onay kapıları, yenilenme saatine göre kota |
| Yönlendirme ve görev devri | `jarvis/router.py` | Alt görevlere ayırma, model seçimi, devir paketi, kilit |
| Kademeli hafıza araması | `jarvis/retrieval.py` | Kalıcı vektör indeksi; içerik değişmedikçe yeniden üretilmez |
| Kabul kaydı | `jarvis/acceptance.py` | 30 senaryo; durumlar gerçek test kayıtlarından okunur |

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
- **Kabul durumu 21/30.** Kalan 9 senaryo gerçek sağlayıcı gerektirir; benzetimle geçtiler
  ama anayasanın 27. bölümü gereği canlı doğrulanmadan "Doğrulandı" sayılmıyorlar.
- Vektörler yerel karakter-üçlüsü karma vektörüdür; bir sinir ağı embedding'i değildir.
  Yazım benzerliğini iyi, eş anlamlılığı zayıf yakalar.
- Görev parçalama ve seviye sınıflandırması kelime tabanlıdır (satır satır böler).
- Kota ve fiyatlar sağlayıcıdan otomatik çekilmez; kullanıcı tanımıdır.
- Anayasadaki bazı tablolar ayrı tablo değil: `cost_ledger` `token_usage` içinde,
  `approval_requests` `approvals`, `audit_events` `audit`, `budget_policies` `settings` içinde.
- Dashboard'da saatlik grafik, ajan bazlı harcama ve tasarruf tahmini yok.
