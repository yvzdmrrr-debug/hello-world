# AgentOS Supreme

Sesli, tam ekran, holografik masaüstü yapay zekâ arayüzü (Electron).

## Kurulum (Windows)

1. `Kurulum.bat` dosyasına çift tıklayın. Bileşenleri indirir, masaüstüne **AgentOS Supreme**
   kısayolunu koyar ve uygulamayı başlatır. Node.js yoksa `winget` ile kurmayı dener.
2. Sonraki açılışlarda masaüstündeki kısayolu kullanın; terminal penceresi açılmaz.

İlk açılışta ses tanıma modeli (yaklaşık 77 MB) bir kez indirilir; sonra çevrimdışı çalışır.

## Kullanım

| Söyleyin (ya da alttaki kutuya yazın) | Ne olur |
|---|---|
| "Hey AgentOS" (ya da ekrana tıklayın) | Parçacıklar çekirdeği oluşturur, asistan uyanır |
| "Binance analizini getir" | Canlı fiyat paneli oluşur (BTC, ETH, BNB, SOL, XRP) |
| "Bitcoin ve Ethereum analizini getir" | Yalnızca söylenen paralarla panel oluşur |
| "Paneli kapat" | Panel animasyonla kapanır |
| "Bitcoin al" / "Ethereum sat" | Onay penceresi açılır (yalnızca sanal işlem) |
| "Onayla", "Evet" / "İptal et", "Kapat" | Onay penceresini sesle yönetir (fare ve Enter/Esc de çalışır) |
| "Saat kaç", "Uygulamayı kapat", "Uyu" | Küçük komutlar |

Asistan konuşurken siz konuşmaya başlarsanız yaklaşık 60 ms içinde susar ve dinlemeye geçer.
Çıkmak için `Esc` → "Onayla".

## Ayarlar (isteğe bağlı)

`ayarlar.ornek.json` dosyasını `ayarlar.json` adıyla kopyalayın:

- `sesModeli`: `Xenova/whisper-small` daha doğru tanır ama daha yavaştır ve 241 MB indirir.
- `sohbet`: OpenAI uyumlu bir sohbet ucu (ör. yerel Ollama). Tanımlı değilse asistan yalnızca
  yukarıdaki komutları bilir. Anahtar gerekiyorsa değerini değil, ortam değişkeninin adını yazın.

## Bilinen sınırlar

- Ses tanıma yereldir (Whisper). Kısa komutlarda ve yabancı kelimelerde hata yapabilir; eşleştirme
  bu hatalara göre toleranslıdır, ama her söyleyişi yakalamaz. Yazarak komut her zaman çalışır.
- Konuşma sesi Windows'un Türkçe sesidir. Türkçe ses yüklü değilse yanıtlar yalnızca altyazı olur
  (Ayarlar → Zaman ve dil → Konuşma → Ses ekle).
- Alım satım yalnızca benzetimdir; borsaya emir gönderen kod yoktur.
- Binance bazı ülkelerde ana akışı engeller; uygulama kendiliğinden yedek veri akışına geçer.

## Test

`npm test` komut anlama mantığını sınar.
